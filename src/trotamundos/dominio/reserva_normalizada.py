"""Reserva normalizada que sale del Parseo aislado hacia el Filtro de remitentes.

Esquema estructurado simple (SPEC-REF-02, Simplificaciones): tipo, fechas, lugar y código.
El identificador del mensaje (ADR-IT3-003) viaja intacto hasta la ingesta.

DECISIÓN DE IMPLEMENTACIÓN: `remitente` y `titular_id` no están en el esquema de la
spec, pero el Filtro necesita el remitente para la whitelist y la ingesta necesita saber
a qué itinerario va la reserva. Conviene reflejarlo en SPEC-REF-02/03 cuando se revisen.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReservaNormalizada(BaseModel):
    id_mensaje: str
    titular_id: str
    remitente: str
    tipo: str
    inicio: datetime
    fin: datetime
    lugar: str
    codigo: str
