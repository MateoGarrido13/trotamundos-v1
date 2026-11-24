# SPEC: SPEC-COMP-05
# ELEMENTO PASO 5: Sesión con token firmado de vida corta (ITERACION_4)
# ADRs: ADR-IT4-004
# DRIVERS: QA-ESC-01, QA-PER-02
"""Token de acceso firmado con Ed25519. Cada región firma con su clave privada; el Gateway solo
tiene las públicas, así valida sin llamar a ninguna región y sin poder emitir (D2)."""
from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from datetime import datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from trotamundos.dominio.identidad import TokenInvalido


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def _desb64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def clave_privada_desde_semilla(semilla_hex: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(semilla_hex))


def clave_publica_hex(semilla_hex: str) -> str:
    return clave_privada_desde_semilla(semilla_hex).public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw).hex()


class EmisorTokens:
    """Lo usa solo el módulo de la región: tiene la clave privada."""

    def __init__(self, region: str, semilla_hex: str, vida: timedelta) -> None:
        self._region = region
        self._clave = clave_privada_desde_semilla(semilla_hex)
        self._vida = vida

    def emitir(self, cuenta_id: str, ahora: datetime) -> str:
        carga = {"sub": cuenta_id, "reg": self._region, "typ": "acceso",
                 "iat": int(ahora.timestamp()), "exp": int((ahora + self._vida).timestamp())}
        cuerpo = _b64(json.dumps(carga, separators=(",", ":")).encode())
        return f"{cuerpo}.{_b64(self._clave.sign(cuerpo.encode()))}"


class ValidadorTokens:
    """Lo usa el Gateway: solo claves públicas, ninguna llamada a una región."""

    def __init__(self, claves_publicas_hex: Mapping[str, str]) -> None:
        self._claves = {r: Ed25519PublicKey.from_public_bytes(bytes.fromhex(h))
                        for r, h in claves_publicas_hex.items()}

    def validar(self, token: str, ahora: datetime) -> str:
        """Devuelve el identificador de cuenta o lanza `TokenInvalido`."""
        try:
            cuerpo, firma = token.split(".")
            carga = json.loads(_desb64(cuerpo))
            clave = self._claves[carga["reg"]]
            clave.verify(_desb64(firma), cuerpo.encode())
            if carga.get("typ") != "acceso" or ahora.timestamp() >= carga["exp"]:
                raise TokenInvalido("vencido")
            cuenta_id = str(carga["sub"])
            if not cuenta_id.startswith(f"{carga['reg']}-"):
                raise TokenInvalido("identidad fuera de su región")
            return cuenta_id
        except TokenInvalido:
            raise
        except (ValueError, KeyError, TypeError, InvalidSignature) as e:
            raise TokenInvalido("token inválido") from e
