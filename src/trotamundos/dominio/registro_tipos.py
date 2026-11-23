"""Registro de tipos de `Reserva` por configuration-time binding (ADR-IT3-005).

Se llena al arrancar. Un tipo duplicado, o una clase que no extiende `Reserva`,
impide el arranque con un error que explica la causa (AC-REF-01-08).
"""
from __future__ import annotations

from trotamundos.dominio.reserva import Reserva


class ErrorRegistroTipos(Exception):
    """El registro rechaza el arranque."""


class RegistroTipos:
    def __init__(self) -> None:
        self._tipos: dict[str, type[Reserva]] = {}

    def registrar(self, tipo: str, clase: type) -> None:
        if not (isinstance(clase, type) and issubclass(clase, Reserva)):
            raise ErrorRegistroTipos(
                f"No se puede registrar el tipo {tipo!r}: {clase!r} no extiende Reserva"
            )
        if tipo in self._tipos:
            raise ErrorRegistroTipos(
                f"No se puede registrar el tipo {tipo!r}: ya está registrado "
                f"como {self._tipos[tipo].__name__}"
            )
        self._tipos[tipo] = clase

    def clase_de(self, tipo: str) -> type[Reserva]:
        try:
            return self._tipos[tipo]
        except KeyError:
            raise ErrorRegistroTipos(f"Tipo de reserva desconocido: {tipo!r}") from None

    def tipos(self) -> dict[str, type[Reserva]]:
        return dict(self._tipos)
