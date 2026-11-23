# SPEC: SPEC-REF-06
# ELEMENTO PASO 5: Servicio de consultas analíticas, endpoint para el equipo de datos (ITERACION_5)
# ADRs: ADR-IT5-001, ADR-IT5-002
# DRIVERS: REF-06, QA-PER-04*
"""App del Servicio de consultas analíticas: nodos propios, separada de la del Orquestador.

`GET /analitica/informe?desde=&hasta=&destino=&tipo_reserva=` con la cuenta ya verificada por el
gateway en `X-Viajero-Id`. 403: la cuenta no es del equipo de datos (ningún dato del informe).
504: la cota de 10 segundos venció (ningún informe parcial). 503: la Base analítica no responde.
422: fechas inválidas o `desde` posterior a `hasta`."""
from __future__ import annotations

from datetime import date
from typing import Annotated

import psycopg
from fastapi import APIRouter, FastAPI, Header, Query
from fastapi.responses import JSONResponse

from trotamundos.analitica.consultas import AccesoDenegado, ErrorTiempoAgotado, ServicioConsultas


def crear_router(servicio: ServicioConsultas) -> APIRouter:
    """El endpoint del informe, para montarlo en la app principal (SPEC-COMP-01)."""
    router = APIRouter()

    @router.get("/analitica/informe")
    async def informe(desde: Annotated[date, Query()], hasta: Annotated[date, Query()],
                      actor: Annotated[str, Header(alias="X-Viajero-Id")],
                      destino: str | None = None, tipo_reserva: str | None = None):
        try:
            return await servicio.informe(actor, desde, hasta, destino, tipo_reserva)
        except AccesoDenegado:
            return JSONResponse({"error": "acceso_denegado"}, status_code=403)
        except ErrorTiempoAgotado:
            return JSONResponse({"error": "tiempo_agotado"}, status_code=504)
        except ValueError as e:
            return JSONResponse({"error": "rango_invalido", "detalle": str(e)}, status_code=422)
        except psycopg.OperationalError:
            return JSONResponse({"error": "base_analitica_no_disponible"}, status_code=503)

    return router


def create_app(servicio: ServicioConsultas | None = None) -> FastAPI:
    servicio = servicio or ServicioConsultas()
    app = FastAPI(title="Trotamundos - consultas analíticas")
    app.state.servicio = servicio
    app.include_router(crear_router(servicio))

    @app.get("/salud")
    def salud() -> dict[str, str]:
        return {"estado": "ok"}

    return app
