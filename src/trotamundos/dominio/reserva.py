"""Contrato `Reserva` (ADR-IT3-005, ADR-IT4-009).

La agrupación del Orquestador trabaja contra esta clase y no conoce los tipos concretos.
Un medio de transporte nuevo es una subclase más, registrada en el Registro de tipos.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class EstadoReserva(StrEnum):
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"


class Reserva(BaseModel, ABC):
    """Identificador, viaje, fechas, estado y resumen (SPEC-REF-01); `lugar` (ADR-IT4-009)."""

    identificador: str
    viaje_id: str
    inicio: datetime
    fin: datetime
    estado: EstadoReserva = EstadoReserva.CONFIRMADA
    lugar: str | None = None

    @abstractmethod
    def resumen(self) -> str:
        """Texto corto que el panel muestra para esta reserva."""
