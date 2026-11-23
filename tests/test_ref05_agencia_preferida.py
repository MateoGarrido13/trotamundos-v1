# SPEC: SPEC-REF-05
# ELEMENTO PASO 5: Orquestador de viajes, agencia preferida (ITERACION_4)
# ADRs: ADR-IT4-010
# DRIVERS: REF-05, CON-02
"""T-REF-05-02: elegirAgenciaPreferida con consentimiento explícito."""
import pytest

from tests.ref04_util import LUIS, contar
from tests.ref05_util import app  # noqa: F401
from trotamundos.persistencia.repositorio_casos import RepositorioCasos

pytestmark = pytest.mark.db


def preferencia(app, cuenta=LUIS):
    return app.state.base_viajes.leer(lambda c: RepositorioCasos.preferencia(c, cuenta))


async def test_AC_REF_05_06_sin_consentimiento_no_se_guarda_la_agencia(app, bases_limpias):
    for consentimiento in (False, None, "si", 1):  # solo un consentimiento explícito vale
        r = await app.state.casos.elegir_agencia(LUIS, "agencia-a", consentimiento)
        assert (r.estado, r.motivo) == ("rechazado", "sin_consentimiento"), consentimiento
    assert preferencia(app) is None
    assert contar(bases_limpias, "preferencia_agencia") == [0, 0]


async def test_una_agencia_que_no_esta_registrada_se_rechaza_sin_guardar(app, bases_limpias):
    r = await app.state.casos.elegir_agencia(LUIS, "agencia-fantasma", True)
    assert (r.estado, r.motivo) == ("rechazado", "agencia_no_registrada")
    assert contar(bases_limpias, "preferencia_agencia") == [0, 0]


async def test_con_consentimiento_la_agencia_queda_guardada_en_las_dos_bases(app, bases_limpias):
    assert (await app.state.casos.elegir_agencia(LUIS, "agencia-a", True)).estado == "ok"
    assert preferencia(app) == "agencia-a"
    assert contar(bases_limpias, "preferencia_agencia") == [1, 1]


async def test_se_puede_cambiar_de_agencia_y_es_por_cuenta(app):
    await app.state.casos.elegir_agencia(LUIS, "agencia-a", True)
    await app.state.casos.elegir_agencia(LUIS, "agencia-b", True)
    await app.state.casos.elegir_agencia("ana", "agencia-a", True)
    assert preferencia(app) == "agencia-b" and preferencia(app, "ana") == "agencia-a"


async def test_consultar_la_agencia_preferida_devuelve_el_nombre_y_el_numero_de_contacto(app):
    await app.state.casos.elegir_agencia(LUIS, "agencia-b", True)
    assert await app.state.casos.consultar_agencia_preferida(LUIS) == {
        "agencia": "agencia-b", "contacto": app.state.configuracion.agencias.contactos["agencia-b"]}


async def test_consultar_sin_agencia_elegida_lo_indica_y_no_es_un_error(app):
    assert await app.state.casos.consultar_agencia_preferida(LUIS) == {"agencia": None, "contacto": None}


async def test_el_contacto_es_el_de_la_agencia_configurada_y_es_por_cuenta(app):
    await app.state.casos.elegir_agencia(LUIS, "agencia-a", True)
    await app.state.casos.elegir_agencia("ana", "agencia-b", True)
    assert (await app.state.casos.consultar_agencia_preferida(LUIS))["agencia"] == "agencia-a"
    assert (await app.state.casos.consultar_agencia_preferida("ana"))["agencia"] == "agencia-b"
    assert (await app.state.casos.consultar_agencia_preferida("otro"))["agencia"] is None
