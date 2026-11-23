# SPEC: SPEC-REF-05
# ELEMENTO PASO 5: Orquestador de viajes, casos de ayuda, endpoints (ITERACION_4)
# ADRs: ADR-IT4-010, ADR-IT4-007, ADR-IT4-008
# DRIVERS: REF-05
"""T-REF-05-08: los endpoints del viajero y sus códigos, con las bases reales."""
import httpx
import pytest

from tests.ref04_util import INTRUSO, ITIN, LUIS, contar
from tests.ref05_util import app, llenar_cola_de_casos, reserva_de, vaciar_un_lugar  # noqa: F401

pytestmark = pytest.mark.db


@pytest.fixture
async def cliente(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c


def cab(actor=LUIS, clave="k1"):
    return {"X-Viajero-Id": actor, "X-Clave-Operacion": clave}


async def listo(cliente, app, actor=LUIS, agencia="agencia-a"):
    ident = await reserva_de(app, actor=actor if actor != INTRUSO else LUIS)
    r = await cliente.put("/agencia-preferida", json={"agencia": agencia, "consentimiento": True}, headers=cab(actor))
    assert r.status_code == 200
    return ident


def cuerpo(ident, **extra):
    return {"itinerario_id": ITIN, "reserva_id": ident, "descripcion": "El hotel no tiene mi reserva", **extra}


async def test_elegir_agencia_exige_consentimiento_y_una_agencia_registrada(cliente):
    r = await cliente.put("/agencia-preferida", json={"agencia": "agencia-a", "consentimiento": False}, headers=cab())
    assert (r.status_code, r.json()) == (422, {"error": "sin_consentimiento"})
    r = await cliente.put("/agencia-preferida", json={"agencia": "otra", "consentimiento": True}, headers=cab())
    assert (r.status_code, r.json()) == (422, {"error": "agencia_no_registrada"})
    r = await cliente.put("/agencia-preferida", json={"agencia": "agencia-b", "consentimiento": True}, headers=cab())
    assert r.status_code == 200


async def test_AC_REF_05_01_reportar_responde_201_en_tramite_sin_esperar_a_la_agencia(cliente, app):
    ident = await listo(cliente, app)
    r = await cliente.post("/casos", json=cuerpo(ident, resumen_dialogo="Resumen del asistente"), headers=cab())
    assert r.status_code == 201
    caso = r.json()["caso"]
    assert (caso["estado"], caso["agencia"], caso["resumen_dialogo"]) == ("en_tramite", "agencia-a", "Resumen del asistente")
    await app.state.casos.esperar_publicaciones()
    assert app.state.broker.tamano_actual("casos_ayuda") == 1


async def test_AC_REF_05_09_el_doble_toque_no_abre_un_segundo_caso_por_http(cliente, app, bases_limpias):
    ident = await listo(cliente, app)
    a = await cliente.post("/casos", json=cuerpo(ident), headers=cab(clave="k1"))
    b = await cliente.post("/casos", json=cuerpo(ident), headers=cab(clave="k1"))
    assert b.status_code == 201 and b.json()["repetida"] is True and b.json()["caso"] == a.json()["caso"]
    assert contar(bases_limpias, "caso") == [1, 1]
    await app.state.casos.esperar_publicaciones()


async def test_AC_REF_05_08_sin_permiso_responde_403_y_no_crea_el_caso(cliente, app, bases_limpias):
    ident = await listo(cliente, app)
    await cliente.put("/agencia-preferida", json={"agencia": "agencia-a", "consentimiento": True}, headers=cab(INTRUSO))
    r = await cliente.post("/casos", json=cuerpo(ident), headers=cab(INTRUSO))
    assert (r.status_code, r.json()) == (403, {"error": "acceso_denegado"})
    assert contar(bases_limpias, "caso") == [0, 0]
    # el permiso se verifica antes que los datos: un cuerpo inválido sin permiso también es 403
    r = await cliente.post("/casos", json=cuerpo("no-existe", descripcion=""), headers=cab(INTRUSO, "k2"))
    assert r.status_code == 403


async def test_los_rechazos_tienen_su_codigo(cliente, app):
    ident = await reserva_de(app)
    r = await cliente.post("/casos", json=cuerpo(ident), headers=cab(clave="a"))  # sin agencia
    assert (r.status_code, r.json()) == (409, {"error": "sin_agencia_o_consentimiento"})
    await cliente.put("/agencia-preferida", json={"agencia": "agencia-a", "consentimiento": True}, headers=cab())
    assert (await cliente.post("/casos", json=cuerpo("no-existe"), headers=cab(clave="b"))).status_code == 404
    assert (await cliente.post("/casos", json=cuerpo(ident, descripcion=" "), headers=cab(clave="c"))).status_code == 422


async def test_faltan_datos_o_el_cuerpo_no_es_un_objeto_responde_422(cliente):
    assert (await cliente.post("/casos", json=[1], headers=cab())).status_code == 422
    assert (await cliente.post("/casos", json={"reserva_id": "r"}, headers=cab())).status_code == 422
    assert (await cliente.post("/casos", json={"itinerario_id": ITIN})).status_code == 422  # sin identidad ni clave
    assert (await cliente.put("/agencia-preferida", json={"agencia": "a"})).status_code == 422
    assert (await cliente.get("/casos")).status_code == 422


async def test_AC_REF_05_12_y_13_reintentar_por_http(cliente, app):
    ident = await listo(cliente, app)
    llenar_cola_de_casos(app)
    caso_id = (await cliente.post("/casos", json=cuerpo(ident), headers=cab())).json()["caso"]["id"]
    await app.state.casos.esperar_publicaciones()  # la cola no tuvo lugar: queda «sin entregar»
    assert [c["estado"] for c in (await cliente.get("/casos", headers=cab())).json()] == ["sin_entregar"]

    vaciar_un_lugar(app)
    r = await cliente.post(f"/casos/{caso_id}/reintentar", json={"itinerario_id": ITIN}, headers=cab(clave="r1"))
    assert (r.status_code, r.json()["caso"]["estado"]) == (200, "en_tramite")
    await app.state.casos.esperar_publicaciones()
    # ya no está «sin entregar»: reintentar de nuevo se rechaza sin efecto
    r = await cliente.post(f"/casos/{caso_id}/reintentar", json={"itinerario_id": ITIN}, headers=cab(clave="r2"))
    assert (r.status_code, r.json()) == (409, {"error": "estado_invalido"})
    r = await cliente.post("/casos/no-existe/reintentar", json={"itinerario_id": ITIN}, headers=cab(clave="r3"))
    assert r.status_code == 404
    r = await cliente.post(f"/casos/{caso_id}/reintentar", json={"itinerario_id": ITIN}, headers=cab(INTRUSO, "r4"))
    assert r.status_code == 403


async def test_consultar_la_agencia_preferida_por_http(cliente, app):
    r = await cliente.get("/agencia-preferida", headers=cab())
    assert (r.status_code, r.json()) == (200, {"agencia": None, "contacto": None})  # sin agencia: no es error
    await cliente.put("/agencia-preferida", json={"agencia": "agencia-a", "consentimiento": True}, headers=cab())
    r = await cliente.get("/agencia-preferida", headers=cab())
    assert r.status_code == 200 and r.json()["agencia"] == "agencia-a" and r.json()["contacto"]
    assert (await cliente.get("/agencia-preferida")).status_code == 422


async def test_consultar_sin_casos_devuelve_lista_vacia(cliente):
    r = await cliente.get("/casos", headers=cab())
    assert (r.status_code, r.json()) == (200, [])
