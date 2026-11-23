# SPEC: SPEC-REF-07
# ELEMENTO PASO 5: IMotorConversacional, intención tipada (RONDA_2/ITERACION_1)
# ADRs: ADR-IT6-004, ADR-IT7-001
# DRIVERS: REF-07, QA-SEG-04
"""Intención tipada de un conjunto cerrado. Cualquier otra respuesta del motor se trata como
`fueraDeAlcance`: el asistente nunca ejecuta algo que no esté en esta lista."""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError


class TipoIntencion(StrEnum):
    CONSULTAR_ESTADO = "consultarEstado"
    AGREGAR_RESERVA = "agregarReserva"
    REPROGRAMAR = "reprogramar"
    ELIMINAR_RESERVA = "eliminarReserva"
    CASO_COMPLEJO = "casoComplejo"
    FUERA_DE_ALCANCE = "fueraDeAlcance"


class Intencion(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tipo: TipoIntencion
    referencia: str | None = None  # identificador de la reserva o un texto que la nombra (lugar, tipo)
    cambios: dict[str, Any] = {}  # reprogramar: los campos a cambiar
    datos: dict[str, Any] = {}  # agregarReserva: tipo, lugar, fechas, viaje
    motivo: str | None = None  # casoComplejo: lo que el viajero cuenta


FUERA_DE_ALCANCE = Intencion(tipo=TipoIntencion.FUERA_DE_ALCANCE)


def normalizar(crudo: Any) -> Intencion:
    """La intención que devolvió el motor, o `fueraDeAlcance` si no pertenece al conjunto cerrado
    (un tipo desconocido, un texto suelto, `None`, un valor mal formado)."""
    if isinstance(crudo, Intencion):
        return crudo
    if isinstance(crudo, dict):
        try:
            return Intencion.model_validate(crudo)
        except ValidationError:
            pass
    return FUERA_DE_ALCANCE
