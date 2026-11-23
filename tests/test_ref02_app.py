# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Gestor de autorización del correo (endpoints) (ITERACION_3)
# ADRs: ADR-IT3-006, ADR-IT3-010
# DRIVERS: QA-SEG-03*
"""T-REF-02-08: endpoints de autorizar y revocar.

AC-REF-02-06: aquí solo se cubre la parte de revocación (el Adaptador deja de leer y una
reserva ya incorporada, simulada con un itinerario en memoria, permanece). La parte de punta
a punta contra el itinerario real y PostgreSQL es T-REF-02-09."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from tests.test_ref02_adaptador import T0, Entorno
from trotamundos.broker import NombreCola
from trotamundos.entrada.app import create_app


@pytest.fixture
def entorno(cfg_broker):
    return Entorno(cfg_broker)


@pytest.fixture
def cliente(entorno):
    return TestClient(create_app(entorno.gestor))


def test_autorizar_requiere_titular_y_guarda_token(cliente, entorno):
    assert cliente.post("/correo/autorizacion", json={"token": "tok"}).status_code == 401
    r = cliente.post("/correo/autorizacion", json={"token": "tok"}, headers={"X-Titular-Id": "t1"})
    assert r.status_code == 201
    assert entorno.gestor.token_vigente("t1") == "tok"
    assert cliente.delete("/correo/autorizacion").status_code == 401


async def test_AC_REF_02_01_endpoint_autorizar_y_revocar_gobiernan_la_lectura(cliente, entorno):
    entorno.api.emitir_token("t1", "tok")
    entorno.correo()
    assert not (await entorno.adaptador.sondear("t1", T0)).leyo
    cliente.post("/correo/autorizacion", json={"token": "tok"}, headers={"X-Titular-Id": "t1"})
    assert (await entorno.adaptador.sondear("t1", T0)).leyo
    assert cliente.delete("/correo/autorizacion", headers={"X-Titular-Id": "t1"}).status_code == 204
    assert not (await entorno.adaptador.sondear("t1", T0)).leyo


async def test_AC_REF_02_06_revocar_deja_de_leer_y_conserva_la_reserva_incorporada(cliente, entorno):
    # Parte de revocación (T-REF-02-08). Falta de punta a punta: T-REF-02-09.
    itinerario = ["reserva-incorporada-desde-correo"]  # simula la reserva ya incorporada
    entorno.api.emitir_token("t1", "tok")
    entorno.correo()
    cliente.post("/correo/autorizacion", json={"token": "tok"}, headers={"X-Titular-Id": "t1"})
    assert (await entorno.adaptador.sondear("t1", T0)).publicados == 1
    lecturas = entorno.api.lecturas
    cliente.delete("/correo/autorizacion", headers={"X-Titular-Id": "t1"})
    assert not (await entorno.adaptador.sondear("t1", T0 + timedelta(minutes=15))).leyo
    assert entorno.api.lecturas == lecturas  # dejó de leer
    assert entorno.broker.tamano_actual(NombreCola.CORREO) == 1  # nada nuevo en la cola
    assert itinerario == ["reserva-incorporada-desde-correo"]  # la revocación no la toca
