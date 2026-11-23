"""Frontera entre SPEC-REF-02 y SPEC-REF-03.

SPEC-REF-02 llega hasta aquí: el Parseo aislado entrega la reserva normalizada, con su
identificador, al Filtro de remitentes. La whitelist y Mensajes en revisión son de
SPEC-REF-03, que implementa este `Protocol`.
"""
from __future__ import annotations

from typing import Protocol

from trotamundos.dominio.reserva_normalizada import ReservaNormalizada


class FiltroRemitentes(Protocol):
    async def recibir(self, reserva: ReservaNormalizada) -> None: ...


class FiltroRemitentesNulo:
    """Implementación provisoria hasta SPEC-REF-03: acumula lo recibido, sin filtrar."""

    def __init__(self) -> None:
        self.recibidas: list[ReservaNormalizada] = []

    async def recibir(self, reserva: ReservaNormalizada) -> None:
        self.recibidas.append(reserva)
