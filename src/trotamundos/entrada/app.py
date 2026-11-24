# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Gestor de autorización del correo (endpoints vía API Gateway) (ITERACION_3)
# ADRs: ADR-IT3-006, ADR-IT3-010
# DRIVERS: QA-SEG-03*
"""App de entrada (nodos de entrada, separada de la del Orquestador, ADR-IT3-010).

Autorizar y revocar llegan por el API Gateway, que identifica al titular con `X-Titular-Id`."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, FastAPI, Header, HTTPException, Response
from pydantic import BaseModel

from trotamundos.entrada import api_agencia
from trotamundos.entrada.agencia import AdaptadorAgencia
from trotamundos.entrada.gestor_autorizacion import GestorAutorizacion


log = logging.getLogger(__name__)

# Aviso a la API de correo de que el acceso se revocó: (titular, token que había). Lo llena la composición.
AlRevocar = Callable[[str, str], Awaitable[None]]


class Consentimiento(BaseModel):
    token: str


def crear_router(gestor: GestorAutorizacion, al_revocar: AlRevocar | None = None) -> APIRouter:
    """Autorizar y revocar el correo, para montarlos en la app principal (SPEC-COMP-01)."""
    router = APIRouter()

    def _titular(x_titular_id: str | None) -> str:
        if not x_titular_id:
            raise HTTPException(status_code=401, detail="falta X-Titular-Id")
        return x_titular_id

    @router.post("/correo/autorizacion", status_code=201)
    def autorizar(consentimiento: Consentimiento, x_titular_id: str | None = Header(default=None)):
        titular = _titular(x_titular_id)
        vence = gestor.autorizar(titular, consentimiento.token)
        return {"titular_id": titular, "vence": vence.isoformat()}

    @router.delete("/correo/autorizacion", status_code=204)
    async def revocar(x_titular_id: str | None = Header(default=None)) -> Response:
        titular = _titular(x_titular_id)
        token = await asyncio.to_thread(gestor.token_vigente, titular) if al_revocar else None
        await asyncio.to_thread(gestor.revocar, titular)  # primero el borrado local (SPEC-COMP-04, regla de revocar)
        if al_revocar and token:
            try:
                await al_revocar(titular, token)
            except Exception:  # noqa: BLE001 - el token local ya no existe: el aviso a la API es de mejor esfuerzo
                log.warning("no se pudo avisar la revocación de %s a la API de correo", titular)
        return Response(status_code=204)

    return router


def create_app(gestor: GestorAutorizacion, adaptador_agencia: AdaptadorAgencia | None = None) -> FastAPI:
    app = FastAPI(title="Trotamundos - nodos de entrada")
    if adaptador_agencia is not None:  # listener del aviso de la agencia (SPEC-REF-05)
        app.include_router(api_agencia.crear_router(adaptador_agencia))
    app.include_router(crear_router(gestor))
    return app
