# SPEC: SPEC-COMP-05
# ELEMENTO PASO 5: API Gateway, frontera del Core (ITERACION_4)
# ADRs: ADR-IT4-004
# DRIVERS: QA-SEG-01
"""El Core solo acepta una identidad que firmó el Gateway (D4, `AC-COMP-05-07`)."""
from __future__ import annotations

from trotamundos.identidad.gateway.firma import CABECERA_FIRMA, CABECERA_IDENTIDAD, es_publica, firma_valida
from trotamundos.identidad.gateway.gateway import responder


class ExigirGateway:
    def __init__(self, app, secreto: str) -> None:
        self.app = app
        self._secreto = secreto

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and not es_publica(scope["path"]):
            cabeceras = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
            identidad = cabeceras.get(CABECERA_IDENTIDAD)
            if identidad is not None and not firma_valida(
                    self._secreto, identidad, cabeceras.get(CABECERA_FIRMA, "")):
                return await responder(send, 401, {"detail": "identidad no verificada por el Gateway"})
        await self.app(scope, receive, send)
