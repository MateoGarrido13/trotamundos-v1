# SPEC: SPEC-COMP-05
# ELEMENTO PASO 5: API Gateway (ITERACION_4)
# ADRs: ADR-008, ADR-IT4-004
# DRIVERS: QA-SEG-01, CON-01
"""Firma de la identidad que el Gateway pasa al Core (D4): el Core solo cree en `X-Viajero-Id`
si viene con la firma que solo el Gateway puede hacer."""
from __future__ import annotations

import hashlib
import hmac

CABECERA_IDENTIDAD = "x-viajero-id"
CABECERA_FIRMA = "x-gateway-firma"
# Las rutas de correo (SPEC-REF-02, SPEC-COMP-04) identifican al titular con esta cabecera: el Gateway la
# pisa con la cuenta del token, igual que `x-viajero-id`.
CABECERA_TITULAR = "x-titular-id"
# `/correo/oauth/callback` es adonde vuelve el navegador desde Google: no trae token. Lo protege el
# `state` de un solo uso que emitió `POST /correo/oauth/iniciar` (SPEC-COMP-04).
RUTAS_PUBLICAS = ("/salud", "/auth/", "/web", "/movil", "/correo/oauth/callback")


def es_publica(ruta: str) -> bool:
    return any(ruta == p.rstrip("/") or ruta.startswith(p) for p in RUTAS_PUBLICAS)


def firmar(secreto: str, identidad: str) -> str:
    return hmac.new(secreto.encode(), identidad.encode(), hashlib.sha256).hexdigest()


def firma_valida(secreto: str, identidad: str, firma: str) -> bool:
    return hmac.compare_digest(firmar(secreto, identidad), firma)
