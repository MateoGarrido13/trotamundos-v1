# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Parseo aislado (ITERACION_3)
# ADRs: ADR-IT3-007
# DRIVERS: QA-SEG-03*, REF-02
"""Esquema estructurado de reserva de viaje (tipo, fechas, lugar y código). Solo pydantic y stdlib.

Valores de prototipo (PLAN-REF-02): tope de 64 KB para el cuerpo, campos de texto acotados
y sin caracteres de control."""
from __future__ import annotations

import json
import unicodedata
from datetime import datetime

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

TOPE_CUERPO_BYTES = 64 * 1024
TOPE_CAMPO = 200


def _sin_control(valor: str) -> str:
    if any(unicodedata.category(c) == "Cc" for c in valor):
        raise ValueError("caracteres de control")
    return valor


class CuerpoReserva(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    tipo: str
    inicio: datetime
    fin: datetime
    lugar: str
    codigo: str

    @field_validator("tipo", "lugar", "codigo")
    @classmethod
    def _texto(cls, v: str) -> str:
        if not v.strip() or len(v) > TOPE_CAMPO:
            raise ValueError("texto vacío o demasiado largo")
        return _sin_control(v)

    @model_validator(mode="after")
    def _fechas(self) -> "CuerpoReserva":
        if self.fin < self.inicio:
            raise ValueError("fin anterior a inicio")
        return self


class MensajeEntrada(BaseModel):
    """Lo que recibe el Parseo. Nunca incluye el token."""

    model_config = ConfigDict(extra="forbid")

    id: str
    titular_id: str
    remitente: str
    cuerpo: str


def validar(entrada: dict) -> dict | None:
    """Devuelve la reserva normalizada como dict JSON-able, o `None` si se descarta."""
    try:
        msg = MensajeEntrada.model_validate(entrada)
        if len(msg.cuerpo.encode()) > TOPE_CUERPO_BYTES:
            return None
        for v in (msg.id, msg.titular_id, msg.remitente):
            if len(v) > TOPE_CAMPO:
                return None
            _sin_control(v)
        cuerpo = CuerpoReserva.model_validate(json.loads(msg.cuerpo))
    except (ValidationError, ValueError, TypeError, RecursionError):
        return None
    return {
        "id_mensaje": msg.id,
        "titular_id": msg.titular_id,
        "remitente": msg.remitente,
        **cuerpo.model_dump(mode="json"),
    }
