# SPEC: SPEC-REF-07
# ELEMENTO PASO 5: Módulo de Asistente Virtual, endpoints para Cliente web y móvil (RONDA_2/ITERACION_1)
# ADRs: ADR-IT6-001
# DRIVERS: REF-07
"""App del Asistente: nodos propios, sin estado, separada de las del Orquestador y de la entrada.

`POST /asistente/turno` con `{"itinerario_id", "mensaje", "contexto"}` y `POST /asistente/accion`
con `{"itinerario_id", "accion": {...}, "contexto"}`. La identidad llega ya verificada en
`X-Viajero-Id`. El cliente devuelve en cada pedido el contexto firmado que recibió en el anterior."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, FastAPI, Header, HTTPException

from trotamundos.asistente.asistente import ModuloAsistente

Actor = Annotated[str, Header(alias="X-Viajero-Id")]


def _texto(cuerpo: Any, campo: str) -> str:
    valor = cuerpo.get(campo) if isinstance(cuerpo, dict) else None
    if not isinstance(valor, str) or not valor:
        raise HTTPException(status_code=422, detail=f"Falta `{campo}`")
    return valor


def crear_router(modulo: ModuloAsistente) -> APIRouter:
    """Los endpoints del asistente, para montarlos en la app principal (SPEC-COMP-01)."""
    router = APIRouter()

    @router.post("/asistente/turno")
    async def turno(actor: Actor, cuerpo: Annotated[Any, Body()]) -> dict:
        itinerario = _texto(cuerpo, "itinerario_id")
        mensaje = cuerpo.get("mensaje")
        if not isinstance(mensaje, str):
            raise HTTPException(status_code=422, detail="Falta `mensaje`")
        r = await modulo.turno(actor, itinerario, mensaje, cuerpo.get("contexto"))
        return r.a_dict()

    @router.post("/asistente/accion")
    async def accion(actor: Actor, cuerpo: Annotated[Any, Body()]) -> dict:
        itinerario = _texto(cuerpo, "itinerario_id")
        if not isinstance(cuerpo.get("accion"), dict):
            raise HTTPException(status_code=422, detail="Falta `accion`")
        r = await modulo.accion(actor, itinerario, cuerpo["accion"], cuerpo.get("contexto"))
        return r.a_dict()

    return router


def create_app(modulo: ModuloAsistente) -> FastAPI:
    app = FastAPI(title="Trotamundos - Asistente virtual")
    app.state.modulo = modulo
    app.include_router(crear_router(modulo))

    @app.get("/salud")
    def salud() -> dict[str, str]:
        return {"estado": "ok"}

    return app
