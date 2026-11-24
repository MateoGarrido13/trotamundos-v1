# SPEC: SPEC-COMP-04
# ELEMENTO PASO 5: Gestor de autorización del correo (endpoints vía API Gateway) (ITERACION_3)
# ADRs: ADR-IT3-006
# DRIVERS: QA-SEG-03*
"""`POST /correo/oauth/iniciar` y `GET /correo/oauth/callback` (adonde vuelve Google)."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from trotamundos.entrada.gmail.oauth import AutorizacionRechazada, ServicioOAuth


def crear_router(oauth: ServicioOAuth) -> APIRouter:
    router = APIRouter()

    @router.post("/correo/oauth/iniciar")
    def iniciar(x_titular_id: str | None = Header(default=None)) -> dict[str, str]:
        if not x_titular_id:
            raise HTTPException(status_code=401, detail="falta X-Titular-Id")
        return {"url": oauth.iniciar_autorizacion(x_titular_id)}

    @router.get("/correo/oauth/callback")
    async def callback(code: str | None = None, state: str | None = None, error: str | None = None) -> dict[str, str]:
        if error or not code or not state:  # el titular negó el permiso, o falta algo
            if state:
                oauth.descartar_estado(state)
            raise HTTPException(status_code=400, detail="autorización rechazada")
        try:
            titular, vence = await oauth.completar_autorizacion(code, state)
        except AutorizacionRechazada:
            raise HTTPException(status_code=400, detail="autorización rechazada") from None
        return {"titular_id": titular, "vence": vence.isoformat()}

    return router
