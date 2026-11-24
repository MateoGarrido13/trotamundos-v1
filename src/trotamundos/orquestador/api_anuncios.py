# SPEC: SPEC-COMP-07
# ELEMENTO PASO 5: Orquestador de viajes, sección «Novedades» (ITERACION_3)
# ADRs: ADR-IT3-009
# DRIVERS: QA-PER-01
"""`GET /novedades/anuncios`: los anuncios de Booking de los últimos 30 días, del más reciente al más
viejo. La identidad llega ya verificada en `X-Viajero-Id`; sin ella, 401. Sin anuncios: lista vacía."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request

from trotamundos.orquestador.anuncios import serializar
from trotamundos.persistencia.base_viajes import ErrorBaseNoDisponible

router = APIRouter()


@router.get("/novedades/anuncios")
async def anuncios(request: Request, x_viajero_id: Annotated[str | None, Header()] = None) -> list[dict]:
    if not x_viajero_id:
        raise HTTPException(status_code=401, detail="falta X-Viajero-Id")
    try:
        return [serializar(f) for f in await request.app.state.anuncios.recientes()]
    except ErrorBaseNoDisponible:
        raise HTTPException(status_code=503, detail="base no disponible") from None
