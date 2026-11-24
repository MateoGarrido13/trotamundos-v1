"""Contrato `Reserva` (ADR-IT3-005, ADR-IT4-009).

La agrupación del Orquestador trabaja contra esta clase y no conoce los tipos concretos.
Un medio de transporte nuevo es una subclase más, registrada en el Registro de tipos.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator, model_validator


class EstadoReserva(StrEnum):
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"


class Origen(StrEnum):
    """De dónde vino la reserva."""

    MANUAL = "manual"
    CORREO = "correo"
    PROVEEDOR = "proveedor"


class Lugar(BaseModel):
    """`lugar` de `Reserva` (`ADR-IT4-009`): nombre, destino y coordenadas opcionales.

    Las coordenadas van las dos o ninguna. Un texto suelto sigue siendo válido: es el nombre,
    sin destino ni coordenadas (reservas ya guardadas y la carga que solo indica un nombre)."""

    model_config = ConfigDict(frozen=True)

    nombre: str
    destino: str | None = None
    latitud: float | None = None
    longitud: float | None = None

    @model_validator(mode="after")
    def coordenadas_juntas(self) -> "Lugar":
        if (self.latitud is None) != (self.longitud is None):
            raise ValueError("latitud y longitud van juntas")
        if self.latitud is not None and not -90 <= self.latitud <= 90:
            raise ValueError("latitud fuera de rango")
        if self.longitud is not None and not -180 <= self.longitud <= 180:
            raise ValueError("longitud fuera de rango")
        return self

    @property
    def solo_nombre(self) -> bool:
        return self.destino is None and self.latitud is None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.solo_nombre and self.nombre == other
        if isinstance(other, Lugar):
            return (self.nombre, self.destino, self.latitud, self.longitud) == (
                other.nombre, other.destino, other.latitud, other.longitud)
        return NotImplemented

    def __hash__(self) -> int:
        # Si `Lugar("Roma") == "Roma"`, los dos tienen que tener el mismo hash (contrato de `__eq__`).
        if self.solo_nombre:
            return hash(self.nombre)
        return hash((self.nombre, self.destino, self.latitud, self.longitud))

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Lugar):
            return self.nombre < other.nombre
        if isinstance(other, str):
            return self.nombre < other
        return NotImplemented

    def __str__(self) -> str:
        return self.nombre


def interpretar_lugar(valor: Any) -> Lugar | None:
    """Acepta el texto histórico, un objeto o `None`."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, Lugar):
        return valor
    if isinstance(valor, str):
        texto = valor.strip()
        if texto.startswith("{"):
            try:
                return Lugar.model_validate_json(texto)
            except ValueError:
                return Lugar(nombre=texto)
        return Lugar(nombre=texto)
    if isinstance(valor, dict):
        return Lugar.model_validate(valor)
    raise ValueError("lugar inválido")


def lugar_publico(lugar: Lugar | str | None) -> dict | str | None:
    """Lo que ve el cliente. Solo el nombre viaja como texto, para las reservas ya existentes."""
    lugar = lugar if isinstance(lugar, Lugar) else interpretar_lugar(lugar)
    if lugar is None:
        return None
    if lugar.solo_nombre:
        return lugar.nombre
    return {"nombre": lugar.nombre, "destino": lugar.destino,
            "latitud": lugar.latitud, "longitud": lugar.longitud}


def lugar_a_texto(lugar: Lugar | str | None) -> str | None:
    """Columna `lugar` (TEXT). El nombre solo queda como estaba; el resto, en JSON."""
    lugar = lugar if isinstance(lugar, Lugar) else interpretar_lugar(lugar)
    if lugar is None:
        return None
    if lugar.solo_nombre:
        return lugar.nombre
    return lugar.model_dump_json()


def texto_destino(lugar: Lugar | str | None) -> str | None:
    """Destino analítico: el destino del lugar o, si no tiene, el nombre."""
    lugar = lugar if isinstance(lugar, Lugar) else interpretar_lugar(lugar)
    if lugar is None:
        return None
    return lugar.destino or lugar.nombre


class Reserva(BaseModel, ABC):
    """Identificador, viaje, fechas, estado y resumen (SPEC-REF-01); `lugar` (ADR-IT4-009).

    SPEC-REF-04: `origen`, `creado_por` (la cuenta que la creó; las del correo o de un
    proveedor no tienen), `editada_manualmente` (una novedad no la pisa) y `baja_en` (baja
    lógica: la reserva se conserva para el historial)."""

    identificador: str
    viaje_id: str
    inicio: datetime
    fin: datetime
    estado: EstadoReserva = EstadoReserva.CONFIRMADA
    lugar: Lugar | None = None
    origen: Origen = Origen.MANUAL
    creado_por: str | None = None
    editada_manualmente: bool = False
    baja_en: datetime | None = None

    @field_validator("lugar", mode="before")
    @classmethod
    def _lugar(cls, valor: Any) -> Lugar | None:
        return interpretar_lugar(valor)

    @field_serializer("lugar")
    def _serializar_lugar(self, lugar: Lugar | None) -> dict | str | None:
        return lugar_publico(lugar)

    @abstractmethod
    def resumen(self) -> str:
        """Texto corto que el panel muestra para esta reserva."""
