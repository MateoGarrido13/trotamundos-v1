# SPEC: SPEC-COMP-05
# ELEMENTO PASO 5: Cuentas, alta y autenticación; Seguridad del login (ITERACION_4)
# ADRs: ADR-IT4-001, ADR-IT4-004, ADR-IT4-005, ADR-IT4-006
# DRIVERS: QA-ESC-01, QA-SEG-01
"""Endpoints `/auth`. El cliente indica su región (enrutamiento por proximidad simulado, D7)."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from trotamundos.dominio.identidad import (
    CorreoYaRegistrado,
    CredencialInvalida,
    DatosInvalidos,
    Sesion,
    TokenInvalido,
    TokenRecuperacionInvalido,
)
from trotamundos.identidad.region.servicio import ServicioRegion
from trotamundos.persistencia.base_viajes import ErrorBaseNoDisponible

MENSAJE_RECUPERACION = {"mensaje": "Si la cuenta existe, enviamos las instrucciones a su correo."}


class PedidoAlta(BaseModel):
    correo: str
    contrasena: str
    region: str


class PedidoLogin(PedidoAlta):
    pass


class PedidoToken(BaseModel):
    token_renovacion: str


class PedidoRecuperacion(BaseModel):
    correo: str
    region: str


class PedidoCompletar(BaseModel):
    token: str
    contrasena: str


def _sesion(s: Sesion) -> dict[str, str]:
    return {"cuenta_id": s.cuenta_id, "token_acceso": s.token_acceso, "token_renovacion": s.token_renovacion}


def crear_router(servicios: dict[str, ServicioRegion], hilos_recuperacion: int = 4) -> APIRouter:
    router = APIRouter(prefix="/auth")
    # D10: la recuperación tiene sus propios hilos; saturarla no consume los del login.
    pool_recuperacion = ThreadPoolExecutor(max_workers=hilos_recuperacion, thread_name_prefix="recuperacion")

    def region(nombre: str) -> ServicioRegion:
        if nombre not in servicios:
            raise HTTPException(422, "región desconocida")
        return servicios[nombre]

    def region_del_token(token: str) -> ServicioRegion | None:
        return servicios.get(token.split(".", 1)[0]) if "." in token else None

    @router.post("/alta", status_code=201)
    def alta(p: PedidoAlta) -> dict[str, str]:
        try:
            return _sesion(region(p.region).alta(p.correo, p.contrasena))
        except CorreoYaRegistrado:
            raise HTTPException(409, "el correo ya está registrado") from None
        except DatosInvalidos as e:
            raise HTTPException(422, str(e)) from None
        except ErrorBaseNoDisponible:
            raise HTTPException(503, "servicio no disponible") from None

    @router.post("/login")
    def login(p: PedidoLogin) -> dict[str, str]:
        try:
            return _sesion(region(p.region).login(p.correo, p.contrasena))
        except CredencialInvalida:
            raise HTTPException(401, "credenciales inválidas") from None
        except ErrorBaseNoDisponible:
            raise HTTPException(503, "servicio no disponible") from None

    @router.post("/renovar")
    def renovar(p: PedidoToken) -> dict[str, str]:
        servicio = region_del_token(p.token_renovacion)
        try:
            if servicio is None:
                raise TokenInvalido("región desconocida")
            return {"token_acceso": servicio.renovar(p.token_renovacion)}
        except TokenInvalido:
            raise HTTPException(401, "token inválido") from None
        except ErrorBaseNoDisponible:
            raise HTTPException(503, "servicio no disponible") from None

    @router.post("/cerrar-sesion", status_code=204)
    def cerrar_sesion(p: PedidoToken) -> None:
        servicio = region_del_token(p.token_renovacion)
        if servicio is not None:
            try:
                servicio.cerrar_sesion(p.token_renovacion)
            except ErrorBaseNoDisponible:
                raise HTTPException(503, "servicio no disponible") from None

    @router.post("/recuperacion", status_code=202)
    async def recuperacion(p: PedidoRecuperacion) -> dict[str, str]:
        servicio = region(p.region)
        try:
            await asyncio.get_running_loop().run_in_executor(
                pool_recuperacion, servicio.solicitar_recuperacion, p.correo)
        except ErrorBaseNoDisponible:
            raise HTTPException(503, "servicio no disponible") from None
        return MENSAJE_RECUPERACION

    @router.post("/recuperacion/completar", status_code=204)
    async def completar(p: PedidoCompletar) -> None:
        servicio = region_del_token(p.token)
        try:
            if servicio is None:
                raise TokenRecuperacionInvalido()
            await asyncio.get_running_loop().run_in_executor(
                pool_recuperacion, servicio.completar_recuperacion, p.token, p.contrasena)
        except TokenRecuperacionInvalido:
            raise HTTPException(400, "token inválido, usado o vencido") from None
        except DatosInvalidos as e:
            raise HTTPException(422, str(e)) from None
        except ErrorBaseNoDisponible:
            raise HTTPException(503, "servicio no disponible") from None

    return router
