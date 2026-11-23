# SPEC: SPEC-REF-05
# ELEMENTO PASO 5: Orquestador de viajes, casos de ayuda, endpoints del viajero (ITERACION_4)
# ADRs: ADR-IT4-010, ADR-IT4-007, ADR-IT4-008
# DRIVERS: REF-05
"""Endpoints del viajero: elegir su agencia, reportar un problema, reintentar un caso y consultar
sus casos. La identidad del actor llega ya verificada en `X-Viajero-Id` y la clave de operación,
generada por el cliente, en `X-Clave-Operacion`.

Como en la gestión manual, el cuerpo se recibe como JSON y el permiso se verifica antes que los
campos. Códigos: 403 acceso denegado, 404 el caso o la reserva no existe, 409 hay que elegir
agencia primero o el caso no está «sin entregar», 422 datos inválidos."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from trotamundos.orquestador.casos import RespuestaCaso, ServicioCasos
from trotamundos.persistencia.base_viajes import ErrorBaseNoDisponible

router = APIRouter()

Actor = Annotated[str, Header(alias="X-Viajero-Id")]
Clave = Annotated[str, Header(alias="X-Clave-Operacion")]
Cuerpo = Annotated[Any, Body()]

CODIGOS_RECHAZO = {
    "sin_consentimiento": 422, "agencia_no_registrada": 422, "descripcion_invalida": 422,
    "sin_agencia_o_consentimiento": 409, "estado_invalido": 409,
    "reserva_inexistente": 404, "caso_inexistente": 404,
}
ACCESO_DENEGADO = {"error": "acceso_denegado"}


def _servicio(request: Request) -> ServicioCasos:
    return request.app.state.casos


def _responder(r: RespuestaCaso) -> JSONResponse:
    if r.estado == "ok":
        cuerpo: dict = {"repetida": r.repetida}
        if r.caso is not None:
            cuerpo["caso"] = r.caso
        return JSONResponse(cuerpo, status_code=201 if r.operacion == "reportar" else 200)
    if r.estado == "denegado":
        return JSONResponse(ACCESO_DENEGADO, status_code=403)
    return JSONResponse({"error": r.motivo}, status_code=CODIGOS_RECHAZO.get(r.motivo or "", 422))


def _objeto(cuerpo: Any) -> dict:
    if not isinstance(cuerpo, dict):
        raise HTTPException(status_code=422, detail="El cuerpo debe ser un objeto JSON")
    return cuerpo


def _texto(cuerpo: dict, campo: str) -> str:
    valor = cuerpo.get(campo)
    if not isinstance(valor, str) or not valor:
        raise HTTPException(status_code=422, detail=f"Falta `{campo}`")
    return valor


@router.put("/agencia-preferida")
async def elegir_agencia(request: Request, actor: Actor, cuerpo: Cuerpo) -> JSONResponse:
    """`elegirAgenciaPreferida(agencia, consentimiento)`. El consentimiento debe ser `true`."""
    c = _objeto(cuerpo)
    try:
        return _responder(await _servicio(request).elegir_agencia(actor, c.get("agencia"), c.get("consentimiento")))
    except ErrorBaseNoDisponible:
        raise HTTPException(status_code=503, detail="Servicio no disponible") from None


@router.get("/agencia-preferida")
async def consultar_agencia_preferida(request: Request, actor: Actor) -> dict:
    """La agencia preferida y su número de contacto. Sin agencia elegida: ambos `null`, no es error."""
    try:
        return await _servicio(request).consultar_agencia_preferida(actor)
    except ErrorBaseNoDisponible:
        raise HTTPException(status_code=503, detail="Servicio no disponible") from None


@router.post("/casos")
async def reportar_problema(request: Request, actor: Actor, clave: Clave, cuerpo: Cuerpo) -> JSONResponse:
    """Reportar un problema: el caso queda «en trámite» y el viajero no espera a la agencia."""
    c = _objeto(cuerpo)
    itinerario, reserva = _texto(c, "itinerario_id"), _texto(c, "reserva_id")
    try:
        return _responder(await _servicio(request).reportar(
            actor, itinerario, clave, reserva, c.get("descripcion"), c.get("resumen_dialogo")))
    except ErrorBaseNoDisponible:
        raise HTTPException(status_code=503, detail="Servicio no disponible") from None


@router.post("/casos/{caso_id}/reintentar")
async def reintentar_caso(request: Request, caso_id: str, actor: Actor, clave: Clave,
                          cuerpo: Cuerpo) -> JSONResponse:
    """Reintenta un caso «sin entregar»: vuelve a «en trámite» y se publica de nuevo."""
    itinerario = _texto(_objeto(cuerpo), "itinerario_id")
    try:
        return _responder(await _servicio(request).reintentar(actor, itinerario, caso_id, clave))
    except ErrorBaseNoDisponible:
        raise HTTPException(status_code=503, detail="Servicio no disponible") from None


@router.get("/casos")
async def consultar_casos(request: Request, actor: Actor):
    """Los casos del viajero con su estado: es lo que ve en «Novedades». Sin casos: lista vacía."""
    try:
        return await _servicio(request).consultar(actor)
    except ErrorBaseNoDisponible:
        raise HTTPException(status_code=503, detail="Servicio no disponible") from None
