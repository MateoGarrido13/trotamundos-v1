# SPEC: SPEC-COMP-05, SPEC-COMP-04
# ELEMENTO PASO 5: API Gateway y Gestor de autorización del correo
# ADRs: ADR-IT4-004, ADR-IT3-006
# DRIVERS: QA-SEG-01, QA-SEG-03*
"""Integración del Gateway (COMP-05) con las rutas de correo (REF-02 y COMP-04): el Gateway es quien
dice quién es el titular, y el regreso de Google no necesita token."""
from dataclasses import replace

import httpx
import pytest
from fastapi import FastAPI, Header

from tests.comp04_util import CFG as GMAIL
from trotamundos.app import create_app
from trotamundos.config import Configuracion
from trotamundos.identidad.gateway.firma import es_publica
from trotamundos.identidad.gateway.gateway import Gateway
from trotamundos.identidad.gateway.limitador import LimitadorTasa
from trotamundos.identidad.tokens import ValidadorTokens

SECRETO = "secreto-del-gateway"


def test_el_regreso_de_google_es_publico_y_el_resto_de_las_rutas_de_correo_no():
    assert es_publica("/correo/oauth/callback")
    assert not es_publica("/correo/oauth/iniciar") and not es_publica("/correo/autorizacion")
    assert not es_publica("/viajes")


class _Validador(ValidadorTokens):
    def __init__(self) -> None:
        pass

    def validar(self, token, ahora):
        return f"amer-{token}"


async def test_el_gateway_pisa_x_titular_id_con_la_cuenta_del_token():
    eco = FastAPI()

    @eco.get("/correo/x")
    def ver(x_titular_id: str | None = Header(default=None), x_viajero_id: str | None = Header(default=None)):
        return {"titular": x_titular_id, "viajero": x_viajero_id}

    @eco.get("/web/p")
    def publica(x_titular_id: str | None = Header(default=None)):
        return {"titular": x_titular_id}

    app = Gateway(eco, validador=_Validador(), limitador=LimitadorTasa({}, 60), secreto=SECRETO)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/correo/x", headers={"Authorization": "Bearer ana", "X-Titular-Id": "victima",
                                              "X-Viajero-Id": "victima"})
        assert r.json() == {"titular": "amer-ana", "viajero": "amer-ana"}  # el cliente no elige
        assert (await c.get("/web/p", headers={"X-Titular-Id": "victima"})).json() == {"titular": None}
        assert (await c.get("/correo/x", headers={"X-Titular-Id": "victima"})).status_code == 401  # sin token


pytestmark_db = pytest.mark.db


@pytest.fixture
def cfg(cuentas_limpias, bases_limpias, analitica_limpia):
    return Configuracion(bases=bases_limpias, analitica=analitica_limpia, gmail=replace(GMAIL),
                         identidad=replace(cuentas_limpias, exigir_gateway=True))


@pytest.fixture
async def app(cfg):
    sistema = create_app(cfg)
    yield sistema
    sistema.state.red_regiones.cerrar()
    await sistema.state.gmail.cerrar()


@pytestmark_db
async def test_con_gateway_el_titular_es_el_del_token_y_no_el_que_dice_el_cliente(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        sesion = (await c.post("/auth/alta", json={"correo": "ana@mail.com", "contrasena": "clave-1",
                                                   "region": "amer"})).json()
        token = {"Authorization": f"Bearer {sesion['token_acceso']}"}
        r = await c.post("/correo/autorizacion", json={"token": "tok"}, headers={**token, "X-Titular-Id": "victima"})
        assert r.status_code == 201 and r.json()["titular_id"] == sesion["cuenta_id"]
    gestor = app.state.gestor_correo
    assert gestor.token_vigente("victima") is None
    assert gestor.token_vigente(sesion["cuenta_id"]) == "tok"


@pytestmark_db
async def test_el_regreso_de_google_llega_al_manejador_sin_token(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/correo/oauth/callback", params={"code": "c", "state": "inventado"})
        assert r.status_code == 400 and r.json() == {"detail": "autorización rechazada"}  # no un 401 del Gateway
        assert (await c.post("/correo/oauth/iniciar")).status_code == 401  # iniciar sí pide token
