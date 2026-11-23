# SPEC: SPEC-REF-03
# ELEMENTO PASO 5: Orquestador de viajes, whitelist y Mensajes en revisión (ITERACION_3)
# ADRs: ADR-IT3-008, ADR-IT3-003
# DRIVERS: REF-03, QA-SEG-03*
"""Servicio del Orquestador para la whitelist y Mensajes en revisión.

Implementa `AlmacenRevision` (lo que consulta el Filtro de remitentes) y las operaciones del
titular: consultar, aprobar o dar de alta, quitar y descartar. El acceso a la base es síncrono
y se ejecuta fuera del lazo de eventos."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from trotamundos.config import ConfiguracionRevision
from trotamundos.dominio.puertos_correo import LiberadorDeRevision, ResultadoRetencion
from trotamundos.dominio.reserva_normalizada import ReservaNormalizada
from trotamundos.persistencia.repositorio_revision import MensajePendiente, RepositorioRevision

log = logging.getLogger(__name__)


class ErrorMensajeNoEncontrado(Exception):
    """El mensaje no existe, ya está resuelto o es de otro titular."""


def _ahora_utc() -> datetime:
    return datetime.now(UTC)


class ServicioRevision:
    def __init__(
        self,
        repositorio: RepositorioRevision,
        configuracion: ConfiguracionRevision | None = None,
        *,
        liberador: LiberadorDeRevision | None = None,
        reloj: Callable[[], datetime] = _ahora_utc,
    ) -> None:
        self._repo = repositorio
        self._cfg = configuracion or ConfiguracionRevision()
        self.liberador = liberador  # lo conecta `composicion.py`: el filtro libera hacia la ingesta
        self._reloj = reloj

    # --- AlmacenRevision (lo usa el Filtro de remitentes) -----------------------
    async def remitente_seguro(self, titular_id: str, remitente: str) -> bool:
        return await asyncio.to_thread(self._repo.es_seguro, titular_id, remitente)

    async def retener(self, reserva: ReservaNormalizada) -> ResultadoRetencion:
        return await asyncio.to_thread(self._repo.retener, reserva, self._reloj())

    # --- operaciones del titular -------------------------------------------------
    async def consultar(self, titular_id: str) -> list[MensajePendiente]:
        return await asyncio.to_thread(self._repo.pendientes, titular_id)

    async def aprobar(self, titular_id: str, remitente: str) -> int:
        """Agrega el remitente a la whitelist y libera sus mensajes pendientes hacia la
        ingesta. Sirve para aprobar desde un mensaje en revisión o dar de alta un remitente.
        Si el remitente ya estaba aprobado, también libera lo que hubiera quedado pendiente.
        Devuelve la cantidad de mensajes liberados.

        Los pendientes se borran recién después de liberarlos: si la liberación falla no se
        pierde nada y aprobar de nuevo la reintenta (la ingesta descarta el duplicado)."""
        await asyncio.to_thread(self._repo.agregar_remitente, titular_id, remitente)
        pendientes = await asyncio.to_thread(self._repo.pendientes_de, titular_id, remitente)
        if pendientes:
            if self.liberador is None:
                raise RuntimeError("No hay liberador conectado para soltar las reservas retenidas")
            await self.liberador.liberar([m.reserva for m in pendientes])
            await asyncio.to_thread(self._repo.borrar, titular_id, [m.id_mensaje for m in pendientes])
        return len(pendientes)

    async def quitar(self, titular_id: str, remitente: str) -> None:
        """Solo cambia el destino de los mensajes siguientes: no toca reservas incorporadas."""
        await asyncio.to_thread(self._repo.quitar_remitente, titular_id, remitente)

    async def descartar(self, titular_id: str, id_mensaje: str) -> None:
        if not await asyncio.to_thread(self._repo.descartar, titular_id, id_mensaje):
            raise ErrorMensajeNoEncontrado(
                f"No hay un mensaje pendiente {id_mensaje!r} para el titular")

    # --- retención ---------------------------------------------------------------
    async def purgar(self, ahora: datetime | None = None) -> int:
        limite = (ahora or self._reloj()) - timedelta(days=self._cfg.retencion_dias)
        return await asyncio.to_thread(self._repo.purgar, limite)


async def tarea_purga(servicio: ServicioRevision, intervalo_segundos: float) -> None:
    """Proceso periódico que elimina los mensajes que cumplieron la retención."""
    while True:
        try:
            await servicio.purgar()
        except Exception:  # una base caída no mata el proceso periódico
            log.exception("falló la purga periódica de Mensajes en revisión")
        await asyncio.sleep(intervalo_segundos)
