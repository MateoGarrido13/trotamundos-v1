# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Adaptador de correo, API de correo externa (ITERACION_3)
# ADRs: ADR-IT3-003, ADR-IT3-006
# DRIVERS: CON-02, REF-02
"""API de correo (externa): Protocol y mock (CON-02). El mock es la simplificación de la spec:
buzones por titular, demora y caída inyectables, y rechazo de tokens inválidos."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class ErrorApiCorreo(Exception):
    """La API de correo no responde o falló."""


class TokenInvalido(ErrorApiCorreo):
    """La API de correo rechazó el token."""


@dataclass(frozen=True)
class CorreoCrudo:
    cuerpo: str
    remitente: str
    recibido: datetime
    message_id: str | None = None


class ApiCorreo(Protocol):
    async def leer_mensajes(self, token: str, desde: datetime) -> list[CorreoCrudo]: ...


class MockApiCorreo:
    def __init__(self, *, dormir: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self._dormir = dormir
        self._tokens: dict[str, str] = {}  # token -> titular
        self._buzones: dict[str, list[CorreoCrudo]] = {}
        self.caida = False
        self.demora_segundos = 0.0
        self.lecturas = 0  # lecturas que llegaron a la API (con o sin éxito)

    def emitir_token(self, titular_id: str, token: str) -> None:
        self._tokens[token] = titular_id

    def agregar_correo(self, titular_id: str, correo: CorreoCrudo) -> None:
        self._buzones.setdefault(titular_id, []).append(correo)

    async def leer_mensajes(self, token: str, desde: datetime) -> list[CorreoCrudo]:
        self.lecturas += 1
        if self.demora_segundos:
            await self._dormir(self.demora_segundos)
        if self.caida:
            raise ErrorApiCorreo("la API de correo no responde")
        titular = self._tokens.get(token)
        if titular is None:
            raise TokenInvalido("token rechazado por la API de correo")
        return [c for c in self._buzones.get(titular, []) if c.recibido >= desde]
