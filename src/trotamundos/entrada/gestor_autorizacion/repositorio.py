# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Gestor de autorización del correo (ITERACION_3)
# ADRs: ADR-IT3-006
# DRIVERS: QA-SEG-03*, REF-02
"""Almacén de tokens cifrados. `RepositorioTokens` es un Protocol con dos versiones: en memoria
(tests y desarrollo) y PostgreSQL sobre la Base primaria de viajes (T-REF-02-09)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from trotamundos.persistencia.base_viajes import BaseViajes


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


class RepositorioTokensPostgres:
    """Tokens cifrados en la tabla `token_correo`. Escribe por `BaseViajes`, así que cada alta
    o baja pasa por el commit en dos fases y queda en la primaria y en la pasiva."""

    def __init__(self, base: BaseViajes) -> None:
        self._base = base

    def guardar(self, token: TokenGuardado) -> None:
        self._base.escribir(lambda c: c.execute(
            "INSERT INTO token_correo (titular_id, token_cifrado, vence) VALUES (%s, %s, %s)"
            " ON CONFLICT (titular_id) DO UPDATE"
            " SET token_cifrado = EXCLUDED.token_cifrado, vence = EXCLUDED.vence",
            (token.titular_id, token.token_cifrado, token.vence)))

    def obtener(self, titular_id: str) -> TokenGuardado | None:
        fila = self._base.leer(lambda c: c.execute(
            "SELECT titular_id, token_cifrado, vence FROM token_correo WHERE titular_id = %s",
            (titular_id,)).fetchone())
        return None if fila is None else TokenGuardado(fila[0], bytes(fila[1]), fila[2])

    def borrar(self, titular_id: str) -> None:
        self._base.escribir(lambda c: c.execute(
            "DELETE FROM token_correo WHERE titular_id = %s", (titular_id,)))

    def titulares(self) -> list[str]:
        return [f[0] for f in self._base.leer(lambda c: c.execute(
            "SELECT titular_id FROM token_correo ORDER BY titular_id").fetchall())]
