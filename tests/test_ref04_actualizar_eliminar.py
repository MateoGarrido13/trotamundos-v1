# SPEC: SPEC-REF-04
# ELEMENTO PASO 5: Operaciones manuales de reserva (actualizarReserva, eliminarReserva) (ITERACION_4)
# ADRs: ADR-IT4-008, ADR-IT4-007
# DRIVERS: REF-04, QA-SEG-02
"""T-REF-04-04: actualizar y eliminar, con el alcance de cada rol."""
import pytest

from tests.ref04_util import (  # noqa: F401
    ANA,
    INTRUSO,
    ITIN,
    LUIS,
    app,
    asientos,
    contar,
    reserva_externa,
    solicitud,
    viaje_en,
)
from trotamundos.dominio.reserva import Origen
from trotamundos.persistencia.conexion import conectar

pytestmark = pytest.mark.db


async def _crear(app, actor, clave="alta", **kw):
    r = await app.state.gestion.agregar(actor, ITIN, clave, solicitud(**kw))
    assert r.estado == "ok"
    return r.reserva["identificador"]


def _reserva(app, ident):
    return next(r for r in app.state.repositorio.reservas_de(["roma"]) if r.identificador == ident)


def _baja(bases, ident):
    with conectar(bases.viajes_primaria) as c:
        return c.execute("SELECT baja_en FROM reserva WHERE identificador = %s", (ident,)).fetchone()[0]


async def test_actualizar_cambia_los_campos_y_marca_la_reserva_como_editada_a_mano(app):
    ident = await _crear(app, LUIS)
    r = await app.state.gestion.actualizar(LUIS, ITIN, ident, "u1", {"lugar": "Vaticano", "estado": "cancelada"})
    assert r.estado == "ok"
    reserva = _reserva(app, ident)
    assert (reserva.lugar, reserva.estado.value, reserva.editada_manualmente) == ("Vaticano", "cancelada", True)
    assert (reserva.creado_por, reserva.origen) == (LUIS, Origen.MANUAL)  # no cambian


async def test_AC_REF_04_07_participante_modifica_y_elimina_lo_que_creo(app):
    ident = await _crear(app, LUIS)
    assert (await app.state.gestion.actualizar(LUIS, ITIN, ident, "u1", {"lugar": "X"})).estado == "ok"
    assert (await app.state.gestion.eliminar(LUIS, ITIN, ident, "e1")).estado == "ok"
    permitidos = [a for a in asientos(app) if a["resultado"] == "permitido"]
    assert [a["operacion"] for a in permitidos] == ["agregar", "actualizar", "eliminar"]  # cada uno, su asiento


async def test_AC_REF_04_08_participante_no_toca_lo_ajeno_ni_lo_de_proveedor_o_correo(app, bases_limpias):
    de_ana = await _crear(app, ANA, clave="ana1")
    reserva_externa(app, "del-proveedor", Origen.PROVEEDOR)
    reserva_externa(app, "del-correo", Origen.CORREO)
    antes = {i: _reserva(app, i).model_dump() for i in (de_ana, "del-proveedor", "del-correo")}
    for ident in (de_ana, "del-proveedor", "del-correo"):
        for op in ("actualizar", "eliminar"):
            r = await (app.state.gestion.actualizar(LUIS, ITIN, ident, f"{op}-{ident}", {"lugar": "X"})
                       if op == "actualizar" else
                       app.state.gestion.eliminar(LUIS, ITIN, ident, f"{op}-{ident}"))
            assert r.estado == "denegado", (ident, op)
    assert {i: _reserva(app, i).model_dump() for i in antes} == antes  # no cambió nada
    denegados = [a for a in asientos(app) if a["resultado"] == "denegado"]
    assert len(denegados) == 6 and {a["cuenta"] for a in denegados} == {LUIS}


async def test_AC_REF_04_09_organizador_modifica_cualquier_reserva(app):
    de_luis = await _crear(app, LUIS)
    reserva_externa(app, "del-proveedor", Origen.PROVEEDOR)
    reserva_externa(app, "del-correo", Origen.CORREO)
    for ident in (de_luis, "del-proveedor", "del-correo"):
        r = await app.state.gestion.actualizar(ANA, ITIN, ident, f"u-{ident}", {"lugar": "Corregido"})
        assert r.estado == "ok", ident
    assert {_reserva(app, i).lugar for i in (de_luis, "del-proveedor", "del-correo")} == {"Corregido"}
    assert (await app.state.gestion.eliminar(ANA, ITIN, de_luis, "e1")).estado == "ok"


async def test_AC_REF_04_03_eliminar_deja_baja_logica_y_conserva_el_historial(app, bases_limpias):
    ident = await _crear(app, LUIS)
    r = await app.state.gestion.eliminar(LUIS, ITIN, ident, "e1")
    assert r.estado == "ok" and r.reserva["identificador"] == ident
    assert _baja(bases_limpias, ident) is not None  # baja lógica: la fila sigue ahí
    assert contar(bases_limpias, "reserva") == [1, 1]
    assert app.state.repositorio.reservas_de(["roma"]) == []  # ya no se ve
    assert [a["operacion"] for a in asientos(app)] == ["agregar", "eliminar"]


async def test_AC_REF_04_11_reserva_en_baja_no_se_actualiza_ni_se_elimina(app, bases_limpias):
    ident = await _crear(app, LUIS)
    await app.state.gestion.eliminar(LUIS, ITIN, ident, "e1")
    baja = _baja(bases_limpias, ident)
    for r in (await app.state.gestion.actualizar(ANA, ITIN, ident, "u2", {"lugar": "X"}),
              await app.state.gestion.eliminar(ANA, ITIN, ident, "e2")):
        assert (r.estado, r.motivo) == ("rechazado", "en_baja")
    assert _baja(bases_limpias, ident) == baja  # sin efecto


async def test_AC_REF_04_12_inexistente_o_de_otro_itinerario_se_rechaza_sin_revelar_existencia(app):
    viaje_en(app, "viaje-otro", "otro")
    app.state.base_viajes.escribir(lambda c: c.execute(
        "INSERT INTO membresia VALUES ('otro', 'zoe', 'organizador')"))
    ajena = await app.state.gestion.agregar("zoe", "otro", "z1", solicitud(viaje_id="viaje-otro"))
    ident_ajeno = ajena.reserva["identificador"]

    for ident in ("no-existe", ident_ajeno):  # con permiso en ITIN
        for r in (await app.state.gestion.actualizar(ANA, ITIN, ident, f"u-{ident}", {"lugar": "X"}),
                  await app.state.gestion.eliminar(ANA, ITIN, ident, f"e-{ident}")):
            assert (r.estado, r.motivo) == ("rechazado", "no_existe"), ident
    # sin permiso en ese itinerario: acceso denegado, igual exista o no (no se revela)
    for ident in ("no-existe", ident_ajeno):
        r = await app.state.gestion.actualizar(INTRUSO, ITIN, ident, f"i-{ident}", {"lugar": "X"})
        assert (r.estado, r.motivo) == ("denegado", None), ident
    # la reserva ajena no cambió
    assert app.state.repositorio.reservas_de(["viaje-otro"])[0].lugar == "Coliseo"


async def test_actualizar_con_campos_invalidos_se_rechaza_con_asiento_y_sin_cambios(app):
    ident = await _crear(app, LUIS)
    for cambios in ({"tipo": "hotel"}, {"creado_por": "ana"}, {"inicio": "no-es-fecha"},
                    {"fin": "2020-01-01T00:00:00"}, {}):
        r = await app.state.gestion.actualizar(LUIS, ITIN, ident, f"u-{cambios}", cambios)
        assert (r.estado, r.motivo) == ("rechazado", "campos_invalidos"), cambios
    reserva = _reserva(app, ident)
    assert reserva.lugar == "Coliseo" and reserva.creado_por == LUIS and not reserva.editada_manualmente
    assert [a["resultado"] for a in asientos(app)].count("rechazado") == 5


async def test_actualizar_con_la_misma_clave_no_se_aplica_dos_veces(app):
    ident = await _crear(app, LUIS)
    await app.state.gestion.actualizar(LUIS, ITIN, ident, "u1", {"lugar": "Primero"})
    r = await app.state.gestion.actualizar(LUIS, ITIN, ident, "u1", {"lugar": "Segundo"})
    assert r.repetida and _reserva(app, ident).lugar == "Primero"


async def test_AC_REF_04_14_falla_al_actualizar_no_deja_cambio_ni_asiento(app):
    ident = await _crear(app, LUIS)
    antes = len(asientos(app))

    def falla():
        raise RuntimeError("falla inyectada")

    app.state.gestion._gancho_fallo = falla
    with pytest.raises(RuntimeError):
        await app.state.gestion.actualizar(LUIS, ITIN, ident, "u1", {"lugar": "X"})
    with pytest.raises(RuntimeError):
        await app.state.gestion.eliminar(LUIS, ITIN, ident, "e1")
    app.state.gestion._gancho_fallo = None
    reserva = _reserva(app, ident)
    assert reserva.lugar == "Coliseo" and reserva.baja_en is None
    assert len(asientos(app)) == antes
