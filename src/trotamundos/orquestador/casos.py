# SPEC: SPEC-REF-05
# ELEMENTO PASO 5: Orquestador de viajes, casos de ayuda y agencia preferida (ITERACION_4)
# ADRs: ADR-IT4-010, ADR-IT3-002, ADR-IT3-003, ADR-IT4-007, ADR-IT4-008
# DRIVERS: REF-05, CON-02
"""Casos de ayuda: el Orquestador guarda el caso, lo publica en la cola de casos de ayuda y
muestra «en trámite» sin esperar a la agencia.

Solo conoce los **nombres** de las agencias: los adaptadores viven en los nodos de entrada.
Reportar y reintentar son una sola escritura de `BaseViajes` (permiso, clave de operación,
validación, caso y asiento de auditoría); la publicación en la cola es **después** del commit,
para no dejar pedidos de casos que se revirtieron. Como cada escritura corre en las dos bases,
el identificador del caso y la hora se calculan antes y se pasan adentro.

Tras el commit, la publicación corre en segundo plano con reintentos de espera creciente si la
cola está llena. Si el proceso muere a mitad, el caso queda «en trámite» sin publicarse
(riesgo aceptado, ver PLAN-REF-05)."""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import psycopg

from trotamundos.broker import Broker, ColaLlena, Mensaje, NombreCola
from trotamundos.config import ConfiguracionAgencias
from trotamundos.dominio.agencias import EstadoCaso, PedidoCaso, puede_pasar
from trotamundos.orquestador.control_acceso import Decision, ModuloControlAcceso, Permiso
from trotamundos.persistencia.base_viajes import BaseViajes
from trotamundos.persistencia.repositorio_casos import FilaCaso, RepositorioCasos
from trotamundos.persistencia.repositorio_gestion import RepositorioGestion

log = logging.getLogger(__name__)

MAX_DESCRIPCION = 2000
# Las claves de operación comparten la tabla con REF-04: se prefijan para no chocar con las suyas.
PREFIJO_CLAVE = "caso:"


@dataclass(frozen=True)
class RespuestaCaso:
    estado: str  # "ok" | "denegado" | "rechazado"
    operacion: str  # "elegir_agencia" | "reportar" | "reintentar"
    motivo: str | None = None
    caso: dict | None = None
    repetida: bool = False  # el resultado es el de una operación anterior con la misma clave

    def a_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if k != "repetida"}

    @classmethod
    def repetida_de(cls, guardado: dict) -> RespuestaCaso:
        return cls(**guardado, repetida=True)


def _ahora_utc() -> datetime:
    return datetime.now(UTC)


def dict_caso(fila: FilaCaso) -> dict[str, Any]:
    return {
        "id": fila.id, "estado": fila.estado, "agencia": fila.agencia,
        "itinerario_id": fila.itinerario_id, "reserva_id": fila.reserva_id,
        "descripcion": fila.descripcion, "resumen_dialogo": fila.resumen_dialogo,
        "creado_en": fila.creado_en.isoformat(), "actualizado_en": fila.actualizado_en.isoformat(),
    }


class ServicioCasos:
    def __init__(
        self,
        base: BaseViajes,
        broker: Broker,
        agencias_disponibles: Iterable[str],
        configuracion: ConfiguracionAgencias | None = None,
        acceso: ModuloControlAcceso | None = None,
        *,
        reloj: Callable[[], datetime] = _ahora_utc,
        dormir=asyncio.sleep,
    ) -> None:
        self._base = base
        self._broker = broker
        self._agencias = frozenset(agencias_disponibles)
        self._cfg = configuracion or ConfiguracionAgencias()
        self._acceso = acceso or ModuloControlAcceso()
        self._reloj = reloj
        self._dormir = dormir
        self._tareas: set[asyncio.Task] = set()

    # --- agencia preferida ----------------------------------------------------------
    async def elegir_agencia(self, actor: str, agencia: str, consentimiento: bool) -> RespuestaCaso:
        """`elegirAgenciaPreferida`. El consentimiento es explícito: la reserva afectada y la
        descripción del problema viajarán a ese tercero. Sin él, o con una agencia que no está
        registrada como adaptador, no se guarda nada."""
        if consentimiento is not True:
            return RespuestaCaso("rechazado", "elegir_agencia", "sin_consentimiento")
        if agencia not in self._agencias:
            return RespuestaCaso("rechazado", "elegir_agencia", "agencia_no_registrada")
        ahora = self._reloj()
        await asyncio.to_thread(self._base.escribir, lambda c: RepositorioCasos.guardar_preferencia(
            c, actor, agencia, ahora))
        return RespuestaCaso("ok", "elegir_agencia")

    # --- reportar y reintentar ---------------------------------------------------------
    async def reportar(self, actor: str, itinerario_id: str, clave: str, reserva_id: str,
                       descripcion: str, resumen_dialogo: str | None = None) -> RespuestaCaso:
        """Lo usan el endpoint del viajero y, más adelante, el asistente (SPEC-REF-07)."""
        id_caso, ahora = f"caso-{uuid.uuid4().hex}", self._reloj()
        respuesta = await asyncio.to_thread(self._escribir, lambda c: self._reportar(
            c, actor, itinerario_id, clave, reserva_id, descripcion, resumen_dialogo, id_caso, ahora))
        if respuesta.estado == "ok" and not respuesta.repetida:
            self._programar_publicacion(id_caso)
        return respuesta

    async def reintentar(self, actor: str, itinerario_id: str, caso_id: str, clave: str) -> RespuestaCaso:
        ahora = self._reloj()
        respuesta = await asyncio.to_thread(self._escribir, lambda c: self._reintentar(
            c, actor, itinerario_id, caso_id, clave, ahora))
        if respuesta.estado == "ok" and not respuesta.repetida:
            self._programar_publicacion(caso_id)  # el mismo pedido, con el mismo identificador
        return respuesta

    async def consultar_agencia_preferida(self, actor: str) -> dict[str, str | None]:
        """Nombre y número de contacto de la agencia preferida, o `None` en ambos si el viajero no
        eligió una (no es un error). Lo usa el asistente (SPEC-REF-07) cuando ningún proveedor de
        modelo de IA está disponible. El número se guarda con la agencia en la configuración."""
        agencia = await asyncio.to_thread(
            self._base.leer, lambda c: RepositorioCasos.preferencia(c, actor))
        if agencia is None or agencia not in self._agencias:
            return {"agencia": None, "contacto": None}
        return {"agencia": agencia, "contacto": self._cfg.contactos.get(agencia)}

    async def consultar(self, actor: str) -> list[dict[str, Any]]:
        """Los casos que el viajero reportó, con su estado: es lo que ve en «Novedades»."""
        filas = await asyncio.to_thread(self._base.leer, lambda c: RepositorioCasos.casos_de(c, actor))
        return [dict_caso(f) for f in filas]

    # --- novedades de la agencia (implementa `EntregaNovedadCaso`) -------------------------
    async def aplicar_estado_caso(self, id_caso: str, estado: EstadoCaso) -> str:
        """`aplicado`, `ignorado` (retrocede, repite o el caso ya no admite novedades) o
        `no_existe`. Los estados solo avanzan."""
        ahora = self._reloj()
        return await asyncio.to_thread(
            self._base.escribir, lambda c: self._aplicar_estado(c, id_caso, estado, ahora))

    # --- publicación en la cola de casos de ayuda -------------------------------------------
    async def esperar_publicaciones(self) -> None:
        """Espera las publicaciones en curso (para las pruebas y para un cierre ordenado)."""
        while self._tareas:
            await asyncio.gather(*list(self._tareas))

    def _programar_publicacion(self, id_caso: str) -> None:
        tarea = asyncio.get_running_loop().create_task(self._publicar_con_reintentos(id_caso))
        self._tareas.add(tarea)
        tarea.add_done_callback(self._tareas.discard)

    async def _publicar_con_reintentos(self, id_caso: str) -> None:
        caso = await asyncio.to_thread(self._base.leer, lambda c: RepositorioCasos.caso(c, id_caso))
        if caso is None or caso.estado != EstadoCaso.EN_TRAMITE:
            return
        for intento in range(self._cfg.reintentos_publicacion + 1):
            try:
                self._broker.publicar(NombreCola.CASOS_AYUDA, Mensaje(id_caso, caso.pedido))
                return
            except ColaLlena:
                if intento < self._cfg.reintentos_publicacion:
                    await self._dormir(self._cfg.backoff_publicacion_segundos * (2**intento))
        log.warning("cola de casos llena: el caso %s queda sin entregar", id_caso)
        await self.aplicar_estado_caso(id_caso, EstadoCaso.SIN_ENTREGAR)

    # --- dentro de la transacción -------------------------------------------------------------
    def _reportar(self, c: psycopg.Connection, actor: str, itin: str, clave: str, reserva_id: str,
                  descripcion: str, resumen: str | None, id_caso: str, ahora: datetime) -> RespuestaCaso:
        previo = self._previo(c, "reportar", actor, itin, clave, ahora, reserva_id)
        if isinstance(previo, RespuestaCaso):
            return previo
        agencia = RepositorioCasos.preferencia(c, actor)
        if agencia is None or agencia not in self._agencias:  # sin agencia o sin consentimiento
            return self._rechazar(c, "reportar", actor, itin, clave, ahora, "sin_agencia_o_consentimiento",
                                  reserva_id)
        reserva = RepositorioGestion.reserva(c, reserva_id, bloquear=False)
        if reserva is None or reserva.itinerario_id != itin or reserva.baja_en is not None:
            return self._rechazar(c, "reportar", actor, itin, clave, ahora, "reserva_inexistente", reserva_id)
        descripcion = (descripcion or "").strip() if isinstance(descripcion, str) else ""
        if not descripcion or len(descripcion) > MAX_DESCRIPCION:
            return self._rechazar(c, "reportar", actor, itin, clave, ahora, "descripcion_invalida", reserva_id)
        pedido = PedidoCaso(
            id_caso=id_caso, agencia=agencia, descripcion=descripcion, resumen_dialogo=resumen,
            reserva={"identificador": reserva.identificador, "tipo": reserva.tipo, "lugar": reserva.lugar,
                     "inicio": reserva.inicio.isoformat(), "fin": reserva.fin.isoformat()},
        ).model_dump(mode="json")
        fila = FilaCaso(id_caso, actor, itin, reserva_id, agencia, descripcion, resumen, pedido,
                        EstadoCaso.EN_TRAMITE.value, ahora, ahora)
        RepositorioCasos.insertar_caso(c, fila)
        return self._confirmar(c, "reportar", actor, itin, clave, ahora, reserva_id, dict_caso(fila))

    def _reintentar(self, c: psycopg.Connection, actor: str, itin: str, caso_id: str, clave: str,
                    ahora: datetime) -> RespuestaCaso:
        previo = self._previo(c, "reintentar", actor, itin, clave, ahora, None)
        if isinstance(previo, RespuestaCaso):
            return previo
        fila = RepositorioCasos.caso(c, caso_id, bloquear=True)
        # Solo quien reportó el caso lo reintenta; uno ajeno es indistinguible de uno inexistente.
        if fila is None or fila.itinerario_id != itin or fila.cuenta_id != actor:
            return self._rechazar(c, "reintentar", actor, itin, clave, ahora, "caso_inexistente", None)
        if fila.estado != EstadoCaso.SIN_ENTREGAR:
            return self._rechazar(c, "reintentar", actor, itin, clave, ahora, "estado_invalido", fila.reserva_id)
        RepositorioCasos.actualizar_estado(c, caso_id, EstadoCaso.EN_TRAMITE.value, ahora)
        nuevo = RepositorioCasos.caso(c, caso_id)
        return self._confirmar(c, "reintentar", actor, itin, clave, ahora, fila.reserva_id, dict_caso(nuevo))

    def _aplicar_estado(self, c: psycopg.Connection, id_caso: str, estado: EstadoCaso, ahora: datetime) -> str:
        fila = RepositorioCasos.caso(c, id_caso, bloquear=True)
        if fila is None:
            return "no_existe"
        if not puede_pasar(EstadoCaso(fila.estado), estado):
            return "ignorado"
        RepositorioCasos.actualizar_estado(c, id_caso, estado.value, ahora)
        return "aplicado"

    # --- piezas comunes ---------------------------------------------------------------------------
    def _previo(self, c, operacion, actor, itin, clave, ahora, reserva_id):
        """Permiso `registrar` y clave de operación. Devuelve una respuesta si ya se resolvió
        (denegado o repetida), o `None` si hay que seguir."""
        if self._acceso.verificar_permiso(c, actor, itin, Permiso.REGISTRAR) is Decision.DENEGADO:
            self._auditar(c, operacion, actor, itin, "denegado", ahora, reserva_id, clave)
            return RespuestaCaso("denegado", operacion)
        guardado = RepositorioGestion.clave(c, actor, PREFIJO_CLAVE + clave)
        if guardado is not None:
            return RespuestaCaso.repetida_de(guardado)
        return None

    def _rechazar(self, c, operacion, actor, itin, clave, ahora, motivo, reserva_id):
        self._auditar(c, operacion, actor, itin, "rechazado", ahora, reserva_id, clave, motivo)
        return RespuestaCaso("rechazado", operacion, motivo)

    def _confirmar(self, c, operacion, actor, itin, clave, ahora, reserva_id, caso):
        self._auditar(c, operacion, actor, itin, "permitido", ahora, reserva_id, clave)
        respuesta = RespuestaCaso("ok", operacion, caso=caso)
        RepositorioGestion.guardar_clave(c, actor, PREFIJO_CLAVE + clave, respuesta.a_dict(), ahora)
        return respuesta

    @staticmethod
    def _auditar(c, operacion, actor, itin, resultado, ahora, reserva_id, clave, motivo=None):
        RepositorioGestion.auditar(
            c, cuenta_id=actor, itinerario_id=itin, operacion=f"{operacion}_caso", permiso=Permiso.REGISTRAR,
            resultado=resultado, ahora=ahora, reserva_id=reserva_id, clave=clave, motivo=motivo)

    def _escribir(self, operacion):
        try:
            return self._base.escribir(operacion)
        except psycopg.errors.UniqueViolation:
            # Dos pedidos con la misma clave chocaron: el segundo ya encuentra el resultado.
            return self._base.escribir(operacion)
