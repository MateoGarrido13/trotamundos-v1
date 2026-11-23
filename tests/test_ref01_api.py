# SPEC: SPEC-REF-01
# ELEMENTO PASO 5: Vista principal y archivo para Cliente web y móvil (ITERACION_1)
# ADRs: ADR-001
# DRIVERS: REF-01, CON-01
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from trotamundos.app import create_app
from trotamundos.config import Configuracion, ConfiguracionBases
from trotamundos.dominio.tipos_reserva import ReservaHotel, ReservaVuelo
from trotamundos.orquestador.archivado import archivar_completados

H = {"X-Viajero-Id": "ana"}


@pytest.fixture
def cliente(bases_limpias):
    app = create_app(Configuracion(bases=bases_limpias))
    return TestClient(app), app.state.repositorio


@pytest.mark.db
def test_AC_REF_01_01_http_vista_principal_agrupa_reservas_por_viaje(cliente):
    http, repo = cliente
    repo.insertar_viaje("v1", "ana")
    repo.insertar_reserva(ReservaVuelo(identificador="r1", viaje_id="v1", lugar="Lima",
                                       inicio=datetime(2027, 1, 1), fin=datetime(2027, 1, 2)))
    repo.insertar_reserva(ReservaHotel(identificador="r2", viaje_id="v1",
                                       inicio=datetime(2027, 1, 2), fin=datetime(2027, 1, 9)))
    r = http.get("/viajes", headers=H)
    assert r.status_code == 200
    [viaje] = r.json()
    assert viaje["id"] == "v1"
    assert [(x["identificador"], x["tipo"]) for x in viaje["reservas"]] == [("r1", "vuelo"), ("r2", "hotel")]
    assert viaje["reservas"][0]["resumen"] == "Vuelo en Lima (r1)"


@pytest.mark.db
def test_AC_REF_01_07_http_sin_viajes_activos_devuelve_lista_vacia(cliente):
    http, _ = cliente
    r = http.get("/viajes", headers=H)
    assert r.status_code == 200 and r.json() == []


@pytest.mark.db
def test_AC_REF_01_06_http_archivados_devuelve_viajes_o_lista_vacia(cliente):
    http, repo = cliente
    assert http.get("/viajes/archivados", headers=H).json() == []
    repo.insertar_viaje("v1", "ana")
    repo.insertar_reserva(ReservaHotel(identificador="r1", viaje_id="v1",
                                       inicio=datetime(2026, 12, 1), fin=datetime(2026, 12, 5)))
    archivar_completados(repo, datetime(2026, 12, 10))
    assert http.get("/viajes", headers=H).json() == []
    [viaje] = http.get("/viajes/archivados", headers=H).json()
    assert viaje["id"] == "v1" and viaje["estado"] == "archivado" and len(viaje["reservas"]) == 1
    assert http.get("/viajes/archivados", headers={"X-Viajero-Id": "otra"}).json() == []


def test_sin_ninguna_base_responde_503():
    muertas = ConfiguracionBases(
        viajes_primaria="postgresql://x:x@127.0.0.1:1/x?connect_timeout=1",
        viajes_pasiva="postgresql://x:x@127.0.0.1:1/x?connect_timeout=1",
        umbral_conmutacion=1)
    http = TestClient(create_app(Configuracion(bases=muertas)))
    assert http.get("/viajes", headers=H).status_code == 503
    assert http.get("/viajes/archivados", headers=H).status_code == 503
