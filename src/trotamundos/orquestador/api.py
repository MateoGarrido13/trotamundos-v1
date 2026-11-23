# SPEC: SPEC-REF-01
# ELEMENTO PASO 5: Vista principal y archivo para Cliente web y móvil (ITERACION_1)
# ADRs: ADR-001
# DRIVERS: REF-01, CON-01
"""GET /viajes y GET /viajes/archivados. La identidad llega ya encaminada en `X-Viajero-Id`
(simula al gateway)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request

from trotamundos.orquestador.agrupacion import Agrupacion, ViajeAgrupado
from trotamundos.persistencia.base_viajes import ErrorBaseNoDisponible

router = APIRouter()


def _serializar(request: Request, viaje: ViajeAgrupado) -> dict:
    nombres = {clase: nombre for nombre, clase in request.app.state.registro_tipos.tipos().items()}
    return {
        "id": viaje.id,
        "estado": viaje.estado,
        "reservas": [
            {
                "identificador": r.identificador,
                "tipo": nombres.get(type(r)),
                "inicio": r.inicio.isoformat(),
                "fin": r.fin.isoformat(),
                "estado": r.estado.value,
                "lugar": r.lugar,
                "resumen": r.resumen(),
            }
            for r in viaje.reservas
        ],
    }


def _consultar(request: Request, viajero_id: str, archivados: bool) -> list[dict]:
    agrupacion = Agrupacion(request.app.state.repositorio)
    try:
        viajes = (agrupacion.archivados if archivados else agrupacion.vista_principal)(viajero_id)
    except ErrorBaseNoDisponible as e:
        raise HTTPException(status_code=503, detail=f"Servicio no disponible: {e}") from e
    return [_serializar(request, v) for v in viajes]


@router.get("/viajes")
def vista_principal(request: Request, x_viajero_id: Annotated[str, Header()]) -> list[dict]:
    return _consultar(request, x_viajero_id, archivados=False)


@router.get("/viajes/archivados")
def viajes_archivados(request: Request, x_viajero_id: Annotated[str, Header()]) -> list[dict]:
    return _consultar(request, x_viajero_id, archivados=True)
