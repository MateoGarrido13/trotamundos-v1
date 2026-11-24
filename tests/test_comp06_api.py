# SPEC: SPEC-COMP-06 | PLAN-COMP-06 T-COMP-06-06
import httpx
import pytest
from fastapi import FastAPI

from tests.comp06_util import Cronometro, borde_con, sistema
from trotamundos.cotizacion.api import crear_router

URL = "/cotizaciones"
OK = {"fecha": "2027-01-10", "hospedaje": "hotel", "compania": "familia"}


@pytest.fixture
def montaje():
    sis = sistema()
    app = FastAPI()
    app.include_router(crear_router(borde_con(sis)))
    cliente = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
    return sis, cliente


async def test_AC_COMP_06_01_extremo_a_extremo_la_cotizacion_responde_la_grilla_completa(montaje):
    sis, cliente = montaje
    for api in sis.apis.values():
        api.demora_segundos = 0.15
    with Cronometro() as t:
        r = await cliente.get(URL, params=OK)
    assert r.status_code == 200 and t.segundos < 0.8
    cuerpo = r.json()
    assert set(cuerpo) == {"origenes", "completa", "copia", "en_curso"}
    assert cuerpo["completa"] and not cuerpo["copia"] and not cuerpo["en_curso"]
    assert {o["proveedor"] for o in cuerpo["origenes"]} == {"aerolineas", "hoteles", "arrendadoras"}
    assert cuerpo["origenes"][0]["precios"][0]["moneda"] == "USD"


async def test_segundo_pedido_igual_sale_de_la_copia(montaje):
    _, cliente = montaje
    await cliente.get(URL, params=OK)
    assert (await cliente.get(URL, params=OK)).json()["copia"] is True


@pytest.mark.parametrize("params", [
    {**OK, "fecha": "no-es-fecha"},
    {**OK, "fecha": "2027-13-40"},
    {"hospedaje": "hotel", "compania": "familia"},
    {**OK, "hospedaje": ""},
    {**OK, "compania": "   "},
    {**OK, "hospedaje": "x" * 101},
])
async def test_parametros_invalidos_son_422(montaje, params):
    _, cliente = montaje
    assert (await cliente.get(URL, params=params)).status_code == 422


def test_la_app_principal_expone_la_cotizacion():
    from trotamundos.app import create_app

    app = create_app()
    assert "/cotizaciones" in app.openapi()["paths"]
    assert app.state.cotizacion.balanceador.nodos_sanos == ["cotizacion-1", "cotizacion-2"]
