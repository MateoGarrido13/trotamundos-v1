# SPEC: SPEC-COMP-07
# ELEMENTO PASO 5: Orquestador de viajes, anuncios de Booking (ITERACION_3)
# ADRs: ADR-IT3-003, ADR-IT3-010
# DRIVERS: QA-PER-01
"""Lado del Orquestador de los anuncios de Booking: guarda los que le entrega la ingesta y los lista para
«Novedades». Un anuncio **no modifica reservas** (regla 7): vive en su propia tabla y lo ven todos."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from trotamundos.config import ConfiguracionBooking
from trotamundos.dominio.puertos_anuncios import Anuncio
from trotamundos.persistencia.base_viajes import BaseViajes
from trotamundos.persistencia.repositorio_anuncios import FilaAnuncio, RepositorioAnuncios


def _ahora_utc() -> datetime:
    return datetime.now(UTC)


class ServicioAnuncios:
    def __init__(self, base: BaseViajes, configuracion: ConfiguracionBooking | None = None, *,
                 reloj: Callable[[], datetime] = _ahora_utc) -> None:
        self._base = base
        self._cfg = configuracion or ConfiguracionBooking()
        self._reloj = reloj

    async def guardar_anuncio(self, anuncio: Anuncio) -> bool:
        """Implementa `EntregaAnuncios`. Si la base no está disponible la excepción sube y la ingesta
        reintenta (el Broker); el anuncio repetido es un no-op."""
        recibido = self._reloj()
        return await asyncio.to_thread(
            self._base.escribir, lambda c: RepositorioAnuncios.insertar(c, anuncio, recibido))

    async def recientes(self) -> list[FilaAnuncio]:
        desde = self._reloj() - timedelta(days=self._cfg.retencion_anuncios_dias)
        return await asyncio.to_thread(
            self._base.leer, lambda c: RepositorioAnuncios.recientes(c, desde, self._cfg.tope_listado_anuncios))


def serializar(fila: FilaAnuncio) -> dict:
    return {"id": fila.id, "titulo": fila.titulo, "destino": fila.destino, "inicio": fila.inicio.isoformat(),
            "fin": fila.fin.isoformat(), "proveedor": fila.proveedor,
            "recibido_en": fila.recibido_en.isoformat()}
