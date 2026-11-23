# SPEC: SPEC-REF-05
# ELEMENTO PASO 5: Orquestador, cola de casos, Adaptador de agencia, ingesta (ITERACION_4)
# ADRs: ADR-IT4-010, ADR-IT3-003
# DRIVERS: REF-05, CON-02
"""T-REF-05-08: del reporte del viajero a «resuelto», por el camino completo y las bases reales."""
import httpx
import pytest
from fastapi import FastAPI

from tests.ref04_util import ITIN, LUIS
from tests.ref05_util import CLAVE_AGENCIA, app, reserva_de  # noqa: F401
from trotamundos.broker import NombreCola, ResultadoEntrega
from trotamundos.dominio.agencias import EstadoCaso
from trotamundos.entrada import api_agencia

pytestmark = pytest.mark.db


def cab(clave="k1"):
    return {"X-Viajero-Id": LUIS, "X-Clave-Operacion": clave}


@pytest.fixture
async def viajero(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://orquestador") as c:
        yield c


@pytest.fixture
async def agencia_llama(app):
    """El listener del Adaptador, como lo vería la agencia."""
    nodo = FastAPI()
    nodo.include_router(api_agencia.crear_router(app.state.adaptador_agencia))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=nodo), base_url="http://entrada") as c:
        yield c


async def estado_visible(viajero):
    [caso] = (await viajero.get("/casos", headers=cab())).json()
    return caso["estado"]


async def circular(app):
    """El Adaptador entrega los pedidos y la ingesta le pasa los cambios al Orquestador."""
    while await app.state.adaptador_agencia.procesar_uno() is not ResultadoEntrega.VACIA:
        pass
    while await app.state.nodos_correo.ingesta.procesar_uno() is not ResultadoEntrega.VACIA:
        pass


async def test_AC_REF_05_05_del_reporte_a_resuelto_por_el_camino_completo(app, viajero, agencia_llama):
    ident = await reserva_de(app)
    await viajero.put("/agencia-preferida", json={"agencia": "agencia-a", "consentimiento": True}, headers=cab())
    r = await viajero.post("/casos", json={"itinerario_id": ITIN, "reserva_id": ident,
                                           "descripcion": "Me cancelaron el hotel"}, headers=cab())
    caso_id = r.json()["caso"]["id"]
    assert await estado_visible(viajero) == "en_tramite"  # el viajero ve «en trámite» enseguida

    await app.state.casos.esperar_publicaciones()
    agencia = app.state.adaptador_agencia.agencias["agencia-a"]
    await circular(app)  # el Adaptador llama a abrirCaso
    assert caso_id in agencia.casos and agencia.pedidos[0].descripcion == "Me cancelaron el hotel"
    assert agencia.pedidos[0].reserva["identificador"] == ident

    for estado in (EstadoCaso.ABIERTO, EstadoCaso.EN_CURSO, EstadoCaso.RESUELTO):
        agencia.cambiar_estado(caso_id, estado)  # la agencia trabaja y avisa
        aviso = await agencia_llama.post("/agencia/agencia-a/avisos", json={"id_caso": caso_id},
                                         headers={"X-Clave-Agencia": CLAVE_AGENCIA})
        assert aviso.json() == {"resultado": "publicado"}
        await circular(app)
        assert await estado_visible(viajero) == estado.value  # lo ve en «Novedades»
    assert app.state.broker.mensajes_muertos(NombreCola.CASOS_AYUDA) == []
    assert app.state.broker.mensajes_muertos(NombreCola.NOVEDADES) == []


async def test_AC_REF_05_16_una_segunda_agencia_atiende_sin_cambios_en_el_orquestador(app, viajero):
    ident = await reserva_de(app)
    await viajero.put("/agencia-preferida", json={"agencia": "agencia-b", "consentimiento": True}, headers=cab())
    caso_id = (await viajero.post("/casos", json={"itinerario_id": ITIN, "reserva_id": ident,
                                                  "descripcion": "Problema"}, headers=cab())).json()["caso"]["id"]
    await app.state.casos.esperar_publicaciones()
    await circular(app)
    a, b = (app.state.adaptador_agencia.agencias[n] for n in ("agencia-a", "agencia-b"))
    assert list(b.casos) == [caso_id] and list(a.casos) == []  # solo la agencia elegida recibió el pedido


async def test_un_caso_que_la_agencia_nunca_recibe_termina_sin_entregar_y_se_puede_reintentar(app, viajero):
    ident = await reserva_de(app)
    await viajero.put("/agencia-preferida", json={"agencia": "agencia-a", "consentimiento": True}, headers=cab())
    caso_id = (await viajero.post("/casos", json={"itinerario_id": ITIN, "reserva_id": ident,
                                                  "descripcion": "Problema"}, headers=cab())).json()["caso"]["id"]
    await app.state.casos.esperar_publicaciones()
    agencia = app.state.adaptador_agencia.agencias["agencia-a"]
    agencia.caida = True
    await circular(app)
    assert await estado_visible(viajero) == "sin_entregar"  # visible en «Novedades»

    agencia.caida = False
    r = await viajero.post(f"/casos/{caso_id}/reintentar", json={"itinerario_id": ITIN}, headers=cab("reintento"))
    assert r.status_code == 200
    await app.state.casos.esperar_publicaciones()
    await circular(app)
    assert list(agencia.casos) == [caso_id] and await estado_visible(viajero) == "en_tramite"
