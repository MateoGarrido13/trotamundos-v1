# SPEC: SPEC-COMP-05
# ELEMENTO PASO 5: Cuentas, alta y autenticación (ITERACION_4)
# ADRs: ADR-IT4-001, ADR-IT4-004
# DRIVERS: QA-ESC-01
"""Contrato de las cuentas: `IRegistroUsuario`, la sesión y los errores. Solo depende del dominio."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Sesion:
    cuenta_id: str
    token_acceso: str
    token_renovacion: str


class ErrorIdentidad(Exception):
    """Base de los errores de identidad."""


class DatosInvalidos(ErrorIdentidad):
    """Correo o contraseña con forma inválida (422)."""


class CorreoYaRegistrado(ErrorIdentidad):
    """El correo ya tiene una cuenta, en esta región o en otra (409)."""


class CredencialInvalida(ErrorIdentidad):
    """Correo o contraseña incorrectos (401)."""


class TokenInvalido(ErrorIdentidad):
    """Token de acceso o de renovación inválido, vencido o revocado (401)."""


class TokenRecuperacionInvalido(ErrorIdentidad):
    """Token de recuperación usado, vencido o inexistente (400)."""


class IRegistroUsuario(Protocol):
    def alta(self, correo: str, contrasena: str) -> Sesion: ...

    def login(self, correo: str, contrasena: str) -> Sesion: ...

    def renovar(self, token_renovacion: str) -> str: ...

    def cerrar_sesion(self, token_renovacion: str) -> None: ...
