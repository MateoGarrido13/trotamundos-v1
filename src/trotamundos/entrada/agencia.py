# SPEC: SPEC-REF-05
# ELEMENTO PASO 5: Adaptador de agencia (capa anti-corrupción), IAgencia (ITERACION_4)
# ADRs: ADR-IT4-010, ADR-IT3-002, ADR-IT3-003
# DRIVERS: REF-05, CON-02
"""Adaptador de agencia: lleva los pedidos de la cola de casos de ayuda a la agencia y trae de
vuelta sus cambios de estado.

Corre en los nodos de entrada, junto a la ingesta. **No escribe la Base de viajes ni la lee**: no
sabe qué casos hay abiertos, y todo cambio de estado vuelve por la cola de novedades, la ingesta
y el Orquestador. Enruta cada pedido al adaptador `IAgencia` de la agencia que el caso guardó:
una agencia nueva es un adaptador más en el registro, sin tocar al Orquestador (`CON-02`)."""
from __future__ import annotations

import asyncio
import hmac
import logging
from collections.abc import Awaitable, Callable, Mapping

from trotamundos.broker import Broker, ColaLlena, Mensaje, NombreCola, ResultadoEntrega
from trotamundos.config import ConfiguracionAgencias
from trotamundos.dominio.agencias import EstadoCaso, IAgencia, PedidoCaso

log = logging.getLogger(__name__)

# Estados que una agencia puede informar. «En trámite» y «sin entregar» son del Orquestador.
INFORMABLES = (EstadoCaso.ABIERTO, EstadoCaso.EN_CURSO, EstadoCaso.RESUELTO)


class ErrorAgencia(Exception):
    """La API de la agencia no respondió o falló."""


class ClaveInvalida(Exception):
    """El aviso no trae la clave compartida."""


class AgenciaDesconocida(Exception):
    """No hay un adaptador registrado con ese nombre."""


class MockAgencia:
    """API de agencia simulada (`CON-02`). Se le puede inyectar demora o caída, y puede perder la
    respuesta después de haber abierto el caso. Una agencia real descarta un `abrirCaso` repetido
    con el mismo identificador; este mock también."""

    def __init__(self, nombre: str, *,
                 dormir: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self.nombre = nombre
        self._dormir = dormir
        self.casos: dict[str, EstadoCaso] = {}  # lo que la agencia tiene abierto
        self.pedidos: list[PedidoCaso] = []  # cada caso nuevo que abrió, con el pedido recibido
        self.caida = False
        self.demora_segundos = 0.0
        self.respuestas_perdidas = 0  # veces que abre el caso y no responde
        self.llamadas_abrir = 0
        self.consultas = 0

    async def _espera(self) -> None:
        if self.demora_segundos:
            await self._dormir(self.demora_segundos)
        if self.caida:
            raise ErrorAgencia(f"la API de {self.nombre} no responde")

    async def abrir_caso(self, pedido: PedidoCaso) -> None:
        self.llamadas_abrir += 1
        await self._espera()
        if pedido.id_caso not in self.casos:  # idempotente por identificador
            self.casos[pedido.id_caso] = EstadoCaso.ABIERTO
            self.pedidos.append(pedido)
        if self.respuestas_perdidas:
            self.respuestas_perdidas -= 1
            raise ErrorAgencia("la agencia abrió el caso pero la respuesta se perdió")

    async def consultar_caso(self, id_caso: str) -> EstadoCaso | None:
        self.consultas += 1
        await self._espera()
        return self.casos.get(id_caso)

    def cambiar_estado(self, id_caso: str, estado: EstadoCaso) -> None:
        """La agencia trabaja el caso (en la prueba, antes de avisar)."""
        self.casos[id_caso] = estado


class AdaptadorAgencia:
    def __init__(
        self,
        broker: Broker,
        agencias: Mapping[str, IAgencia],
        configuracion: ConfiguracionAgencias | None = None,
        *,
        dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._broker = broker
        self._agencias = dict(agencias)
        self._cfg = configuracion or ConfiguracionAgencias()
        self._dormir = dormir
        self._ultimo_id: str | None = None

    @property
    def agencias(self) -> dict[str, IAgencia]:
        """Los adaptadores registrados, por nombre de agencia."""
        return self._agencias

    # --- cola de casos de ayuda -> agencia ----------------------------------------------
    async def procesar_uno(self) -> ResultadoEntrega:
        """Toma un pedido y llama a `abrirCaso`. El Broker reintenta (1 s, 2 s, 4 s) y, al
        agotar los reintentos, lo manda a mensajes muertos; entonces se publica la novedad
        «sin entregar»."""
        self._ultimo_id = None
        resultado = await self._broker.procesar_uno(NombreCola.CASOS_AYUDA, self._entregar)
        if resultado is ResultadoEntrega.MUERTO and self._ultimo_id:
            await self._publicar_sin_entregar(self._ultimo_id)
        return resultado

    async def _entregar(self, mensaje: Mensaje) -> None:
        self._ultimo_id = mensaje.id
        pedido = PedidoCaso.model_validate(mensaje.cuerpo)
        agencia = self._agencias.get(pedido.agencia)
        if agencia is None:
            raise AgenciaDesconocida(f"no hay un adaptador registrado para {pedido.agencia!r}")
        await agencia.abrir_caso(pedido)

    async def _publicar_sin_entregar(self, id_caso: str) -> None:
        # Misma espera creciente que el Orquestador. Si la cola de novedades sigue llena, el
        # pedido queda en mensajes muertos con aviso a operaciones (limitación de ADR-IT3-002).
        for intento in range(self._cfg.reintentos_publicacion + 1):
            try:
                self._publicar_novedad(id_caso, EstadoCaso.SIN_ENTREGAR)
                return
            except ColaLlena:
                if intento < self._cfg.reintentos_publicacion:
                    await self._dormir(self._cfg.backoff_publicacion_segundos * (2**intento))
        log.error("no se pudo publicar «sin entregar» del caso %s: cola de novedades llena", id_caso)

    # --- aviso de la agencia -> cola de novedades --------------------------------------------
    async def recibir_aviso(self, agencia: str, id_caso: str, clave: str | None) -> str:
        """Aviso liviano: la agencia manda el identificador del caso y la clave compartida; el
        adaptador pregunta el estado con `consultarCaso` y recién entonces publica la novedad.

        `publicado`, `desconocido` (la agencia no conoce el caso) o `ignorado` (estado que no
        informa una agencia). Una clave inválida se rechaza sin consultar ni publicar nada.
        Propaga `ErrorAgencia` (la agencia puede avisar de nuevo) y `ColaLlena` (cola de
        novedades llena: responde indisponibilidad y delega la reentrega en la agencia)."""
        esperada = self._cfg.clave_aviso
        if not esperada or not clave or not hmac.compare_digest(clave, esperada):
            raise ClaveInvalida("clave de aviso inválida")
        adaptador = self._agencias.get(agencia)
        if adaptador is None:
            raise AgenciaDesconocida(agencia)
        estado = await adaptador.consultar_caso(id_caso)
        if estado is None:
            return "desconocido"
        if estado not in INFORMABLES:
            return "ignorado"
        self._publicar_novedad(id_caso, estado)
        return "publicado"

    def _publicar_novedad(self, id_caso: str, estado: EstadoCaso) -> None:
        # El identificador de la novedad se forma con el del caso y el estado: la ingesta descarta
        # las repetidas (ADR-IT3-003).
        self._broker.publicar(NombreCola.NOVEDADES, Mensaje(
            f"caso:{id_caso}:{estado.value}",
            {"origen": "caso", "id_caso": id_caso, "estado": estado.value}))
