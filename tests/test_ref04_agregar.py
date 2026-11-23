# SPEC: SPEC-REF-04
# ELEMENTO PASO 5: Operaciones manuales de reserva (agregarReserva) (ITERACION_4)
# ADRs: ADR-IT4-008, ADR-IT4-007, ADR-IT4-009
# DRIVERS: REF-04, QA-SEG-02
"""T-REF-04-03: agregarReserva, de punta a punta contra las dos bases reales."""
from datetime import datetime

import pytest

from tests.ref04_util import ANA, INTRUSO, ITIN, LUIS, app, asientos, contar, solicitud  # noqa: F401
from trotamundos.dominio.reserva import Origen

pytestmark = pytest.mark.db


async def test_AC_REF_04_01_agregar_persiste_con_creado_por_y_asiento_de_auditoria(app, bases_limpias):
    r = await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud(lugar="Coliseo"))
    assert r.estado == "ok" and r.reserva["creado_por"] == LUIS
    [reserva] = app.state.repositorio.reservas_de(["roma"])
    assert (reserva.creado_por, reserva.origen, reserva.lugar) == (LUIS, Origen.MANUAL, "Coliseo")
    assert type(reserva).__name__ == "ReservaActividad"
    [viaje] = app.state.repositorio.listar_viajes(LUIS, "activo")  # agrupable por viaje
    assert viaje.id == "roma"
    assert asientos(app) == [{
        "cuenta": LUIS, "operacion": "agregar", "permiso": "registrar", "resultado": "permitido",
        "reserva": reserva.identificador, "clave": "k1", "motivo": None}]
    assert contar(bases_limpias, "reserva") == [1, 1] and contar(bases_limpias, "auditoria") == [1, 1]


async def test_la_reserva_manual_puede_traer_lugar_o_no_y_va_al_viaje_existente(app):
    await app.state.gestion.agregar(ANA, ITIN, "k1", solicitud(lugar=None))
    await app.state.gestion.agregar(ANA, ITIN, "k2", solicitud(lugar="Roma"))  # mismo viaje
    reservas = app.state.repositorio.reservas_de(["roma"])
    assert sorted(r.lugar or "" for r in reservas) == ["", "Roma"]
    assert len(app.state.repositorio.listar_viajes(ANA, "activo")) == 1


async def test_AC_REF_04_02_reintento_con_la_misma_clave_no_duplica(app, bases_limpias):
    primera = await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud())
    segunda = await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud())
    assert segunda.repetida and segunda.reserva == primera.reserva
    assert contar(bases_limpias, "reserva") == [1, 1]
    assert len(asientos(app)) == 1  # el reintento no agrega un asiento


async def test_AC_REF_04_10_misma_clave_con_otro_contenido_devuelve_la_primera_operacion(app, bases_limpias):
    primera = await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud(lugar="Coliseo"))
    otra = await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud(lugar="Vaticano"))
    assert otra.repetida and otra.reserva["lugar"] == "Coliseo"  # no se aplica la segunda
    assert otra.reserva["identificador"] == primera.reserva["identificador"]
    assert [r.lugar for r in app.state.repositorio.reservas_de(["roma"])] == ["Coliseo"]


async def test_la_clave_es_por_cuenta(app):
    await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud(lugar="A"))
    r = await app.state.gestion.agregar(ANA, ITIN, "k1", solicitud(lugar="B"))
    assert r.estado == "ok" and not r.repetida
    assert len(app.state.repositorio.reservas_de(["roma"])) == 2


async def test_AC_REF_04_05_sin_membresia_no_persiste_y_deja_el_asiento_de_la_denegacion(app, bases_limpias):
    r = await app.state.gestion.agregar(INTRUSO, ITIN, "k1", solicitud())
    assert r.estado == "denegado"
    assert contar(bases_limpias, "reserva") == [0, 0] and contar(bases_limpias, "viaje") == [0, 0]
    assert asientos(app) == [{
        "cuenta": INTRUSO, "operacion": "agregar", "permiso": "registrar", "resultado": "denegado",
        "reserva": None, "clave": "k1", "motivo": None}]


async def test_la_denegacion_no_memoriza_la_clave(app):
    await app.state.gestion.agregar(INTRUSO, ITIN, "k1", solicitud())
    assert (await app.state.gestion.agregar(INTRUSO, ITIN, "k1", solicitud())).estado == "denegado"
    assert len(asientos(app)) == 2


async def test_AC_REF_04_13_tipo_no_registrado_se_rechaza_con_asiento(app, bases_limpias):
    r = await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud(tipo="cohete"))
    assert (r.estado, r.motivo) == ("rechazado", "tipo_no_registrado")
    assert contar(bases_limpias, "reserva") == [0, 0]
    [asiento] = asientos(app)
    assert (asiento["resultado"], asiento["motivo"]) == ("rechazado", "tipo_no_registrado")


@pytest.mark.parametrize("cambios", [
    {"fin": datetime(2026, 12, 1)},  # fin anterior a inicio
    {"inicio": None},  # campo obligatorio ausente
    {"datos": {"creado_por": "otro"}},  # intenta fijar un campo que el servidor controla
    {"datos": {"identificador": "res-forzado"}},
    {"viaje_id": "viaje-de-otro-itinerario"},
])
async def test_AC_REF_04_13_campos_invalidos_se_rechazan_con_asiento(app, bases_limpias, cambios):
    from dataclasses import replace
    gestion = app.state.gestion
    # un viaje que pertenece a otro itinerario
    app.state.base_viajes.escribir(lambda c: c.execute(
        "INSERT INTO viaje (id, viajero_id, itinerario_id) VALUES ('viaje-de-otro-itinerario', 'x', 'otro')"))
    r = await gestion.agregar(LUIS, ITIN, "k1", replace(solicitud(), **cambios))
    assert (r.estado, r.motivo) == ("rechazado", "campos_invalidos")
    assert contar(bases_limpias, "reserva") == [0, 0]
    assert [a["resultado"] for a in asientos(app)] == ["rechazado"]


async def test_un_rechazo_no_memoriza_la_clave_y_se_puede_corregir(app):
    malo = await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud(tipo="cohete"))
    bueno = await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud())
    assert malo.estado == "rechazado" and bueno.estado == "ok" and not bueno.repetida


async def test_AC_REF_04_14_falla_a_mitad_de_la_escritura_no_deja_reserva_ni_asiento(app, bases_limpias):
    def falla():
        raise RuntimeError("falla inyectada entre la reserva y el asiento")

    app.state.gestion._gancho_fallo = falla
    with pytest.raises(RuntimeError, match="falla inyectada"):
        await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud())
    for tabla in ("reserva", "viaje", "auditoria", "clave_operacion"):
        assert contar(bases_limpias, tabla) == [0, 0], tabla
    # sin la falla, el mismo pedido se procesa: la clave no quedó memorizada
    app.state.gestion._gancho_fallo = None
    assert (await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud())).estado == "ok"


async def test_la_escritura_queda_en_primaria_y_pasiva_con_el_mismo_identificador(app, bases_limpias):
    from trotamundos.persistencia.conexion import conectar
    await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud())
    ids = []
    for dsn in (bases_limpias.viajes_primaria, bases_limpias.viajes_pasiva):
        with conectar(dsn) as c:
            ids.append(c.execute("SELECT identificador FROM reserva").fetchone()[0])
    assert ids[0] == ids[1]
