# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Gestor de autorización del correo (ITERACION_3)
# ADRs: ADR-IT3-006
# DRIVERS: QA-SEG-03*, REF-02
"""Cifrado de tokens (Fernet). La clave sale de `TROTA_CLAVE_TOKENS` (simplificación de la spec)."""
from __future__ import annotations

from cryptography.fernet import Fernet


class CifradorTokens:
    def __init__(self, clave: str | bytes) -> None:
        if not clave:
            raise ValueError("Falta la clave de cifrado de tokens (TROTA_CLAVE_TOKENS)")
        self._fernet = Fernet(clave)

    def cifrar(self, token: str) -> bytes:
        return self._fernet.encrypt(token.encode())

    def descifrar(self, cifrado: bytes) -> str:
        return self._fernet.decrypt(cifrado).decode()
