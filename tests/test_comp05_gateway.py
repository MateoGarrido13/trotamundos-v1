# SPEC: SPEC-COMP-05
# ELEMENTO PASO 5: API Gateway y Seguridad del login (ITERACION_4)
# ADRs: ADR-008, ADR-IT4-004, ADR-IT4-005, ADR-IT4-006
# DRIVERS: QA-SEG-01, QA-ESC-01
"""El sistema armado con `exigir_gateway`: validación local del token, firma de identidad y ráfaga."""
import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI, Header

from tests.comp05_util import Reloj
from trotamundos.app import create_app
from trotamundos.broker import NombreCola
from trotamundos.config import Configuracion
from trotamundos.identidad.gateway.firma import firmar
from trotamundos.identidad.gateway.gateway import Gateway
from trotamundos.identidad.gateway.limitador import LimitadorTasa
from trotamundos.identidad.tokens import EmisorTokens, ValidadorTokens, clave_publica_hex

pytestmark = pytest.mark.db
SECRETO = "secreto-del-gateway"


def cliente(app, origen=("10.0.0.1", 5000)):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=origen), base_url="http://t")


@pytest.fixture
def cfg(cuentas_limpias, bases_limpias, analitica_limpia):
    return Configuracion(bases=bases_limpias, analitica=analitica_limpia,
                         identidad=replace(cuentas_limpias, exigir_gateway=True))


@pytest.fixture
async def app(cfg):
    sistema = create_app(cfg)
    yield sistema
    sistema.state.red_regiones.cerrar()


async def alta(c, correo="ana@mail.com", region="amer", contrasena="clave-1"):
    r = await c.post("/auth/alta", json={"correo": correo, "contrasena": contrasena, "region": region})
    assert r.status_code == 201, r.text
    return r.json()


def con_token(sesion):
    return {"Authorization": f"Bearer {sesion['token_acceso']}"}


async def test_AC_COMP_05_02_el_alta_por_http_trae_la_sesion_y_opera_sin_login(app):
    async with cliente(app) as c:
        sesion = await alta(c)
        assert sesion["cuenta_id"].startswith("amer-")
        r = await c.get("/viajes", headers=con_token(sesion))  # opera sin un login aparte
        assert r.status_code == 200


async def test_AC_COMP_05_05_el_gateway_valida_sin_llamar_a_ninguna_region(app):
    async with cliente(app) as c:
        sesion = await alta(c)

        class RegionCaida:
            def __getattr__(self, nombre):
                if nombre == "cerrar_conexiones":  # lo consulta el cierre de la fixture, no el Gateway
                    raise AttributeError(nombre)
                raise AssertionError(f"el Gateway llamó a una región: {nombre}")

        for servicio in app.state.servicios_identidad.values():
            servicio._base = RegionCaida()
        r = await c.get("/viajes", headers=con_token(sesion))
        assert r.status_code == 200  # el usuario con token vigente sigue siendo atendido


def _app_minima(emisor_reg="amer"):
    """Un Core de juguete detrás del Gateway real, para contar cuántos pedidos llegan."""
    semilla = "07" * 32
    llegaron = []
    nucleo = FastAPI()

    @nucleo.get("/algo")
    def algo(x_viajero_id: str = Header()):
        llegaron.append(x_viajero_id)
        return {"quien": x_viajero_id}

    reloj = Reloj()
    nucleo.add_middleware(Gateway, validador=ValidadorTokens({"amer": clave_publica_hex(semilla)}),
                          limitador=LimitadorTasa({}), secreto=SECRETO, reloj=reloj)
    emisor = EmisorTokens("amer", semilla, timedelta(minutes=15))
    return nucleo, emisor, reloj, llegaron


async def test_AC_COMP_05_06_token_alterado_o_vencido_no_llega_al_core():
    nucleo, emisor, reloj, llegaron = _app_minima()
    bueno = emisor.emitir("amer-1", reloj())
    async with cliente(nucleo) as c:
        assert (await c.get("/algo", headers={"Authorization": f"Bearer {bueno}"})).json() == {"quien": "amer-1"}
        cuerpo, firma = bueno.split(".")
        alterado = f"{cuerpo}.{'A' + firma[1:]}"
        otro_cuerpo = emisor.emitir("amer-2", reloj()).split(".")[0]
        for malo in (alterado, f"{otro_cuerpo}.{firma}", "basura", ""):
            r = await c.get("/algo", headers={"Authorization": f"Bearer {malo}"})
            assert r.status_code == 401
        assert (await c.get("/algo")).status_code == 401  # sin token
        reloj.avanzar(minutes=16)  # vencido
        assert (await c.get("/algo", headers={"Authorization": f"Bearer {bueno}"})).status_code == 401
    assert llegaron == ["amer-1"]  # los rechazados nunca llegaron


async def test_AC_COMP_05_06_el_gateway_ignora_el_x_viajero_id_del_cliente():
    nucleo, emisor, reloj, llegaron = _app_minima()
    async with cliente(nucleo) as c:
        r = await c.get("/algo", headers={"Authorization": f"Bearer {emisor.emitir('amer-1', reloj())}",
                                          "X-Viajero-Id": "otra-cuenta"})
        assert r.json() == {"quien": "amer-1"}


async def test_AC_COMP_05_07_pedido_directo_al_core_con_identidad_se_rechaza(cfg):
    core = create_app(cfg, con_gateway=False)  # el Core sin Gateway delante
    try:
        async with cliente(core) as c:
            assert (await c.get("/viajes", headers={"X-Viajero-Id": "ana"})).status_code == 401
            falsa = {"X-Viajero-Id": "ana", "X-Gateway-Firma": firmar("otro-secreto", "ana")}
            assert (await c.get("/viajes", headers=falsa)).status_code == 401
            firmada = {"X-Viajero-Id": "ana",
                       "X-Gateway-Firma": firmar(cfg.identidad.clave_gateway, "ana")}
            assert (await c.get("/viajes", headers=firmada)).status_code == 200  # solo la firma lo habilita
    finally:
        core.state.red_regiones.cerrar()


async def test_AC_COMP_05_07_con_el_gateway_delante_el_cliente_no_puede_inventar_identidad(app):
    async with cliente(app) as c:
        r = await c.get("/viajes", headers={"X-Viajero-Id": "ana"})
        assert r.status_code == 401  # sin token de acceso


async def test_AC_COMP_05_08_rafaga_de_50_recuperaciones(app):
    async with cliente(app) as c:
        await alta(c, "ana@mail.com")
        await alta(c, "luis@mail.com", contrasena="clave-luis")
    cuerpo = {"correo": "ana@mail.com", "region": "amer"}
    broker = app.state.broker

    # Fase 1: los 50 pedidos salen de un mismo origen y, entre medio, un usuario legítimo hace login.
    async with cliente(app, ("10.9.9.9", 1)) as atacante, cliente(app, ("10.1.1.1", 1)) as legitimo:
        tareas = [atacante.post("/auth/recuperacion", json=cuerpo) for _ in range(50)]
        tareas.append(legitimo.post("/auth/login", json={"correo": "luis@mail.com",
                                                          "contrasena": "clave-luis", "region": "amer"}))
        respuestas = await asyncio.gather(*tareas)
    recuperaciones, login = respuestas[:-1], respuestas[-1]
    assert login.status_code == 200  # el login sigue disponible
    estados = {r.status_code for r in recuperaciones}
    assert estados <= {202, 429}
    assert sum(r.status_code == 202 for r in recuperaciones) <= app.state.configuracion.identidad.cupo_recuperacion
    assert all(r.json() == recuperaciones[0].json() for r in recuperaciones if r.status_code == 202)
    assert any(r.status_code == 429 for r in recuperaciones)
    assert app.state.limitador.rechazos  # el evento queda registrado
    # Un solo correo con código salió: un único pedido vigente por cuenta.
    assert broker.tamano_actual(NombreCola.NOTIFICACIONES) == 1

    # Fase 2: 50 orígenes distintos, así que la tasa por origen no frena a ninguno. Pasa uno como máximo.
    ana = app.state.servicios_identidad["amer"]
    ana.solicitar_recuperacion("ana@mail.com")  # no cambia nada: ya hay uno vigente
    tareas = []
    for i in range(50):
        c = cliente(app, (f"10.2.0.{i}", 1))
        tareas.append(c.post("/auth/recuperacion", json=cuerpo))
    respuestas = await asyncio.gather(*tareas)
    assert {r.status_code for r in respuestas} == {202}
    vigentes = ana._base.leer(lambda c: c.execute("SELECT count(*) FROM recuperacion WHERE NOT usado").fetchone()[0])
    assert vigentes == 1
    codigos = [m for m in broker._colas[NombreCola.NOTIFICACIONES] if "código" in m.cuerpo["propuesta"]["cuerpo"]]
    assert len(codigos) == 1  # ningún correo adicional


async def test_AC_COMP_05_09_respuesta_uniforme_exista_o_no_la_cuenta(app):
    async with cliente(app) as c:
        await alta(c)
        existente = await c.post("/auth/recuperacion", json={"correo": "ana@mail.com", "region": "amer"})
        inexistente = await c.post("/auth/recuperacion", json={"correo": "nadie@mail.com", "region": "amer"})
    assert (existente.status_code, existente.json()) == (inexistente.status_code, inexistente.json())
    assert existente.headers["content-type"] == inexistente.headers["content-type"]


async def test_login_y_recuperacion_por_http(app):
    async with cliente(app) as c:
        sesion = await alta(c)
        assert (await c.post("/auth/login", json={"correo": "ana@mail.com", "contrasena": "mala",
                                                  "region": "amer"})).status_code == 401
        r = await c.post("/auth/renovar", json={"token_renovacion": sesion["token_renovacion"]})
        assert r.status_code == 200 and r.json()["token_acceso"]
        await c.post("/auth/recuperacion", json={"correo": "ana@mail.com", "region": "amer"})
        mensaje = app.state.broker._colas[NombreCola.NOTIFICACIONES][0].cuerpo
        token = mensaje["propuesta"]["cuerpo"].rsplit(": ", 1)[-1]
        assert (await c.post("/auth/recuperacion/completar",
                             json={"token": token, "contrasena": "nueva-1"})).status_code == 204
        assert (await c.post("/auth/recuperacion/completar",
                             json={"token": token, "contrasena": "otra"})).status_code == 400
        assert (await c.post("/auth/renovar", json={"token_renovacion": sesion["token_renovacion"]})
                ).status_code == 401
        assert (await c.post("/auth/cerrar-sesion", json={"token_renovacion": "x.y"})).status_code == 204
        assert (await c.post("/auth/alta", json={"correo": "ana@mail.com", "contrasena": "x",
                                                 "region": "emea"})).status_code == 409
        assert (await c.post("/auth/alta", json={"correo": "malo", "contrasena": "x",
                                                 "region": "emea"})).status_code == 422
        assert (await c.post("/auth/alta", json={"correo": "a@b.com", "contrasena": "x",
                                                 "region": "luna"})).status_code == 422


async def test_el_login_con_demasiados_pedidos_responde_429(app):
    async with cliente(app) as c:
        cuerpo = {"correo": "nadie@mail.com", "contrasena": "x", "region": "amer"}
        estados = [(await c.post("/auth/login", json=cuerpo)).status_code for _ in range(12)]
    assert estados[:10] == [401] * 10 and estados[10:] == [429, 429]
