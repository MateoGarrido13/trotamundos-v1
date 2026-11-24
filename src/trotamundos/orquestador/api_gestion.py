# SPEC: SPEC-REF-04
# ELEMENTO PASO 5: Operaciones manuales de reserva, endpoints para Cliente web y móvil (ITERACION_4)
# ADRs: ADR-IT4-008, ADR-IT4-007
# DRIVERS: REF-04, QA-SEG-02
"""Endpoints de la gestión manual. La identidad del actor llega ya verificada en
`X-Viajero-Id` (simula al gateway) y la clave de operación, generada por el cliente, en
`X-Clave-Operacion`.

El cuerpo se recibe como JSON y no con un modelo estricto: el permiso se verifica antes que los
campos (para no revelar nada a quien no puede ver), y un campo inválido tiene que dejar su
asiento de auditoría, cosa que un rechazo previo de FastAPI no haría.

Códigos: 403 acceso denegado (el cliente presenta la página «Error 401»), 404 la reserva no
existe, 409 la reserva está dada de baja, 422 tipo no registrado o campos inválidos."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from trotamundos.dominio.reserva import lugar_publico
from trotamundos.orquestador.gestion_reservas import (
    AccesoDenegado,
    GestionReservas,
    RespuestaOperacion,
    SolicitudReserva,
)
from trotamundos.persistencia.base_viajes import ErrorBaseNoDisponible

router = APIRouter(prefix="/itinerarios")

Actor = Annotated[str, Header(alias="X-Viajero-Id")]
Clave = Annotated[str, Header(alias="X-Clave-Operacion")]
Cuerpo = Annotated[Any, Body()]

CODIGOS_RECHAZO = {"no_existe": 404, "en_baja": 409, "tipo_no_registrado": 422, "campos_invalidos": 422}
ACCESO_DENEGADO = {"error": "acceso_denegado"}


def _gestion(request: Request) -> GestionReservas:
    return request.app.state.gestion


def _responder(r: RespuestaOperacion) -> JSONResponse:
    if r.estado == "ok":
        return JSONResponse({"reserva": r.reserva, "repetida": r.repetida},
                            status_code=201 if r.operacion == "agregar" else 200)
    if r.estado == "denegado":
        return JSONResponse(ACCESO_DENEGADO, status_code=403)
    return JSONResponse({"error": r.motivo}, status_code=CODIGOS_RECHAZO.get(r.motivo or "", 422))


def _objeto(cuerpo: Any, campo: str | None = None) -> dict:
    valor = cuerpo if campo is None else (cuerpo.get(campo) if isinstance(cuerpo, dict) else None)
    if not isinstance(valor, dict):
        raise HTTPException(status_code=422, detail="El cuerpo debe ser un objeto JSON")
    return valor


def _serializar(request: Request, viaje) -> dict:
    # SPEC-COMP-01, regla 8: el `tipo` es el código del registro, no el nombre de la clase.
    nombres = {clase: nombre for nombre, clase in request.app.state.registro_tipos.tipos().items()}
    return {"id": viaje.id, "estado": viaje.estado, "reservas": [{
        "identificador": r.identificador, "tipo": nombres.get(type(r)), "inicio": r.inicio.isoformat(),
        "fin": r.fin.isoformat(), "estado": r.estado.value, "lugar": lugar_publico(r.lugar),
        "origen": r.origen.value,
        "creado_por": r.creado_por, "resumen": r.resumen()} for r in viaje.reservas]}


@router.post("/{itinerario_id}/reservas")
async def agregar_reserva(request: Request, itinerario_id: str, actor: Actor, clave: Clave,
                          cuerpo: Cuerpo) -> JSONResponse:
    """`agregarReserva`. Los campos se validan dentro del servicio, después del permiso."""
    c = _objeto(cuerpo)
    datos = c.get("datos", {})
    if not isinstance(datos, dict):
        raise HTTPException(status_code=422, detail="`datos` debe ser un objeto JSON")
    solicitud = SolicitudReserva(  # inicio y fin llegan como texto: los valida la clase concreta
        viaje_id=c.get("viaje_id"), tipo=c.get("tipo"), inicio=c.get("inicio"), fin=c.get("fin"),
        lugar=c.get("lugar"), datos=datos)
    try:
        return _responder(await _gestion(request).agregar(actor, itinerario_id, clave, solicitud))
    except ErrorBaseNoDisponible:
        raise HTTPException(status_code=503, detail="Servicio no disponible") from None


@router.patch("/{itinerario_id}/reservas/{reserva_id}")
async def actualizar_reserva(request: Request, itinerario_id: str, reserva_id: str, actor: Actor,
                             clave: Clave, cuerpo: Cuerpo) -> JSONResponse:
    """`actualizarReserva(id)`. El cuerpo es `{"cambios": {...}}`."""
    cambios = _objeto(cuerpo, "cambios")
    try:
        return _responder(await _gestion(request).actualizar(actor, itinerario_id, reserva_id, clave, cambios))
    except ErrorBaseNoDisponible:
        raise HTTPException(status_code=503, detail="Servicio no disponible") from None


@router.delete("/{itinerario_id}/reservas/{reserva_id}")
async def eliminar_reserva(request: Request, itinerario_id: str, reserva_id: str, actor: Actor,
                           clave: Clave) -> JSONResponse:
    """`eliminarReserva(id)`: baja lógica."""
    try:
        return _responder(await _gestion(request).eliminar(actor, itinerario_id, reserva_id, clave))
    except ErrorBaseNoDisponible:
        raise HTTPException(status_code=503, detail="Servicio no disponible") from None


@router.get("/{itinerario_id}")
async def vista_itinerario(request: Request, itinerario_id: str, actor: Actor):
    """Las reservas vigentes del itinerario agrupadas por viaje."""
    try:
        viajes = await _gestion(request).vista(actor, itinerario_id)
    except AccesoDenegado:
        return JSONResponse(ACCESO_DENEGADO, status_code=403)
    except ErrorBaseNoDisponible:
        raise HTTPException(status_code=503, detail="Servicio no disponible") from None
    return [_serializar(request, v) for v in viajes]


@router.get("/{itinerario_id}/novedades")
async def novedades(request: Request, itinerario_id: str, actor: Actor):
    """«Novedades»: lo que el proveedor informó y no pisó una edición manual."""
    try:
        pendientes = await request.app.state.novedades.pendientes(actor, itinerario_id)
    except AccesoDenegado:
        return JSONResponse(ACCESO_DENEGADO, status_code=403)
    except ErrorBaseNoDisponible:
        raise HTTPException(status_code=503, detail="Servicio no disponible") from None
    return [{"id": n.id, "reserva_id": n.reserva_id, "proveedor": n.proveedor,
             "cambios": n.cambios, "recibida_en": n.recibida_en.isoformat()} for n in pendientes]
