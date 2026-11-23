# SPEC: SPEC-REF-03
# ELEMENTO PASO 5: Filtro de remitentes, Servicio de ingesta y Orquestador de viajes (ITERACION_3)
# ADRs: ADR-IT3-008, ADR-IT3-003, ADR-IT3-010
# DRIVERS: REF-03, QA-SEG-03*
"""Fronteras entre los nodos de entrada y el Orquestador para el camino del correo.

En el paso 5 estas conexiones son HTTP/REST interno. En el prototipo son llamadas a método
detrás de estos `Protocol`; `composicion.py` las ensambla. Así `entrada` no importa
`orquestador` ni `persistencia` y el contrato queda igual."""
from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from trotamundos.dominio.reserva_normalizada import ReservaNormalizada


class ResultadoRetencion(StrEnum):
    RETENIDA = "retenida"
    DUPLICADA = "duplicada"  # ya estaba pendiente o descartado: se ignora
    TOPE_ALCANZADO = "tope_alcanzado"  # no se retiene; vuelve en un sondeo posterior


class AlmacenRevision(Protocol):
    """Whitelist y Mensajes en revisión. Los guarda el Orquestador."""

    async def remitente_seguro(self, titular_id: str, remitente: str) -> bool: ...

    async def retener(self, reserva: ReservaNormalizada) -> ResultadoRetencion: ...


class Ingesta(Protocol):
    """Destino del Filtro de remitentes."""

    async def recibir(self, reserva: ReservaNormalizada) -> None: ...


class EntregaOrquestador(Protocol):
    """Lo que la ingesta le entrega al Orquestador: el Orquestador guarda la reserva."""

    async def incorporar(self, reserva: ReservaNormalizada) -> None: ...


class LiberadorDeRevision(Protocol):
    """El Orquestador avisa que un remitente fue aprobado y el filtro libera las reservas."""

    async def liberar(self, reservas: list[ReservaNormalizada]) -> None: ...
