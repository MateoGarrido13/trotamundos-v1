# SPEC: SPEC-REF-01
# ELEMENTO PASO 5: Orquestador de viajes, archivado automático por fecha (ITERACION_1)
# ADRs: ADR-IT2-004
# DRIVERS: REF-01, QA-DIS-01
"""Archivado de viajes completados. La escritura pasa por el commit en dos fases."""
from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable
from datetime import datetime
from typing import Protocol

log = logging.getLogger(__name__)

# La spec pide un proceso periódico sin fijar la frecuencia: parámetro de este plan.
INTERVALO_POR_DEFECTO = float(os.environ.get("TROTA_INTERVALO_ARCHIVADO", "3600"))


class FuenteArchivado(Protocol):
    def viajes_completos(self, ahora: datetime) -> list[str]: ...
    def archivar(self, viaje_ids: list[str], ahora: datetime) -> None: ...


def archivar_completados(repositorio: FuenteArchivado, ahora: datetime) -> list[str]:
    """Archiva los viajes cuya última reserva ya terminó. Devuelve los ids archivados."""
    ids = repositorio.viajes_completos(ahora)
    repositorio.archivar(ids, ahora)
    return ids


async def tarea_periodica(repositorio: FuenteArchivado,
                          intervalo_segundos: float = INTERVALO_POR_DEFECTO,
                          reloj: Callable[[], datetime] = datetime.now) -> None:
    while True:
        try:
            await asyncio.to_thread(archivar_completados, repositorio, reloj())
        except Exception:  # una base caída no mata el proceso periódico
            log.exception("falló el archivado periódico")
        await asyncio.sleep(intervalo_segundos)
