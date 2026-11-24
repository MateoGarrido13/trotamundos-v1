# SPEC: SPEC-COMP-05
# ELEMENTO PASO 5: Cuentas, alta y autenticación (ITERACION_4)
# ADRs: ADR-IT4-004
# DRIVERS: QA-SEG-01
"""Contraseñas con hash y sal (scrypt de la biblioteca estándar). Nunca se guardan en claro."""
from __future__ import annotations

import hashlib
import hmac
import secrets


def _scrypt(contrasena: str, sal: bytes, costo: int) -> bytes:
    return hashlib.scrypt(contrasena.encode(), salt=sal, n=2**costo, r=8, p=1, maxmem=2**28, dklen=32)


def hashear(contrasena: str, costo: int) -> str:
    sal = secrets.token_bytes(16)
    return f"scrypt${costo}${sal.hex()}${_scrypt(contrasena, sal, costo).hex()}"


def verificar(contrasena: str, guardado: str) -> bool:
    try:
        _, costo, sal, esperado = guardado.split("$")
        return hmac.compare_digest(_scrypt(contrasena, bytes.fromhex(sal), int(costo)), bytes.fromhex(esperado))
    except (ValueError, TypeError):
        return False
