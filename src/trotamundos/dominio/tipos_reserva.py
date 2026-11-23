# SPEC: SPEC-REF-01
# ELEMENTO PASO 5: Reserva y Registro de tipos (ITERACION_3)
# ADRs: ADR-IT3-005
# DRIVERS: QA-EVO-01, REF-01
"""Tipos concretos de reserva: hotel, auto, vuelo, tren y autobús.

La spec solo fija los campos comunes de `Reserva`. El único campo propio es `codigo` (el
código de reserva que trae el correo, SPEC-REF-03), que viaja en la columna `datos`.
Un medio nuevo es una clase más que extiende `Reserva` y se registra al arrancar.
"""
from __future__ import annotations

from typing import ClassVar

from trotamundos.dominio.reserva import Reserva


class _ReservaConEtiqueta(Reserva):
    etiqueta: ClassVar[str] = "Reserva"
    codigo: str | None = None

    def resumen(self) -> str:
        destino = f" en {self.lugar}" if self.lugar else ""
        return f"{self.etiqueta}{destino} ({self.identificador})"


class ReservaHotel(_ReservaConEtiqueta):
    etiqueta: ClassVar[str] = "Hotel"


class ReservaAuto(_ReservaConEtiqueta):
    etiqueta: ClassVar[str] = "Auto"


class ReservaVuelo(_ReservaConEtiqueta):
    etiqueta: ClassVar[str] = "Vuelo"


class ReservaTren(_ReservaConEtiqueta):
    etiqueta: ClassVar[str] = "Tren"


class ReservaAutobus(_ReservaConEtiqueta):
    etiqueta: ClassVar[str] = "Autobús"


class ReservaActividad(_ReservaConEtiqueta):
    """Actividad que un miembro registra en un itinerario (SPEC-REF-04, ADR-IT4-008)."""

    etiqueta: ClassVar[str] = "Actividad"


TIPOS_BASE: dict[str, type[Reserva]] = {
    "hotel": ReservaHotel,
    "auto": ReservaAuto,
    "vuelo": ReservaVuelo,
    "tren": ReservaTren,
    "autobus": ReservaAutobus,
    "actividad": ReservaActividad,
}
