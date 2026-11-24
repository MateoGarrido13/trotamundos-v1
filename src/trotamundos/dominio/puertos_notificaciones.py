# SPEC: SPEC-COMP-08
# ELEMENTO PASO 5: ICanal (ITERACION_3)
# ADRs: ADR-IT3-004
# DRIVERS: QA-INT-02
"""Contrato de los canales de notificación. Los puertos solo dependen del dominio."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ErrorCanal(Exception):
    """El canal no pudo entregar el envío (caída, API sin respuesta)."""


@dataclass(frozen=True)
class Propuesta:
    asunto: str
    cuerpo: str


class ICanal(Protocol):
    """`enviar` es `async` en el prototipo: todo el sistema corre sobre `asyncio` y una espera de red
    no puede bloquear el bucle (PLAN-COMP-08, D1)."""

    nombre: str

    async def enviar(self, destinatario: str, propuesta: Propuesta) -> None: ...
