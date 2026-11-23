# SPEC: SPEC-REF-03
# ELEMENTO PASO 5: Servicio de ingesta (ITERACION_3)
# ADRs: ADR-IT3-003, ADR-IT3-010
# DRIVERS: REF-03, QA-SEG-03*
"""Servicio de ingesta.

Toma de la cola `novedades` del Broker dos clases de mensaje, que distingue por `origen`:
las reservas del correo que le entrega el Filtro de remitentes (SPEC-REF-03) y los cambios de
estado de un caso de ayuda que publica el Adaptador de agencia (SPEC-REF-05). Descarta los
duplicados por identificador, entrega al Orquestador con un límite de tasa y reintenta si la
entrega falla. Agotados los reintentos, el Broker manda el mensaje a la cola de mensajes
muertos con aviso a operaciones. La ingesta nunca escribe en la base: entrega al Orquestador."""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from trotamundos.broker import Broker, Mensaje, NombreCola, ResultadoEntrega
from trotamundos.config import ConfiguracionIngesta
from trotamundos.dominio.agencias import EstadoCaso
from trotamundos.dominio.puertos_casos import EntregaNovedadCaso
from trotamundos.dominio.puertos_correo import EntregaOrquestador
from trotamundos.dominio.reserva_normalizada import ReservaNormalizada


class LimitadorTasa:
    """Espacia las entregas para no superar `por_segundo`. Reloj y espera inyectables."""

    def __init__(
        self,
        por_segundo: float,
        *,
        reloj: Callable[[], float] = time.monotonic,
        dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._intervalo = 1.0 / por_segundo
        self._reloj = reloj
        self._dormir = dormir
        self._proximo = 0.0

    async def esperar(self) -> None:
        ahora = self._reloj()
        turno = max(ahora, self._proximo)
        self._proximo = turno + self._intervalo
        if turno > ahora:
            await self._dormir(turno - ahora)


def _ahora_utc() -> datetime:
    return datetime.now(UTC)


class ServicioIngesta:
    def __init__(
        self,
        broker: Broker,
        entrega: EntregaOrquestador,
        configuracion: ConfiguracionIngesta | None = None,
        *,
        entrega_casos: EntregaNovedadCaso | None = None,
        limitador: LimitadorTasa | None = None,
        reloj: Callable[[], datetime] = _ahora_utc,
    ) -> None:
        cfg = configuracion or ConfiguracionIngesta()
        self._broker = broker
        self._entrega = entrega
        self._entrega_casos = entrega_casos
        self._retencion = timedelta(days=cfg.retencion_ids_dias)
        self._limitador = limitador or LimitadorTasa(cfg.tasa_por_segundo)
        self._reloj = reloj
        self._procesados: dict[str, datetime] = {}

    # --- lado del Filtro de remitentes (implementa `Ingesta`) -------------------
    async def recibir(self, reserva: ReservaNormalizada) -> None:
        """Deja la reserva en la cola. Con la cola llena lanza `ColaLlena`: el mensaje del
        correo falla, el Broker lo reintenta y no se pierde."""
        self._broker.publicar(
            NombreCola.NOVEDADES,
            Mensaje(self._clave(reserva), {"origen": "correo", "reserva": reserva.model_dump(mode="json")}),
        )

    # --- lado del consumidor ------------------------------------------------------
    async def procesar_uno(self) -> ResultadoEntrega:
        return await self._broker.procesar_uno(NombreCola.NOVEDADES, self._manejar)

    async def _manejar(self, mensaje: Mensaje) -> None:
        if self._ya_procesado(mensaje.id):
            return  # duplicado: se descarta
        origen = mensaje.cuerpo.get("origen")
        if origen == "correo":
            reserva = ReservaNormalizada.model_validate(mensaje.cuerpo["reserva"])
            await self._limitador.esperar()
            await self._entrega.incorporar(reserva)
        elif origen == "caso":
            if self._entrega_casos is None:
                raise RuntimeError("la ingesta no tiene a quién entregarle los cambios de estado de casos")
            await self._limitador.esperar()
            await self._entrega_casos.aplicar_estado_caso(
                mensaje.cuerpo["id_caso"], EstadoCaso(mensaje.cuerpo["estado"]))
        else:
            raise ValueError(f"origen de novedad desconocido: {origen!r}")
        # Se marca como procesado recién después de entregar: si se marcara antes, el reintento
        # tras un fallo se descartaría y la reserva se perdería.
        self._procesados[mensaje.id] = self._reloj()

    # --- internos ------------------------------------------------------------------
    @staticmethod
    def _clave(reserva: ReservaNormalizada) -> str:
        return reserva.identificador_reserva  # incluye al titular: un correo puede ir a dos

    def _ya_procesado(self, clave: str) -> bool:
        limite = self._reloj() - self._retencion
        for k in [k for k, t in self._procesados.items() if t < limite]:
            del self._procesados[k]  # cumplió la retención
        return clave in self._procesados
