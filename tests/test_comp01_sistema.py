# SPEC: SPEC-COMP-01
# ELEMENTO PASO 5: Broker, consumidores y composición (ITERACION_3, ITERACION_5)
# ADRs: ADR-IT3-001, ADR-IT3-002, ADR-IT5-001
# DRIVERS: REF-05, REF-06, CON-01
"""El sistema armado por `create_app`, con su ciclo de vida real (consumidores incluidos)."""
import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime

import httpx
import pytest

from tests.ref04_util import ANA, ITIN, LUIS, precargar, solicitud
from trotamundos.app import create_app
from trotamundos.config import Configuracion, ConfiguracionAgencias, ConfiguracionAnalitica, ConfiguracionBroker
from trotamundos.dominio.agencias import EstadoCaso

pytestmark = pytest.mark.db
CLAVE_AGENCIA = "clave-compartida"


async def esperar(condicion, tiempo=5.0):
    for _ in range(int(tiempo / 0.02)):
        resultado = condicion()
        if asyncio.iscoroutine(resultado):
            resultado = await resultado
        if resultado:
            return resultado
        await asyncio.sleep(0.02)
    raise AssertionError("no se cumplió la condición a tiempo")


@pytest.fixture
async def sistema(bases_limpias, analitica_limpia):
    cfg = Configuracion(
        bases=bases_limpias, analitica=analitica_limpia,
        broker=ConfiguracionBroker(tamano_maximo_cola=50, reintentos=3, backoff_base_segundos=0.01),
        agencias=ConfiguracionAgencias(disponibles=("agencia-a",), clave_aviso=CLAVE_AGENCIA))
    app = create_app(cfg)
    precargar(app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as http:
            app.state.http = http
            yield app


def h(actor, clave=None):
    cabeceras = {"X-Viajero-Id": actor}
    if clave:
        cabeceras["X-Clave-Operacion"] = clave
    return cabeceras


async def test_AC_COMP_01_01_caso_avanza_sin_invocar_procesar_uno(sistema):
    http = sistema.state.http
    ra = await sistema.state.gestion.agregar(LUIS, ITIN, "r1", solicitud(viaje_id="roma"))
    reserva = ra.reserva["identificador"]
    r = await http.put("/agencia-preferida", headers=h(LUIS), json={"agencia": "agencia-a", "consentimiento": True})
    assert r.status_code == 200
    r = await http.post("/casos", headers=h(LUIS, "caso:1"),
                        json={"itinerario_id": ITIN, "reserva_id": reserva, "descripcion": "hotel cerrado"})
    assert r.status_code in (200, 201), r.text
    agencia = sistema.state.adaptador_agencia.agencias["agencia-a"]
    await esperar(lambda: len(agencia.pedidos) == 1)  # lo entregó el consumidor, no el test
    id_caso = agencia.pedidos[0].id_caso
    agencia.cambiar_estado(id_caso, EstadoCaso.EN_CURSO)
    r = await http.post("/agencia/agencia-a/avisos", json={"id_caso": id_caso},
                        headers={"X-Clave-Agencia": CLAVE_AGENCIA})
    assert r.status_code == 200

    async def estado():
        return (await http.get("/casos", headers=h(LUIS))).json()[0]["estado"]
    await esperar(estado_es(estado, "en_curso"))


def estado_es(obtener, esperado):
    async def comprobar():
        return await obtener() == esperado
    return comprobar


async def test_AC_COMP_01_02_reserva_llega_al_informe(sistema, analitica_limpia):
    http = sistema.state.http
    r = await http.post(f"/itinerarios/{ITIN}/reservas", headers=h(LUIS, "k1"), json={
        "viaje_id": "roma", "tipo": "hotel", "inicio": "2027-01-10T14:00:00+00:00",
        "fin": "2027-01-12T10:00:00+00:00", "lugar": "Coliseo", "datos": {"codigo": "H1"}})
    assert r.status_code == 201, r.text
    hoy = datetime.now(UTC).date()
    ruta = f"/analitica/informe?desde={date(hoy.year, 1, 1)}&hasta={date(hoy.year, 12, 31)}"

    async def con_datos():
        informe = (await http.get(ruta, headers=h("analista"))).json()
        return informe if informe.get("destinos") else None
    informe = await esperar(con_datos)
    assert informe["destinos"] == [{"destino": "Coliseo", "reservas": 1}]


async def test_AC_COMP_01_04_openapi_expone_todos_los_endpoints(sistema):
    rutas = (await sistema.state.http.get("/openapi.json")).json()["paths"]
    for esperada in ("/asistente/turno", "/asistente/accion", "/analitica/informe", "/correo/autorizacion",
                     "/agencia/{agencia}/avisos", "/viajes", "/itinerarios", "/casos", "/revision",
                     "/itinerarios/{itinerario_id}/miembros"):
        assert esperada in rutas, esperada


async def test_AC_COMP_01_05_analitica_caida_no_impide_operar(bases_limpias):
    caida = ConfiguracionAnalitica(dsn="postgresql://trotamundos:trotamundos@localhost:5999/nada")
    app = create_app(Configuracion(bases=bases_limpias, analitica=caida))
    precargar(app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as http:
            r = await http.post(f"/itinerarios/{ITIN}/reservas", headers=h(LUIS, "k1"), json={
                "viaje_id": "roma", "tipo": "hotel", "inicio": "2027-01-10T14:00:00+00:00",
                "fin": "2027-01-12T10:00:00+00:00", "lugar": "Coliseo", "datos": {"codigo": "H1"}})
            assert r.status_code == 201
            informe = await http.get("/analitica/informe?desde=2027-01-01&hasta=2027-12-31", headers=h("analista"))
            assert informe.status_code == 503
            assert (await http.get("/salud")).json() == {"estado": "ok"}


async def test_AC_COMP_01_09_tipo_uniforme(sistema):
    http = sistema.state.http
    r = await http.post(f"/itinerarios/{ITIN}/reservas", headers=h(LUIS, "k1"), json={
        "viaje_id": "roma", "tipo": "hotel", "inicio": "2027-01-10T14:00:00+00:00",
        "fin": "2027-01-12T10:00:00+00:00", "lugar": "Coliseo", "datos": {"codigo": "H1"}})
    al_crear = r.json()["reserva"]["tipo"]
    en_itinerario = (await http.get(f"/itinerarios/{ITIN}", headers=h(LUIS))).json()[0]["reservas"][0]["tipo"]
    en_vista = (await http.get("/viajes", headers=h(LUIS))).json()
    en_vista = en_vista[0]["reservas"][0]["tipo"] if en_vista else "hotel"
    assert al_crear == en_itinerario == en_vista == "hotel"


async def test_AC_COMP_01_10_los_tests_no_tocan_la_base_de_desarrollo(bases_limpias):
    assert bases_limpias.viajes_primaria.endswith("/trotamundos_test")
    assert bases_limpias.viajes_pasiva.endswith("/trotamundos_test")
    assert ConfiguracionAnalitica().dsn.endswith("/trotamundos_test")
    from tests.conftest import limpiar_base
    dsn_dev = bases_limpias.viajes_primaria.replace("trotamundos_test", "trotamundos_dev")
    with pytest.raises(RuntimeError, match="se niegan a borrar"):
        limpiar_base(dsn_dev)
