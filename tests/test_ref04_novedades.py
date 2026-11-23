# SPEC: SPEC-REF-04
# ELEMENTO PASO 5: Orquestador de viajes, precedencia de la edición manual (ITERACION_4)
# ADRs: ADR-IT4-008
# DRIVERS: REF-04
"""T-REF-04-06: una novedad del proveedor no pisa una edición manual."""
from datetime import datetime

import pytest

from tests.ref04_util import ANA, INTRUSO, ITIN, LUIS, app, reserva_externa  # noqa: F401
from trotamundos.dominio.reserva import Origen
from trotamundos.orquestador.gestion_reservas import AccesoDenegado
from trotamundos.orquestador.novedades import NovedadProveedor

pytestmark = pytest.mark.db


def _reserva(app, ident):
    return next(r for r in app.state.repositorio.reservas_de(["roma"]) if r.identificador == ident)


async def test_AC_REF_04_04_novedad_no_pisa_la_edicion_manual_y_queda_visible(app):
    reserva_externa(app, "h1", Origen.PROVEEDOR)
    await app.state.gestion.actualizar(ANA, ITIN, "h1", "u1", {"lugar": "Hotel corregido a mano"})

    resultado = await app.state.novedades.aplicar(NovedadProveedor(
        id="n1", reserva_id="h1", proveedor="booking", cambios={"lugar": "Otro hotel", "estado": "cancelada"}))

    assert resultado == "retenida"
    reserva = _reserva(app, "h1")
    assert (reserva.lugar, reserva.estado.value) == ("Hotel corregido a mano", "confirmada")  # permanece
    [novedad] = await app.state.novedades.pendientes(LUIS, ITIN)  # visible en «Novedades»
    assert (novedad.id, novedad.reserva_id, novedad.proveedor) == ("n1", "h1", "booking")
    assert novedad.cambios == {"lugar": "Otro hotel", "estado": "cancelada"}


async def test_una_novedad_sobre_una_reserva_sin_editar_se_aplica(app):
    reserva_externa(app, "h1", Origen.PROVEEDOR)
    r = await app.state.novedades.aplicar(NovedadProveedor(
        id="n1", reserva_id="h1", cambios={"lugar": "Hotel del proveedor", "fin": datetime(2026, 12, 6, 10)}))
    assert r == "aplicada"
    reserva = _reserva(app, "h1")
    assert (reserva.lugar, reserva.fin) == ("Hotel del proveedor", datetime(2026, 12, 6, 10))
    assert reserva.editada_manualmente is False  # aplicar una novedad no la marca como editada a mano
    assert await app.state.novedades.pendientes(ANA, ITIN) == []


async def test_la_precedencia_vale_tambien_para_una_reserva_creada_a_mano(app):
    from tests.ref04_util import solicitud
    r = await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud(lugar="Coliseo"))
    ident = r.reserva["identificador"]
    await app.state.gestion.actualizar(LUIS, ITIN, ident, "u1", {"lugar": "Foro Romano"})
    assert await app.state.novedades.aplicar(NovedadProveedor(
        id="n1", reserva_id=ident, cambios={"lugar": "Otro"})) == "retenida"
    assert _reserva(app, ident).lugar == "Foro Romano"


async def test_una_novedad_sobre_una_reserva_en_baja_queda_pendiente(app):
    reserva_externa(app, "h1", Origen.PROVEEDOR)
    await app.state.gestion.eliminar(ANA, ITIN, "h1", "e1")
    assert await app.state.novedades.aplicar(NovedadProveedor(
        id="n1", reserva_id="h1", cambios={"lugar": "X"})) == "retenida"


async def test_una_novedad_repetida_o_de_una_reserva_inexistente_no_hace_nada(app):
    reserva_externa(app, "h1", Origen.PROVEEDOR)
    n = NovedadProveedor(id="n1", reserva_id="h1", cambios={"lugar": "A"})
    assert await app.state.novedades.aplicar(n) == "aplicada"
    assert await app.state.novedades.aplicar(NovedadProveedor(id="n1", reserva_id="h1", cambios={"lugar": "B"})) == "duplicada"
    assert _reserva(app, "h1").lugar == "A"
    assert await app.state.novedades.aplicar(NovedadProveedor(id="n2", reserva_id="no-existe")) == "no_existe"


async def test_una_novedad_que_no_se_puede_aplicar_queda_para_que_decida_el_viajero(app):
    reserva_externa(app, "h1", Origen.PROVEEDOR)
    for i, cambios in enumerate(({"tipo": "vuelo"}, {"fin": datetime(2020, 1, 1)})):
        assert await app.state.novedades.aplicar(NovedadProveedor(
            id=f"n{i}", reserva_id="h1", cambios=cambios)) == "retenida"
    assert len(await app.state.novedades.pendientes(ANA, ITIN)) == 2


async def test_ver_las_novedades_requiere_permiso_de_ver(app):
    with pytest.raises(AccesoDenegado):
        await app.state.novedades.pendientes(INTRUSO, ITIN)
