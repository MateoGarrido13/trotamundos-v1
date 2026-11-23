# SPEC: SPEC-REF-05
# ELEMENTO PASO 5: Orquestador de viajes, cola de casos de ayuda (ITERACION_4)
# ADRs: ADR-IT3-002, ADR-IT4-010
# DRIVERS: REF-05
"""T-REF-05-04: la publicación del pedido, con la cola llena y con reintentos."""
import pytest

from tests.ref04_util import ITIN, LUIS
from tests.ref05_util import (  # noqa: F401
    app,
    con_agencia,
    estado_del_caso,
    llenar_cola_de_casos,
    pedido_en_cola,
    reserva_de,
    vaciar_un_lugar,
)
from trotamundos.broker import Aviso, NombreCola

pytestmark = pytest.mark.db


async def test_AC_REF_05_01_reportar_publica_el_pedido_en_la_cola_de_casos_de_ayuda(app):
    ident = await reserva_de(app)
    await con_agencia(app, agencia="agencia-b")
    r = await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "Problema", resumen_dialogo="Resumen")
    await app.state.casos.esperar_publicaciones()
    assert app.state.broker.tamano_actual(NombreCola.CASOS_AYUDA) == 1
    mensaje = pedido_en_cola(app)
    assert mensaje.id == r.caso["id"]  # el identificador único lo asigna quien publica
    assert (mensaje.cuerpo["agencia"], mensaje.cuerpo["descripcion"]) == ("agencia-b", "Problema")
    assert mensaje.cuerpo["reserva"]["identificador"] == ident
    assert estado_del_caso(app, r.caso["id"]) == "en_tramite"  # el viajero ve «en trámite»


async def test_la_respuesta_no_espera_a_la_agencia_ni_a_la_cola(app):
    ident = await reserva_de(app)
    await con_agencia(app)
    llenar_cola_de_casos(app)  # ni siquiera hay lugar: el viajero igual recibe «en trámite»
    r = await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "Problema")
    assert r.estado == "ok" and r.caso["estado"] == "en_tramite"
    await app.state.casos.esperar_publicaciones()


async def test_AC_REF_05_10_cola_llena_guarda_en_tramite_y_publica_cuando_hay_lugar(app):
    ident = await reserva_de(app)
    await con_agencia(app)
    llenar_cola_de_casos(app)
    esperas: list[float] = []

    async def dormir(s):
        esperas.append(s)
        if len(esperas) == 2:  # tras el segundo reintento se libera un lugar
            vaciar_un_lugar(app)
    app.state.casos._dormir = dormir

    r = await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "Problema")
    assert r.caso["estado"] == "en_tramite"
    await app.state.casos.esperar_publicaciones()

    assert esperas == [1.0, 2.0]  # espera creciente
    assert estado_del_caso(app, r.caso["id"]) == "en_tramite"  # sigue en trámite
    assert r.caso["id"] in [m.id for m in app.state.broker._colas[NombreCola.CASOS_AYUDA]]  # se publicó


async def test_AC_REF_05_11_cola_llena_agotados_los_reintentos_queda_sin_entregar(app):
    ident = await reserva_de(app)
    await con_agencia(app)
    llenar_cola_de_casos(app)
    esperas: list[float] = []
    avisos: list[Aviso] = []

    async def dormir(s):
        esperas.append(s)
    app.state.casos._dormir = dormir
    app.state.broker._avisar = avisos.append

    r = await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "Problema")
    await app.state.casos.esperar_publicaciones()

    assert esperas == [1.0, 2.0, 4.0]  # 3 reintentos con espera de 1 s, 2 s y 4 s
    assert estado_del_caso(app, r.caso["id"]) == "sin_entregar"
    assert r.caso["id"] not in [m.id for m in app.state.broker._colas[NombreCola.CASOS_AYUDA]]
    assert [a.tipo for a in avisos] == ["cola_llena"] * 4  # operaciones se entera de la saturación


async def test_si_el_caso_ya_no_esta_en_tramite_no_se_publica(app):
    from trotamundos.dominio.agencias import EstadoCaso
    ident = await reserva_de(app)
    await con_agencia(app)
    r = await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "Problema")
    await app.state.casos.esperar_publicaciones()
    await app.state.casos.aplicar_estado_caso(r.caso["id"], EstadoCaso.ABIERTO)
    antes = app.state.broker.tamano_actual(NombreCola.CASOS_AYUDA)
    await app.state.casos._publicar_con_reintentos(r.caso["id"])
    assert app.state.broker.tamano_actual(NombreCola.CASOS_AYUDA) == antes
