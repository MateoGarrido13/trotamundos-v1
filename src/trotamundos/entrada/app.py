# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Gestor de autorización del correo (endpoints vía API Gateway) (ITERACION_3)
# ADRs: ADR-IT3-006, ADR-IT3-010
# DRIVERS: QA-SEG-03*
"""App de entrada (nodos de entrada, separada de la del Orquestador, ADR-IT3-010).

Autorizar y revocar llegan por el API Gateway, que identifica al titular con `X-Titular-Id`."""
from __future__ import annotations

from fastapi import APIRouter, FastAPI, Header, HTTPException, Response
from pydantic import BaseModel

from trotamundos.entrada import api_agencia
from trotamundos.entrada.agencia import AdaptadorAgencia
from trotamundos.entrada.gestor_autorizacion import GestorAutorizacion


class Consentimiento(BaseModel):
    token: str


def crear_router(gestor: GestorAutorizacion) -> APIRouter:
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
    def revocar(x_titular_id: str | None = Header(default=None)) -> Response:
        gestor.revocar(_titular(x_titular_id))
        return Response(status_code=204)

    return router


def create_app(gestor: GestorAutorizacion, adaptador_agencia: AdaptadorAgencia | None = None) -> FastAPI:
    app = FastAPI(title="Trotamundos - nodos de entrada")
    if adaptador_agencia is not None:  # listener del aviso de la agencia (SPEC-REF-05)
        app.include_router(api_agencia.crear_router(adaptador_agencia))
    app.include_router(crear_router(gestor))
    return app
