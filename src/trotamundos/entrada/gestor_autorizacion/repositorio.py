# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Gestor de autorización del correo (ITERACION_3)
# ADRs: ADR-IT3-006
# DRIVERS: QA-SEG-03*, REF-02
"""Almacén de tokens cifrados. `RepositorioTokens` es un Protocol; esta es la versión en
memoria (tests y desarrollo). La de PostgreSQL entra en T-REF-02-09."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class TokenGuardado:
    titular_id: str
    token_cifrado: bytes
    vence: datetime


class RepositorioTokens(Protocol):
    def guardar(self, token: TokenGuardado) -> None: ...

    def obtener(self, titular_id: str) -> TokenGuardado | None: ...

    def borrar(self, titular_id: str) -> None: ...

    def titulares(self) -> list[str]: ...


class RepositorioTokensEnMemoria:
    def __init__(self) -> None:
        self._tokens: dict[str, TokenGuardado] = {}

    def guardar(self, token: TokenGuardado) -> None:
        self._tokens[token.titular_id] = token

    def obtener(self, titular_id: str) -> TokenGuardado | None:
        return self._tokens.get(titular_id)

    def borrar(self, titular_id: str) -> None:
        self._tokens.pop(titular_id, None)

    def titulares(self) -> list[str]:
        return list(self._tokens)
