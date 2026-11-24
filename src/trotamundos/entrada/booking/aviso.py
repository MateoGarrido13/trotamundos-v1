# SPEC: SPEC-COMP-07
# ELEMENTO PASO 5: Adaptador de anuncios (Booking), capa anti-corrupción (ITERACION_3)
# ADRs: ADR-007, ADR-IT3-009, ADR-IT3-003
# DRIVERS: QA-PER-01, QA-INT-01
"""El aviso de Booking y su traducción al modelo interno. Un aviso es un **anuncio de viaje nuevo**
(título, destino, fechas y proveedor): no modifica ninguna reserva (regla 7). No depende de nadie."""
from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

PREFIJO = "booking"


class AvisoInvalido(ValueError):
    """El aviso no se puede traducir al modelo interno (422)."""


class AvisoBooking(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    aviso_id: str = Field(min_length=1, max_length=100)
    titulo: str = Field(min_length=1, max_length=200)
    destino: str = Field(min_length=1, max_length=200)
    inicio: date
    fin: date
    proveedor: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _fechas_en_orden(self) -> AvisoBooking:
        if self.fin < self.inicio:
            raise ValueError("el viaje no puede terminar antes de empezar")
        return self


def traducir_aviso(cuerpo: Any) -> dict[str, str]:
    """Del aviso de Booking a la novedad interna. El identificador lo asigna el listener a partir de la
    identidad del aviso (`ADR-IT3-003`): un aviso repetido tiene el mismo y se descarta en la ingesta."""
    if not isinstance(cuerpo, dict):
        raise AvisoInvalido("el aviso debe ser un objeto JSON")
    try:
        aviso = AvisoBooking.model_validate(cuerpo)
    except ValidationError as error:
        raise AvisoInvalido("aviso mal formado: " + ", ".join(
            ".".join(str(p) for p in e["loc"]) or "cuerpo" for e in error.errors())) from None
    return {"id": f"{PREFIJO}:{aviso.aviso_id}", "titulo": aviso.titulo, "destino": aviso.destino,
            "inicio": aviso.inicio.isoformat(), "fin": aviso.fin.isoformat(), "proveedor": aviso.proveedor}
