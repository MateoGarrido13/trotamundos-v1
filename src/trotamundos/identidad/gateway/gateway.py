# SPEC: SPEC-COMP-05
# ELEMENTO PASO 5: API Gateway (ITERACION_4)
# ADRs: ADR-008, ADR-IT4-004, ADR-IT4-005
# DRIVERS: QA-ESC-01, QA-SEG-01, QA-PER-02, CON-01
"""El Gateway como middleware de la app principal: limita la tasa, valida el token de acceso con
las claves públicas (sin llamar a ninguna región) y pasa al Core la identidad ya verificada."""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from trotamundos.dominio.identidad import TokenInvalido
from trotamundos.identidad.gateway.firma import CABECERA_FIRMA, CABECERA_IDENTIDAD, es_publica, firmar
from trotamundos.identidad.gateway.limitador import LimitadorTasa
from trotamundos.identidad.tokens import ValidadorTokens

log = logging.getLogger(__name__)


async def responder(send, estado: int, cuerpo: dict) -> None:
    datos = json.dumps(cuerpo).encode()
    await send({"type": "http.response.start", "status": estado,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(datos)).encode())]})
    await send({"type": "http.response.body", "body": datos})


class Gateway:
    def __init__(self, app, validador: ValidadorTokens, limitador: LimitadorTasa, secreto: str,
                 reloj: Callable[[], datetime] | None = None) -> None:
        self.app = app
        self._validador = validador
        self.limitador = limitador
        self._secreto = secreto
        self._reloj = reloj or (lambda: datetime.now(UTC))

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        ruta = scope["path"]
        origen = (scope.get("client") or ("desconocido", 0))[0]
        if self.limitador.limita(ruta) and not self.limitador.permitir(ruta, origen):
            log.warning("límite de tasa superado en %s por %s", ruta, origen)
            return await responder(send, 429, {"detail": "demasiados pedidos"})
        # Nada de lo que traiga el cliente en estas cabeceras vale: el Gateway las reescribe.
        cabeceras = [(k, v) for k, v in scope["headers"]
                     if k.decode().lower() not in (CABECERA_IDENTIDAD, CABECERA_FIRMA)]
        if not es_publica(ruta):
            autorizacion = dict(scope["headers"]).get(b"authorization", b"").decode()
            if not autorizacion.lower().startswith("bearer "):
                return await responder(send, 401, {"detail": "falta el token de acceso"})
            try:
                cuenta_id = self._validador.validar(autorizacion[7:].strip(), self._reloj())
            except TokenInvalido:
                return await responder(send, 401, {"detail": "token inválido o vencido"})
            cabeceras += [(CABECERA_IDENTIDAD.encode(), cuenta_id.encode()),
                          (CABECERA_FIRMA.encode(), firmar(self._secreto, cuenta_id).encode())]
        await self.app({**scope, "headers": cabeceras}, receive, send)
