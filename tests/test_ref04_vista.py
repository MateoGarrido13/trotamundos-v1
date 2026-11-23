# SPEC: SPEC-REF-04
# ELEMENTO PASO 5: Operaciones manuales de reserva, vista del itinerario (ITERACION_4)
# ADRs: ADR-IT4-007
# DRIVERS: QA-SEG-02
"""T-REF-04-05: la vista del itinerario para los demás miembros."""
import pytest

from tests.ref04_util import ANA, INTRUSO, ITIN, LUIS, app, asientos, solicitud  # noqa: F401
from trotamundos.orquestador.gestion_reservas import AccesoDenegado

pytestmark = pytest.mark.db


async def test_AC_REF_04_06_otro_miembro_ve_la_actividad_registrada(app):
    await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud(lugar="Coliseo"))
    # otro miembro con permiso de ver pide la vista y ve la actividad (en su próxima consulta)
    viajes = await app.state.gestion.vista(ANA, ITIN)
    [viaje] = viajes
    [reserva] = viaje.reservas
    assert (viaje.id, reserva.lugar, reserva.creado_por) == ("roma", "Coliseo", LUIS)
    assert type(reserva).__name__ == "ReservaActividad"


async def test_la_vista_agrupa_las_reservas_por_viaje(app):
    for i, viaje in enumerate(["roma", "roma", "paris"]):
        await app.state.gestion.agregar(LUIS, ITIN, f"k{i}", solicitud(viaje_id=viaje))
    viajes = {v.id: len(v.reservas) for v in await app.state.gestion.vista(ANA, ITIN)}
    assert viajes == {"paris": 1, "roma": 2}


async def test_la_vista_no_incluye_las_reservas_dadas_de_baja(app):
    r = await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud())
    await app.state.gestion.agregar(LUIS, ITIN, "k2", solicitud(lugar="Vaticano"))
    await app.state.gestion.eliminar(LUIS, ITIN, r.reserva["identificador"], "e1")
    [viaje] = await app.state.gestion.vista(ANA, ITIN)
    assert [x.lugar for x in viaje.reservas] == ["Vaticano"]


async def test_la_vista_es_solo_del_itinerario_pedido(app):
    await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud())
    app.state.base_viajes.escribir(lambda c: c.execute("INSERT INTO membresia VALUES ('otro', 'ana', 'organizador')"))
    assert await app.state.gestion.vista(ANA, "otro") == []  # vacía, no es un error


async def test_AC_REF_04_05_sin_permiso_de_ver_el_acceso_se_deniega_con_asiento(app):
    await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud())
    with pytest.raises(AccesoDenegado):
        await app.state.gestion.vista(INTRUSO, ITIN)
    [*_, ultimo] = asientos(app)
    assert (ultimo["cuenta"], ultimo["operacion"], ultimo["resultado"]) == (INTRUSO, "vista", "denegado")


async def test_ver_no_deja_asiento_cuando_se_permite(app):
    await app.state.gestion.vista(ANA, ITIN)
    await app.state.gestion.vista(LUIS, ITIN)
    assert asientos(app) == []  # solo se audita la denegación de las consultas
