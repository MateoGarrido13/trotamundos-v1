# SPEC: SPEC-REF-03
# ELEMENTO PASO 5: Orquestador de viajes, Mensajes en revisión y aprobación de remitentes (ITERACION_3)
# ADRs: ADR-IT3-008
# DRIVERS: REF-03, QA-SEG-03*
"""Endpoints del titular (Cliente web y móvil, por el API Gateway). La identidad llega ya
encaminada en `X-Viajero-Id`.

Los identificadores de mensaje llevan `<`, `>` y `@`, por eso van en el cuerpo y no en la ruta."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel

from trotamundos.orquestador.revision import ErrorMensajeNoEncontrado, ServicioRevision
from trotamundos.persistencia.base_viajes import ErrorBaseNoDisponible

router = APIRouter(prefix="/revision")

Titular = Annotated[str, Header(alias="X-Viajero-Id")]


class CuerpoRemitente(BaseModel):
    remitente: str


class CuerpoMensaje(BaseModel):
    id_mensaje: str


def _servicio(request: Request) -> ServicioRevision:
    return request.app.state.servicio_revision


def _no_disponible() -> HTTPException:
    return HTTPException(status_code=503, detail="Servicio no disponible")


@router.get("")
async def consultar(request: Request, titular: Titular) -> list[dict]:
    """Mensajes pendientes con remitente y resumen. Sin mensajes: lista vacía, no error."""
    try:
        pendientes = await _servicio(request).consultar(titular)
    except ErrorBaseNoDisponible:
        raise _no_disponible() from None
    return [{"id_mensaje": m.id_mensaje, "remitente": m.remitente, "resumen": m.resumen}
            for m in pendientes]


@router.post("/remitentes")
async def aprobar(request: Request, titular: Titular, cuerpo: CuerpoRemitente) -> dict:
    """Aprueba un remitente (de un mensaje en revisión o nuevo). Ya aprobado: no es error."""
    try:
        liberados = await _servicio(request).aprobar(titular, cuerpo.remitente)
    except ErrorBaseNoDisponible:
        raise _no_disponible() from None
    return {"remitente": cuerpo.remitente.strip().lower(), "liberados": liberados}


@router.delete("/remitentes/{remitente}", status_code=204)
async def quitar(request: Request, titular: Titular, remitente: str) -> Response:
    """Quita un remitente de la whitelist. No está: no es error. No toca reservas incorporadas."""
    try:
        await _servicio(request).quitar(titular, remitente)
    except ErrorBaseNoDisponible:
        raise _no_disponible() from None
    return Response(status_code=204)


@router.post("/descartar", status_code=204)
async def descartar(request: Request, titular: Titular, cuerpo: CuerpoMensaje) -> Response:
    """Descarta un mensaje en revisión. Inexistente, ya resuelto o ajeno: 404 sin efecto."""
    try:
        await _servicio(request).descartar(titular, cuerpo.id_mensaje)
    except ErrorMensajeNoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    except ErrorBaseNoDisponible:
        raise _no_disponible() from None
    return Response(status_code=204)
