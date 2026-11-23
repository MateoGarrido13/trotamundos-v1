# SPEC: SPEC-REF-06
# ELEMENTO PASO 5: Cola de eventos analíticos (ITERACION_5)
# ADRs: ADR-IT5-001
# DRIVERS: REF-06
"""Evento analítico anonimizado.

Tiene una lista **cerrada** de campos (`extra="forbid"`): no lleva la cuenta, el correo, el
nombre, la descripción libre, el resumen de un diálogo ni credenciales, y tampoco el identificador
de la reserva, del viaje ni del itinerario. Al Proyector no le hace falta saber a qué reserva
pertenece un evento: solo lo cuenta."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

TipoEvento = Literal["alta", "modificacion", "baja", "archivado"]


class EventoAnalitico(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str  # identificador único del evento (aleatorio): el Proyector descarta los repetidos
    tipo: TipoEvento
    tipo_reserva: str | None = None  # `None` en el archivado de un viaje
    destino: str | None = None  # el `lugar` de la reserva
    inicio: datetime | None = None
    fin: datetime | None = None
    origen: str | None = None
    estado: str | None = None
    ocurrido_en: datetime


CAMPOS_PERMITIDOS = frozenset(EventoAnalitico.model_fields)
