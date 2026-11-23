# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Gestor de autorización del correo (endpoints vía API Gateway) (ITERACION_3)
# ADRs: ADR-IT3-006, ADR-IT3-010
# DRIVERS: QA-SEG-03*
"""App de entrada (nodos de entrada, separada de la del Orquestador, ADR-IT3-010).

Autorizar y revocar llegan por el API Gateway, que identifica al titular con `X-Titular-Id`."""
from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel

from trotamundos.entrada.gestor_autorizacion import GestorAutorizacion


class Consentimiento(BaseModel):
    token: str


def create_app(gestor: GestorAutorizacion) -> FastAPI:
    app = FastAPI(title="Trotamundos - nodos de entrada")

    def _titular(x_titular_id: str | None) -> str:
        if not x_titular_id:
            raise HTTPException(status_code=401, detail="falta X-Titular-Id")
        return x_titular_id

    @app.post("/correo/autorizacion", status_code=201)
    def autorizar(consentimiento: Consentimiento, x_titular_id: str | None = Header(default=None)):
        titular = _titular(x_titular_id)
        vence = gestor.autorizar(titular, consentimiento.token)
        return {"titular_id": titular, "vence": vence.isoformat()}

    @app.delete("/correo/autorizacion", status_code=204)
    def revocar(x_titular_id: str | None = Header(default=None)) -> Response:
        gestor.revocar(_titular(x_titular_id))
        return Response(status_code=204)

    return app
