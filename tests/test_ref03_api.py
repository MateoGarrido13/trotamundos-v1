# SPEC: SPEC-REF-03
# ELEMENTO PASO 5: Orquestador de viajes, Mensajes en revisión (ITERACION_3)
# ADRs: ADR-IT3-008
# DRIVERS: REF-03
"""T-REF-03-07: endpoints del titular, con las bases reales."""
import pytest
from fastapi.testclient import TestClient

from tests.ref03_util import reserva_norm
from trotamundos.app import create_app
from trotamundos.config import Configuracion

pytestmark = pytest.mark.db
H = {"X-Viajero-Id": "t1"}


@pytest.fixture
def app(bases_limpias):
    return create_app(Configuracion(bases=bases_limpias))


@pytest.fixture
def cliente(app):
    return TestClient(app)


async def _retener(app, *reservas):
    for r in reservas:
        await app.state.servicio_revision.retener(r)


async def test_AC_REF_03_10_sin_mensajes_en_revision_devuelve_lista_vacia_por_http(cliente):
    r = cliente.get("/revision", headers=H)
    assert r.status_code == 200 and r.json() == []


async def test_consultar_muestra_remitente_y_resumen(app, cliente):
    await _retener(app, reserva_norm())
    assert cliente.get("/revision", headers=H).json() == [{
        "id_mensaje": "<m1@x>", "remitente": "agencia@x.com",
        "resumen": "hotel en Roma (2026-12-01 a 2026-12-05)"}]
    assert cliente.get("/revision", headers={"X-Viajero-Id": "t2"}).json() == []


async def test_AC_REF_03_03_aprobar_por_http_libera_hacia_la_ingesta(app, cliente):
    await _retener(app, reserva_norm())
    r = cliente.post("/revision/remitentes", json={"remitente": "Agencia@X.com"}, headers=H)
    assert r.status_code == 200 and r.json() == {"remitente": "agencia@x.com", "liberados": 1}
    assert cliente.get("/revision", headers=H).json() == []
    assert app.state.broker.tamano_actual("novedades") == 1  # la reserva siguió hacia la ingesta
    # aprobar de nuevo no es error y no libera nada más
    r = cliente.post("/revision/remitentes", json={"remitente": "agencia@x.com"}, headers=H)
    assert r.status_code == 200 and r.json()["liberados"] == 0


async def test_AC_REF_03_09_quitar_remitente_por_http_no_es_error_si_no_esta(app, cliente):
    cliente.post("/revision/remitentes", json={"remitente": "a@x.com"}, headers=H)
    assert cliente.delete("/revision/remitentes/a@x.com", headers=H).status_code == 204
    assert cliente.delete("/revision/remitentes/a@x.com", headers=H).status_code == 204
    assert not await app.state.servicio_revision.remitente_seguro("t1", "a@x.com")


async def test_AC_REF_03_12_descartar_por_http_rechaza_inexistente_o_ajeno_sin_cambios(app, cliente):
    await _retener(app, reserva_norm())
    assert cliente.post("/revision/descartar", json={"id_mensaje": "<no@x>"}, headers=H).status_code == 404
    assert cliente.post("/revision/descartar", json={"id_mensaje": "<m1@x>"},
                        headers={"X-Viajero-Id": "t2"}).status_code == 404
    assert len(cliente.get("/revision", headers=H).json()) == 1
    assert cliente.post("/revision/descartar", json={"id_mensaje": "<m1@x>"}, headers=H).status_code == 204
    assert cliente.get("/revision", headers=H).json() == []
    assert cliente.post("/revision/descartar", json={"id_mensaje": "<m1@x>"}, headers=H).status_code == 404


async def test_sin_identidad_el_servicio_responde_422(cliente):
    assert cliente.get("/revision").status_code == 422
    assert cliente.post("/revision/remitentes", json={"remitente": "a@x.com"}).status_code == 422
