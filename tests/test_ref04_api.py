# SPEC: SPEC-REF-04
# ELEMENTO PASO 5: Operaciones manuales de reserva, endpoints (ITERACION_4)
# ADRs: ADR-IT4-008, ADR-IT4-007
# DRIVERS: REF-04, QA-SEG-02
"""T-REF-04-07: los endpoints y sus códigos de respuesta, con las bases reales."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from tests.ref04_util import (  # noqa: F401
    AHORA,
    ANA,
    INTRUSO,
    ITIN,
    LUIS,
    app,
    asientos,
    contar,
    reserva_externa,
)
from trotamundos.dominio.reserva import Origen
from trotamundos.orquestador.novedades import NovedadProveedor

pytestmark = pytest.mark.db

CUERPO = {"viaje_id": "roma", "tipo": "actividad", "inicio": "2026-12-02T09:00:00",
          "fin": "2026-12-02T12:00:00", "lugar": "Coliseo"}


def cab(actor, clave="k1"):
    return {"X-Viajero-Id": actor, "X-Clave-Operacion": clave}


@pytest.fixture
def cliente(app):
    return TestClient(app)


def test_AC_REF_04_01_agregar_por_http_responde_201_con_la_reserva(cliente, app):
    r = cliente.post(f"/itinerarios/{ITIN}/reservas", json=CUERPO, headers=cab(LUIS))
    assert r.status_code == 201
    reserva = r.json()["reserva"]
    assert (reserva["creado_por"], reserva["origen"], reserva["lugar"]) == (LUIS, "manual", "Coliseo")
    assert [a["resultado"] for a in asientos(app)] == ["permitido"]


def test_AC_REF_04_02_reintento_por_http_devuelve_lo_mismo_sin_duplicar(cliente, app, bases_limpias):
    a = cliente.post(f"/itinerarios/{ITIN}/reservas", json=CUERPO, headers=cab(LUIS))
    b = cliente.post(f"/itinerarios/{ITIN}/reservas", json={**CUERPO, "lugar": "Otro"}, headers=cab(LUIS))
    assert b.status_code == 201 and b.json()["repetida"] is True
    assert b.json()["reserva"] == a.json()["reserva"]
    assert contar(bases_limpias, "reserva") == [1, 1]


def test_AC_REF_04_05_sin_membresia_responde_403_y_no_persiste(cliente, app, bases_limpias):
    r = cliente.post(f"/itinerarios/{ITIN}/reservas", json=CUERPO, headers=cab(INTRUSO))
    assert r.status_code == 403 and r.json() == {"error": "acceso_denegado"}
    assert contar(bases_limpias, "reserva") == [0, 0]
    assert [(a["cuenta"], a["resultado"]) for a in asientos(app)] == [(INTRUSO, "denegado")]
    # lo mismo para ver, actualizar, eliminar y las novedades
    assert cliente.get(f"/itinerarios/{ITIN}", headers=cab(INTRUSO)).status_code == 403
    assert cliente.get(f"/itinerarios/{ITIN}/novedades", headers=cab(INTRUSO)).status_code == 403
    assert cliente.patch(f"/itinerarios/{ITIN}/reservas/x", json={"cambios": {"lugar": "X"}},
                         headers=cab(INTRUSO, "k2")).status_code == 403
    assert cliente.delete(f"/itinerarios/{ITIN}/reservas/x", headers=cab(INTRUSO, "k3")).status_code == 403


def test_AC_REF_04_06_otro_miembro_ve_la_actividad_por_http(cliente):
    cliente.post(f"/itinerarios/{ITIN}/reservas", json=CUERPO, headers=cab(LUIS))
    r = cliente.get(f"/itinerarios/{ITIN}", headers=cab(ANA))
    assert r.status_code == 200
    [viaje] = r.json()
    assert viaje["id"] == "roma" and viaje["reservas"][0]["lugar"] == "Coliseo"
    assert viaje["reservas"][0]["creado_por"] == LUIS


def test_actualizar_y_eliminar_por_http(cliente):
    ident = cliente.post(f"/itinerarios/{ITIN}/reservas", json=CUERPO,
                         headers=cab(LUIS)).json()["reserva"]["identificador"]
    r = cliente.patch(f"/itinerarios/{ITIN}/reservas/{ident}", json={"cambios": {"lugar": "Foro"}},
                      headers=cab(LUIS, "k2"))
    assert r.status_code == 200 and r.json()["reserva"]["lugar"] == "Foro"
    r = cliente.delete(f"/itinerarios/{ITIN}/reservas/{ident}", headers=cab(LUIS, "k3"))
    assert r.status_code == 200 and r.json()["reserva"]["identificador"] == ident
    [viaje] = cliente.get(f"/itinerarios/{ITIN}", headers=cab(ANA)).json()
    assert viaje["id"] == "roma" and viaje["reservas"] == []  # el viaje sigue; la reserva dada de baja no se ve


def test_los_rechazos_tienen_su_codigo(cliente):
    assert cliente.post(f"/itinerarios/{ITIN}/reservas", json={**CUERPO, "tipo": "cohete"},
                        headers=cab(LUIS, "a")).status_code == 422
    assert cliente.post(f"/itinerarios/{ITIN}/reservas", json={**CUERPO, "fin": "2020-01-01T00:00:00"},
                        headers=cab(LUIS, "b")).status_code == 422
    assert cliente.patch(f"/itinerarios/{ITIN}/reservas/no-existe", json={"cambios": {"lugar": "X"}},
                         headers=cab(ANA, "c")).status_code == 404
    ident = cliente.post(f"/itinerarios/{ITIN}/reservas", json=CUERPO,
                         headers=cab(LUIS, "d")).json()["reserva"]["identificador"]
    cliente.delete(f"/itinerarios/{ITIN}/reservas/{ident}", headers=cab(LUIS, "e"))
    assert cliente.delete(f"/itinerarios/{ITIN}/reservas/{ident}", headers=cab(LUIS, "f")).status_code == 409
    assert cliente.patch(f"/itinerarios/{ITIN}/reservas/{ident}", json={"cambios": {"lugar": "X"}},
                         headers=cab(ANA, "g")).status_code == 409


def test_el_permiso_se_verifica_antes_que_los_campos(cliente, app):
    """Sin permiso, un cuerpo inválido da 403 y no 422: no se revela nada al que no puede ver."""
    r = cliente.post(f"/itinerarios/{ITIN}/reservas", json={"tipo": "cohete"}, headers=cab(INTRUSO))
    assert r.status_code == 403


def test_sin_identidad_ni_clave_o_con_cuerpo_que_no_es_un_objeto_responde_422(cliente):
    assert cliente.post(f"/itinerarios/{ITIN}/reservas", json=CUERPO).status_code == 422
    assert cliente.post(f"/itinerarios/{ITIN}/reservas", json=CUERPO,
                        headers={"X-Viajero-Id": LUIS}).status_code == 422
    assert cliente.post(f"/itinerarios/{ITIN}/reservas", json=[1, 2], headers=cab(LUIS)).status_code == 422
    assert cliente.post(f"/itinerarios/{ITIN}/reservas", json={**CUERPO, "datos": "x"},
                        headers=cab(LUIS)).status_code == 422
    assert cliente.get(f"/itinerarios/{ITIN}").status_code == 422


def test_novedades_por_http(cliente, app):
    import asyncio
    reserva_externa(app, "h1", Origen.PROVEEDOR)
    cliente.patch(f"/itinerarios/{ITIN}/reservas/h1", json={"cambios": {"lugar": "A mano"}}, headers=cab(ANA))
    asyncio.run(app.state.novedades.aplicar(NovedadProveedor(
        id="n1", reserva_id="h1", proveedor="booking", cambios={"lugar": "Otro"})))
    r = cliente.get(f"/itinerarios/{ITIN}/novedades", headers=cab(LUIS))
    assert r.status_code == 200 and [(n["id"], n["cambios"]) for n in r.json()] == [("n1", {"lugar": "Otro"})]


async def test_la_purga_elimina_las_claves_de_mas_de_siete_dias(app, bases_limpias):
    from tests.ref04_util import solicitud
    await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud())
    assert await app.state.gestion.purgar_claves(AHORA + timedelta(days=6)) == 0
    assert contar(bases_limpias, "clave_operacion") == [1, 1]
    from datetime import UTC, datetime
    assert await app.state.gestion.purgar_claves(datetime.now(UTC) + timedelta(days=8)) == 1
    assert contar(bases_limpias, "clave_operacion") == [0, 0]
