# SPEC: SPEC-REF-05
# ELEMENTO PASO 5: Adaptador de agencia, listener del aviso (ITERACION_4)
# ADRs: ADR-IT4-010, ADR-IT3-002
# DRIVERS: REF-05
"""Listener del Adaptador de agencia: la agencia avisa que cambió un caso.

`POST /agencia/{agencia}/avisos` con `{"id_caso": ...}` y la clave compartida en
`X-Clave-Agencia`. 401: clave inválida (no se consulta ni se publica nada). 404: no hay un
adaptador con ese nombre. 503: la agencia no respondió o la cola de novedades está llena; la
agencia puede avisar de nuevo."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Header, HTTPException

from trotamundos.broker import ColaLlena
from trotamundos.entrada.agencia import AdaptadorAgencia, AgenciaDesconocida, ClaveInvalida, ErrorAgencia


def crear_router(adaptador: AdaptadorAgencia) -> APIRouter:
    router = APIRouter()

    @router.post("/agencia/{agencia}/avisos")
    async def aviso(agencia: str, cuerpo: Annotated[Any, Body()],
                    x_clave_agencia: Annotated[str | None, Header()] = None) -> dict:
        id_caso = cuerpo.get("id_caso") if isinstance(cuerpo, dict) else None
        try:
            resultado = await adaptador.recibir_aviso(agencia, id_caso or "", x_clave_agencia)
        except ClaveInvalida:
            raise HTTPException(status_code=401, detail="clave inválida") from None
        except AgenciaDesconocida:
            raise HTTPException(status_code=404, detail="agencia desconocida") from None
        except (ErrorAgencia, ColaLlena):
            raise HTTPException(status_code=503, detail="indisponible: avise de nuevo") from None
        return {"resultado": resultado}

    return router
