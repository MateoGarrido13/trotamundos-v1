# SPEC: SPEC-COMP-01
# ELEMENTO PASO 5: Alta de viajes y miembros, endpoints para Cliente web y móvil (ITERACION_4)
# ADRs: ADR-IT4-007, ADR-IT4-008
# DRIVERS: REF-04, CON-01
"""`POST /viajes`, `GET /itinerarios` y la administración de miembros. Mismos códigos que
`api_gestion`: 403 acceso denegado, 404 no existe, 409 último organizador, 422 datos inválidos."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from trotamundos.orquestador.alta_viajes import RespuestaAlta, ServicioViajes
from trotamundos.persistencia.base_viajes import ErrorBaseNoDisponible

router = APIRouter()

Actor = Annotated[str, Header(alias="X-Viajero-Id")]
Clave = Annotated[str, Header(alias="X-Clave-Operacion")]
Cuerpo = Annotated[Any, Body()]

CODIGOS = {"nombre_invalido": 422, "rol_invalido": 422, "cuenta_invalida": 422, "no_existe": 404,
           "ultimo_organizador": 409}


def _servicio(request: Request) -> ServicioViajes:
    return request.app.state.servicio_viajes


def _objeto(cuerpo: Any) -> dict:
    if not isinstance(cuerpo, dict):
        raise HTTPException(status_code=422, detail="El cuerpo debe ser un objeto JSON")
    return cuerpo


def _responder(r: RespuestaAlta, exito: int = 200) -> JSONResponse:
    if r.estado == "ok":
        return JSONResponse({**r.datos, "repetida": r.repetida}, status_code=200 if r.repetida else exito)
    if r.estado == "denegado":
        return JSONResponse({"error": "acceso_denegado"}, status_code=403)
    return JSONResponse({"error": r.motivo}, status_code=CODIGOS.get(r.motivo or "", 422))


async def _llamar(coroutine):
    try:
        return await coroutine
    except ErrorBaseNoDisponible:
        raise HTTPException(status_code=503, detail="Servicio no disponible") from None


@router.post("/viajes")
async def crear_viaje(request: Request, actor: Actor, clave: Clave, cuerpo: Cuerpo) -> JSONResponse:
    c = _objeto(cuerpo)
    return _responder(await _llamar(_servicio(request).crear_viaje(
        actor, clave, c.get("nombre"), c.get("itinerario_id"))), exito=201)


@router.get("/itinerarios")
async def mis_itinerarios(request: Request, actor: Actor) -> list[dict]:
    return await _llamar(_servicio(request).itinerarios_de(actor))


@router.get("/itinerarios/{itinerario_id}/miembros")
async def listar_miembros(request: Request, itinerario_id: str, actor: Actor):
    miembros = await _llamar(_servicio(request).listar_miembros(actor, itinerario_id))
    if miembros is None:
        return JSONResponse({"error": "acceso_denegado"}, status_code=403)
    return miembros


@router.post("/itinerarios/{itinerario_id}/miembros")
async def agregar_miembro(request: Request, itinerario_id: str, actor: Actor, clave: Clave,
                          cuerpo: Cuerpo) -> JSONResponse:
    c = _objeto(cuerpo)
    return _responder(await _llamar(_servicio(request).agregar_miembro(
        actor, itinerario_id, clave, c.get("cuenta"), c.get("rol"))))


@router.delete("/itinerarios/{itinerario_id}/miembros/{cuenta}")
async def quitar_miembro(request: Request, itinerario_id: str, cuenta: str, actor: Actor,
                         clave: Clave) -> JSONResponse:
    return _responder(await _llamar(_servicio(request).quitar_miembro(actor, itinerario_id, clave, cuenta)))
