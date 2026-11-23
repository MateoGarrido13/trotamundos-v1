# SPEC: SPEC-COMP-01
# ELEMENTO PASO 5: Orquestador de viajes, control de acceso y auditoría (ITERACION_4)
# ADRs: ADR-IT4-007, ADR-IT4-008
# DRIVERS: REF-04, QA-SEG-02
import httpx
import pytest

from tests.ref04_util import ANA, ITIN, LUIS
from trotamundos.app import create_app
from trotamundos.config import Configuracion
from trotamundos.persistencia.repositorio_gestion import RepositorioGestion

pytestmark = pytest.mark.db


@pytest.fixture
async def http(bases_limpias):
    app = create_app(Configuracion(bases=bases_limpias))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as cliente:
        cliente.app = app
        yield cliente


def h(actor, clave="k1"):
    return {"X-Viajero-Id": actor, "X-Clave-Operacion": clave}


def asientos(http, itinerario):
    return http.app.state.base_viajes.leer(lambda c: RepositorioGestion.asientos(c, itinerario))


async def test_AC_COMP_01_06_crear_viaje_sin_itinerario_hace_organizador(http):
    r = await http.post("/viajes", headers=h("sofia"), json={"nombre": "Italia 2027"})
    assert r.status_code == 201, r.text
    datos = r.json()
    assert datos["viaje_id"].startswith("viaje-") and datos["nombre"] == "Italia 2027"
    miembros = (await http.get(f"/itinerarios/{datos['itinerario_id']}/miembros", headers=h("sofia"))).json()
    assert miembros == [{"cuenta": "sofia", "rol": "organizador"}]
    assert (await http.get("/itinerarios", headers=h("sofia"))).json() == [
        {"id": datos["itinerario_id"], "rol": "organizador"}]
    assert [(a["cuenta"], a["operacion"], a["resultado"]) for a in asientos(http, datos["itinerario_id"])] == [
        ("sofia", "crear_viaje", "permitido")]
    # y desde el itinerario ya se pueden registrar reservas en ese viaje
    r = await http.post(f"/itinerarios/{datos['itinerario_id']}/reservas", headers=h("sofia", "k2"), json={
        "viaje_id": datos["viaje_id"], "tipo": "hotel", "inicio": "2027-01-10T14:00:00+00:00",
        "fin": "2027-01-12T10:00:00+00:00", "lugar": "Roma", "datos": {"codigo": "H1"}})
    assert r.status_code == 201


async def _con_itinerario(http):
    datos = (await http.post("/viajes", headers=h(ANA, "alta"), json={"nombre": "Familia"})).json()
    return datos["itinerario_id"]


async def test_AC_COMP_01_07_participante_no_agrega_miembros(http):
    itin = await _con_itinerario(http)
    ok = await http.post(f"/itinerarios/{itin}/miembros", headers=h(ANA, "m1"), json={"cuenta": LUIS, "rol": "participante"})
    assert ok.status_code == 200, ok.text
    r = await http.post(f"/itinerarios/{itin}/miembros", headers=h(LUIS, "m2"), json={"cuenta": "tercero", "rol": "participante"})
    assert r.status_code == 403 and r.json() == {"error": "acceso_denegado"}
    assert "tercero" not in [m["cuenta"] for m in (await http.get(f"/itinerarios/{itin}/miembros", headers=h(ANA))).json()]
    assert [(a["cuenta"], a["operacion"], a["resultado"]) for a in asientos(http, itin)][-1] == (
        LUIS, "agregar_miembro", "denegado")
    # quitar tampoco
    r = await http.delete(f"/itinerarios/{itin}/miembros/{ANA}", headers=h(LUIS, "m3"))
    assert r.status_code == 403


async def test_AC_COMP_01_08_no_se_quita_al_ultimo_organizador(http):
    itin = await _con_itinerario(http)
    r = await http.delete(f"/itinerarios/{itin}/miembros/{ANA}", headers=h(ANA, "q1"))
    assert r.status_code == 409 and r.json() == {"error": "ultimo_organizador"}
    r = await http.post(f"/itinerarios/{itin}/miembros", headers=h(ANA, "q2"), json={"cuenta": ANA, "rol": "participante"})
    assert r.status_code == 409  # degradarse también deja al itinerario sin organizador
    miembros = (await http.get(f"/itinerarios/{itin}/miembros", headers=h(ANA))).json()
    assert miembros == [{"cuenta": ANA, "rol": "organizador"}]
    # con un segundo organizador sí se puede
    await http.post(f"/itinerarios/{itin}/miembros", headers=h(ANA, "q3"), json={"cuenta": LUIS, "rol": "organizador"})
    r = await http.delete(f"/itinerarios/{itin}/miembros/{ANA}", headers=h(LUIS, "q4"))
    assert r.status_code == 200
    r = await http.delete(f"/itinerarios/{itin}/miembros/{ANA}", headers=h(LUIS, "q5"))
    assert r.status_code == 404  # ya no es miembro


async def test_AC_COMP_01_11_clave_repetida_no_duplica_viaje(http):
    primera = await http.post("/viajes", headers=h(ANA, "misma"), json={"nombre": "Uno"})
    segunda = await http.post("/viajes", headers=h(ANA, "misma"), json={"nombre": "Otro nombre"})
    assert primera.status_code == 201 and segunda.status_code == 200
    assert segunda.json()["viaje_id"] == primera.json()["viaje_id"] and segunda.json()["repetida"] is True
    assert len((await http.get("/itinerarios", headers=h(ANA))).json()) == 1


async def test_AC_COMP_01_13_itinerario_ajeno_igual_que_inexistente(http):
    ajeno = await _con_itinerario(http)
    r1 = await http.post("/viajes", headers=h("intruso", "x1"), json={"nombre": "Colado", "itinerario_id": ajeno})
    r2 = await http.post("/viajes", headers=h("intruso", "x2"), json={"nombre": "Colado", "itinerario_id": "no-existe"})
    assert (r1.status_code, r1.json()) == (r2.status_code, r2.json()) == (403, {"error": "acceso_denegado"})


async def test_crear_viaje_valida_el_nombre_y_el_rol(http):
    assert (await http.post("/viajes", headers=h(ANA, "n1"), json={"nombre": "  "})).status_code == 422
    assert (await http.post("/viajes", headers=h(ANA, "n2"), json={})).status_code == 422
    itin = await _con_itinerario(http)
    r = await http.post(f"/itinerarios/{itin}/miembros", headers=h(ANA, "n3"), json={"cuenta": LUIS, "rol": "dios"})
    assert r.status_code == 422 and r.json() == {"error": "rol_invalido"}
