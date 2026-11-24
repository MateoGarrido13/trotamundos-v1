# SPEC: SPEC-COMP-06
# ELEMENTO PASO 5: API Gateway hacia la Caché de borde (ITERACION_2)
# ADRs: ADR-IT2-001
# DRIVERS: QA-PER-02
"""`GET /cotizaciones?fecha=&hospedaje=&compania=`. Parámetros inválidos: 422 (lo valida FastAPI)."""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from trotamundos.cotizacion.borde import CacheBorde
from trotamundos.dominio.cotizacion import Criterios

Texto = Annotated[str, Query(min_length=1, max_length=100, pattern=r"\S")]


def crear_router(borde: CacheBorde) -> APIRouter:
    router = APIRouter()

    @router.get("/cotizaciones")
    async def cotizaciones(fecha: date, hospedaje: Texto, compania: Texto) -> dict:
        grilla = await borde.obtener(Criterios(fecha, hospedaje.strip(), compania.strip()))
        return grilla.a_dict()

    return router
