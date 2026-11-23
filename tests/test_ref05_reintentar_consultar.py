# SPEC: SPEC-REF-05
# ELEMENTO PASO 5: Orquestador de viajes, reintentar y consultar casos (ITERACION_4)
# ADRs: ADR-IT4-010, ADR-IT3-003, ADR-IT4-007
# DRIVERS: REF-05
"""T-REF-05-07: reintentar un caso «sin entregar» y consultar los casos del viajero."""
import pytest

from tests.ref04_util import ANA, INTRUSO, ITIN, LUIS, asientos
from tests.ref05_util import (  # noqa: F401
    app,
    con_agencia,
    estado_del_caso,
    llenar_cola_de_casos,
    reserva_de,
    vaciar_un_lugar,
)
from trotamundos.broker import NombreCola
from trotamundos.dominio.agencias import EstadoCaso

pytestmark = pytest.mark.db


async def caso_sin_entregar(app, actor=LUIS):
    ident = await reserva_de(app)
    await con_agencia(app, actor=actor)
    llenar_cola_de_casos(app)
    r = await app.state.casos.reportar(actor, ITIN, "reporte", ident, "Problema")
    await app.state.casos.esperar_publicaciones()
    assert estado_del_caso(app, r.caso["id"]) == "sin_entregar"
    vaciar_un_lugar(app)  # ahora hay lugar
    return r.caso["id"]


async def test_AC_REF_05_12_reintentar_vuelve_a_en_tramite_y_republica_el_mismo_pedido(app):
    caso_id = await caso_sin_entregar(app)
    r = await app.state.casos.reintentar(LUIS, ITIN, caso_id, "reintento")
    assert r.estado == "ok" and r.caso["estado"] == "en_tramite"
    await app.state.casos.esperar_publicaciones()
    publicados = [m for m in app.state.broker._colas[NombreCola.CASOS_AYUDA] if m.id == caso_id]
    assert len(publicados) == 1 and publicados[0].cuerpo["id_caso"] == caso_id  # el mismo identificador
    assert estado_del_caso(app, caso_id) == "en_tramite"
    assert "reintentar_caso" in [a["operacion"] for a in asientos(app)]


@pytest.mark.parametrize("estado", [EstadoCaso.EN_TRAMITE, EstadoCaso.ABIERTO, EstadoCaso.EN_CURSO,
                                    EstadoCaso.RESUELTO])
async def test_AC_REF_05_13_reintentar_un_caso_que_no_esta_sin_entregar_se_rechaza(app, estado):
    ident = await reserva_de(app)
    await con_agencia(app)
    caso_id = (await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "Problema")).caso["id"]
    await app.state.casos.esperar_publicaciones()
    if estado is not EstadoCaso.EN_TRAMITE:
        await app.state.casos.aplicar_estado_caso(caso_id, estado)
    en_cola = app.state.broker.tamano_actual(NombreCola.CASOS_AYUDA)
    r = await app.state.casos.reintentar(LUIS, ITIN, caso_id, "reintento")
    assert (r.estado, r.motivo) == ("rechazado", "estado_invalido")
    assert estado_del_caso(app, caso_id) == estado.value  # sin efecto
    await app.state.casos.esperar_publicaciones()
    assert app.state.broker.tamano_actual(NombreCola.CASOS_AYUDA) == en_cola  # y no se republicó


async def test_reintentar_dos_veces_con_la_misma_clave_publica_una_sola_vez(app):
    caso_id = await caso_sin_entregar(app)
    await app.state.casos.reintentar(LUIS, ITIN, caso_id, "reintento")
    r = await app.state.casos.reintentar(LUIS, ITIN, caso_id, "reintento")
    assert r.repetida
    await app.state.casos.esperar_publicaciones()
    assert [m.id for m in app.state.broker._colas[NombreCola.CASOS_AYUDA]].count(caso_id) == 1


async def test_reintentar_sin_permiso_registrar_se_deniega_con_asiento(app):
    caso_id = await caso_sin_entregar(app)
    r = await app.state.casos.reintentar(INTRUSO, ITIN, caso_id, "reintento")
    assert r.estado == "denegado" and estado_del_caso(app, caso_id) == "sin_entregar"
    assert asientos(app)[-1]["resultado"] == "denegado"


async def test_solo_quien_reporto_el_caso_lo_reintenta(app):
    caso_id = await caso_sin_entregar(app)  # lo reportó Luis
    r = await app.state.casos.reintentar(ANA, ITIN, caso_id, "reintento")  # Ana es organizadora
    assert (r.estado, r.motivo) == ("rechazado", "caso_inexistente")  # indistinguible de uno inexistente
    assert estado_del_caso(app, caso_id) == "sin_entregar"
    r = await app.state.casos.reintentar(LUIS, ITIN, "caso-no-existe", "otra")
    assert (r.estado, r.motivo) == ("rechazado", "caso_inexistente")


async def test_consultar_devuelve_solo_los_casos_del_viajero_y_vacio_si_no_hay(app):
    assert await app.state.casos.consultar(LUIS) == []  # sin casos: lista vacía, no error
    ident = await reserva_de(app)
    await con_agencia(app)
    await con_agencia(app, actor=ANA)
    r = await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "Problema")
    await app.state.casos.esperar_publicaciones()
    await app.state.casos.aplicar_estado_caso(r.caso["id"], EstadoCaso.ABIERTO)
    assert [(c["id"], c["estado"]) for c in await app.state.casos.consultar(LUIS)] == [(r.caso["id"], "abierto")]
    assert await app.state.casos.consultar(ANA) == []  # lo de otro no se ve
