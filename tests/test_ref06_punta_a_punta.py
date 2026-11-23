# SPEC: SPEC-REF-06
# ELEMENTO PASO 5: Orquestador, quinta cola, Proyector y Servicio de consultas (ITERACION_5)
# ADRs: ADR-IT5-001, ADR-IT5-002
# DRIVERS: REF-06, QA-PER-02, QA-DIS-01
"""T-REF-06-07: del alta de una reserva al informe del equipo de datos."""
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from tests.ref04_util import ITIN, LUIS, precargar, solicitud
from trotamundos.analitica.consultas import ServicioConsultas
from trotamundos.analitica.proyector import Proyector
from trotamundos.app import create_app
from trotamundos.broker import ResultadoEntrega
from trotamundos.config import Configuracion

pytestmark = pytest.mark.db


async def sin_espera(_s):
    return None


async def test_de_la_reserva_del_viajero_al_informe_del_equipo_de_datos(bases_limpias, analitica_limpia):
    app = create_app(Configuracion(bases=bases_limpias, analitica=analitica_limpia))
    precargar(app)
    app.state.emisor_eventos._dormir = sin_espera
    gestion = app.state.gestion

    r1 = await gestion.agregar(LUIS, ITIN, "k1", solicitud(viaje_id="roma", lugar="Coliseo"))
    await gestion.agregar(LUIS, ITIN, "k2", solicitud(viaje_id="roma", lugar="Coliseo"))
    r3 = await gestion.agregar(LUIS, ITIN, "k3", solicitud(viaje_id="paris", lugar="Louvre"))
    await gestion.actualizar(LUIS, ITIN, r1.reserva["identificador"], "k4", {"lugar": "Foro Romano"})
    await gestion.eliminar(LUIS, ITIN, r3.reserva["identificador"], "k5")
    await app.state.emisor_eventos.esperar()

    proyector = Proyector(app.state.broker, analitica_limpia.dsn)
    try:
        while await proyector.procesar_uno() is not ResultadoEntrega.VACIA:
            pass
    finally:
        proyector.cerrar()

    hoy = datetime.now(UTC).date()
    servicio = ServicioConsultas(replace(analitica_limpia, cuentas_datos=("analista",)))
    informe = await servicio.informe("analista", date(hoy.year, 1, 1), date(hoy.year, 12, 31))
    assert informe["tendencias"] == [{"dia": hoy.isoformat(), "altas": 3}]
    assert informe["destinos"] == [{"destino": "Coliseo", "reservas": 2}, {"destino": "Louvre", "reservas": 1}]
    assert informe["cancelaciones"] == [{"dia": hoy.isoformat(), "destino": "Louvre", "bajas": 1}]
    # y el informe no tiene ningún dato de las cuentas ni de las reservas
    assert LUIS not in str(informe) and "res-" not in str(informe) and ITIN not in str(informe)


async def test_con_la_base_analitica_caida_el_viajero_sigue_operando_y_los_eventos_esperan(bases_limpias):
    cfg = Configuracion(bases=bases_limpias)
    app = create_app(replace(cfg, analitica=replace(cfg.analitica, dsn="postgresql://x:x@localhost:1/nada")))
    precargar(app)
    app.state.emisor_eventos._dormir = sin_espera
    assert (await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud())).estado == "ok"
    await app.state.emisor_eventos.esperar()
    proyector = Proyector(app.state.broker, app.state.configuracion.analitica.dsn)
    app.state.broker._dormir = sin_espera
    assert await proyector.procesar_uno() is ResultadoEntrega.MUERTO  # el Proyector no puede escribir
    assert (await app.state.gestion.agregar(LUIS, ITIN, "k2", solicitud())).estado == "ok"  # y el viajero sigue
