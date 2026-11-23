# SPEC: SPEC-REF-05
# ELEMENTO PASO 5: Orquestador de viajes, reportar un problema (ITERACION_4)
# ADRs: ADR-IT4-010, ADR-IT4-007, ADR-IT4-008
# DRIVERS: REF-05
"""T-REF-05-03: reportar un problema, en una sola transacción."""
import pytest

from tests.ref04_util import ANA, INTRUSO, ITIN, LUIS, asientos, contar
from tests.ref05_util import app, con_agencia, reserva_de  # noqa: F401
from trotamundos.persistencia.repositorio_casos import RepositorioCasos

pytestmark = pytest.mark.db


def casos(app, cuenta=LUIS):
    return app.state.base_viajes.leer(lambda c: RepositorioCasos.casos_de(c, cuenta))


async def test_AC_REF_05_01_reportar_guarda_el_caso_en_tramite_con_la_agencia_vigente(app, bases_limpias):
    ident = await reserva_de(app)
    await con_agencia(app, agencia="agencia-a")
    r = await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "El hotel no tiene mi reserva")
    assert r.estado == "ok" and r.caso["estado"] == "en_tramite" and r.caso["agencia"] == "agencia-a"
    [caso] = casos(app)
    assert (caso.estado, caso.agencia, caso.reserva_id, caso.cuenta_id) == ("en_tramite", "agencia-a", ident, LUIS)
    assert contar(bases_limpias, "caso") == [1, 1]
    ultimo = [a for a in asientos(app) if a["operacion"] == "reportar_caso"]
    assert [(a["resultado"], a["permiso"], a["reserva"]) for a in ultimo] == [("permitido", "registrar", ident)]
    await app.state.casos.esperar_publicaciones()


async def test_el_caso_conserva_la_agencia_que_estaba_vigente_al_reportar(app):
    ident = await reserva_de(app)
    await con_agencia(app, agencia="agencia-a")
    await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "Problema")
    await con_agencia(app, agencia="agencia-b")  # cambia la preferencia después
    assert [c.agencia for c in casos(app)] == ["agencia-a"]
    await app.state.casos.esperar_publicaciones()


async def test_AC_REF_05_07_sin_agencia_preferida_no_se_crea_el_caso(app, bases_limpias):
    ident = await reserva_de(app)  # el viajero nunca eligió agencia ni dio consentimiento
    r = await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "Problema")
    assert (r.estado, r.motivo) == ("rechazado", "sin_agencia_o_consentimiento")
    assert contar(bases_limpias, "caso") == [0, 0]
    assert [a["resultado"] for a in asientos(app) if a["operacion"] == "reportar_caso"] == ["rechazado"]


async def test_AC_REF_05_07_si_el_consentimiento_se_rechazo_tampoco_se_crea_el_caso(app, bases_limpias):
    ident = await reserva_de(app)
    await app.state.casos.elegir_agencia(LUIS, "agencia-a", False)  # rechazado: no queda guardado
    r = await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "Problema")
    assert r.motivo == "sin_agencia_o_consentimiento" and contar(bases_limpias, "caso") == [0, 0]


async def test_AC_REF_05_08_sin_permiso_registrar_se_deniega_con_asiento(app, bases_limpias):
    ident = await reserva_de(app)
    await con_agencia(app, actor=INTRUSO)  # elegir agencia no requiere itinerario
    r = await app.state.casos.reportar(INTRUSO, ITIN, "k1", ident, "Problema")
    assert r.estado == "denegado"
    assert contar(bases_limpias, "caso") == [0, 0]
    [asiento] = [a for a in asientos(app) if a["operacion"] == "reportar_caso"]
    assert (asiento["cuenta"], asiento["resultado"], asiento["permiso"]) == (INTRUSO, "denegado", "registrar")


async def test_sin_permiso_no_se_revela_si_la_reserva_existe(app):
    await con_agencia(app, actor=INTRUSO)
    a = await app.state.casos.reportar(INTRUSO, ITIN, "k1", await reserva_de(app), "x")
    b = await app.state.casos.reportar(INTRUSO, ITIN, "k2", "no-existe", "x")
    assert (a.estado, a.motivo) == (b.estado, b.motivo) == ("denegado", None)


async def test_un_participante_con_permiso_registrar_puede_reportar(app):
    ident = await reserva_de(app, actor=ANA, clave="ana-1")
    await con_agencia(app, actor=LUIS)
    assert (await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "Problema")).estado == "ok"
    await app.state.casos.esperar_publicaciones()


async def test_AC_REF_05_09_la_misma_clave_no_abre_un_segundo_caso(app, bases_limpias):
    ident = await reserva_de(app)
    await con_agencia(app)
    a = await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "Problema")
    b = await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "Otro texto")  # doble toque
    assert b.repetida and b.caso == a.caso
    assert contar(bases_limpias, "caso") == [1, 1]
    await app.state.casos.esperar_publicaciones()
    assert app.state.broker.tamano_actual("casos_ayuda") == 1  # y un solo pedido en la cola


async def test_la_clave_de_un_caso_no_choca_con_una_clave_de_reserva(app):
    ident = await reserva_de(app, clave="k1")  # misma clave que usará el reporte
    await con_agencia(app)
    r = await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "Problema")
    assert r.estado == "ok" and not r.repetida
    await app.state.casos.esperar_publicaciones()


async def test_AC_REF_05_17_el_resumen_del_dialogo_queda_en_el_caso_y_en_el_pedido(app):
    ident = await reserva_de(app)
    await con_agencia(app)
    r = await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "Perdí el vuelo",
                                      resumen_dialogo="El asistente no pudo reprogramar")
    assert r.caso["resumen_dialogo"] == "El asistente no pudo reprogramar"
    [caso] = casos(app)
    assert caso.resumen_dialogo == "El asistente no pudo reprogramar"
    assert caso.pedido["resumen_dialogo"] == "El asistente no pudo reprogramar"
    await app.state.casos.esperar_publicaciones()


async def test_el_pedido_solo_lleva_lo_que_el_viajero_consintio(app):
    ident = await reserva_de(app)
    await reserva_de(app, actor=ANA, clave="otra", viaje="paris")  # otra reserva del itinerario
    await con_agencia(app)
    await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "Problema")
    [caso] = casos(app)
    assert set(caso.pedido) == {"id_caso", "agencia", "reserva", "descripcion", "resumen_dialogo"}
    assert caso.pedido["reserva"]["identificador"] == ident
    assert set(caso.pedido["reserva"]) == {"identificador", "tipo", "lugar", "inicio", "fin"}
    texto = str(caso.pedido)
    assert ANA not in texto and "paris" not in texto and ITIN not in texto  # sin miembros ni otras reservas
    await app.state.casos.esperar_publicaciones()


@pytest.mark.parametrize("reserva,descripcion,motivo", [
    ("no-existe", "Problema", "reserva_inexistente"),
    ("RESERVA", "   ", "descripcion_invalida"),
    ("RESERVA", "x" * 2001, "descripcion_invalida"),
    ("RESERVA", None, "descripcion_invalida"),
])
async def test_reserva_inexistente_o_descripcion_invalida_no_crea_el_caso(app, bases_limpias, reserva, descripcion, motivo):
    ident = await reserva_de(app)
    await con_agencia(app)
    r = await app.state.casos.reportar(LUIS, ITIN, "k1", ident if reserva == "RESERVA" else reserva, descripcion)
    assert (r.estado, r.motivo) == ("rechazado", motivo)
    assert contar(bases_limpias, "caso") == [0, 0]


async def test_una_reserva_de_otro_itinerario_o_dada_de_baja_se_rechaza(app):
    ident = await reserva_de(app)
    await con_agencia(app)
    app.state.base_viajes.escribir(lambda c: c.execute("INSERT INTO membresia VALUES ('otro', 'luis', 'participante')"))
    r = await app.state.casos.reportar(LUIS, "otro", "k1", ident, "Problema")  # con permiso, pero no es de ese itinerario
    assert (r.estado, r.motivo) == ("rechazado", "reserva_inexistente")
    await app.state.gestion.eliminar(LUIS, ITIN, ident, "baja")
    r = await app.state.casos.reportar(LUIS, ITIN, "k2", ident, "Problema")
    assert (r.estado, r.motivo) == ("rechazado", "reserva_inexistente")


async def test_un_rechazo_no_memoriza_la_clave_y_se_puede_corregir(app):
    ident = await reserva_de(app)
    malo = await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "Problema")  # sin agencia
    await con_agencia(app)
    bueno = await app.state.casos.reportar(LUIS, ITIN, "k1", ident, "Problema")
    assert malo.estado == "rechazado" and bueno.estado == "ok" and not bueno.repetida
    await app.state.casos.esperar_publicaciones()
