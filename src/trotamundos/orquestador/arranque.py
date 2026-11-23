# SPEC: SPEC-REF-01
# ELEMENTO PASO 5: Registro de tipos por configuration-time binding (ITERACION_3)
# ADRs: ADR-IT3-005
# DRIVERS: QA-EVO-01, REF-01
"""Registro de tipos de reserva al arrancar. Un tipo duplicado o una clase que no
extiende `Reserva` hace fallar el arranque con `ErrorRegistroTipos` (AC-REF-01-08)."""
from __future__ import annotations

from collections.abc import Mapping

from trotamundos.dominio.registro_tipos import RegistroTipos
from trotamundos.dominio.tipos_reserva import TIPOS_BASE


def registrar_tipos(registro: RegistroTipos, tipos_extra: Mapping[str, type] | None = None) -> None:
    for nombre, clase in TIPOS_BASE.items():
        registro.registrar(nombre, clase)
    for nombre, clase in (tipos_extra or {}).items():
        registro.registrar(nombre, clase)
