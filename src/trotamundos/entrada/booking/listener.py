# SPEC: SPEC-COMP-07
# ELEMENTO PASO 5: Adaptador de anuncios (Booking), listener del aviso (ITERACION_3)
# ADRs: ADR-IT3-009, ADR-IT3-010
# DRIVERS: QA-PER-01
"""`POST /proveedores/booking/avisos`, con la clave compartida en `X-Clave-Proveedor`.

202: quedó en la cola de novedades. 401: clave inválida (no se publica nada). 422: aviso mal formado.
429: se superó la tasa. 503: la cola está llena; Booking reentrega. El endpoint no pasa por el Gateway."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request

from trotamundos.broker import ColaLlena
from trotamundos.entrada.booking.adaptador import AdaptadorBooking, ClaveInvalida, TasaExcedida
from trotamundos.entrada.booking.aviso import AvisoInvalido


def crear_router(adaptador: AdaptadorBooking) -> APIRouter:
    router = APIRouter()

    @router.post("/proveedores/booking/avisos", status_code=202)
    async def aviso(request: Request, x_clave_proveedor: Annotated[str | None, Header()] = None) -> dict:
        origen = request.client.host if request.client else "desconocido"
        try:
            adaptador.autenticar(x_clave_proveedor)  # la clave se mira antes de leer el cuerpo
            cuerpo = await adaptador.cuerpo_valido(request.json)
            identificador = await adaptador.recibir_aviso(cuerpo, x_clave_proveedor, origen)
        except ClaveInvalida:
            raise HTTPException(status_code=401, detail="clave inválida") from None
        except TasaExcedida:
            raise HTTPException(status_code=429, detail="demasiados avisos", headers={"Retry-After": "1"}) from None
        except AvisoInvalido as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        except ColaLlena:
            raise HTTPException(status_code=503, detail="indisponible: reentregue",
                                headers={"Retry-After": "1"}) from None
        return {"id": identificador}

    return router
