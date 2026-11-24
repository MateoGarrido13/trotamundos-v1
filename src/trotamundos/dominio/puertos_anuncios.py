# SPEC: SPEC-COMP-07
# ELEMENTO PASO 5: Servicio de ingesta -> Orquestador de viajes, anuncios (ITERACION_3)
# ADRs: ADR-IT3-010
# DRIVERS: QA-PER-01
"""Frontera entre la ingesta y el Orquestador para los anuncios de Booking. Los puertos solo
dependen del dominio: `entrada` no importa `orquestador` ni `persistencia`."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class Anuncio:
    id: str  # booking:<aviso_id>
    titulo: str
    destino: str
    inicio: date
    fin: date
    proveedor: str
    detectado_en: datetime  # cuando el listener lo detectó: de ahí corre la medida de QA-PER-01


class EntregaAnuncios(Protocol):
    """Lo que la ingesta le entrega al Orquestador: el Orquestador guarda el anuncio."""

    async def guardar_anuncio(self, anuncio: Anuncio) -> bool:
        """`True` si era nuevo, `False` si ya estaba (una entrega repetida)."""
        ...
