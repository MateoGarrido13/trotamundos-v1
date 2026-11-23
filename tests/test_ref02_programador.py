# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Adaptador de correo (sondeo periódico) (ITERACION_3)
# ADRs: ADR-IT3-003
# DRIVERS: REF-02
"""T-REF-02-05: ProgramadorSondeo."""
from datetime import timedelta

import pytest

from tests.test_ref02_adaptador import T0, Entorno, _vaciar
from trotamundos.entrada.programador_sondeo import ProgramadorSondeo


@pytest.fixture
def entorno(cfg_broker):
    return Entorno(cfg_broker)


async def test_AC_REF_02_09_dos_sondeos_publican_el_mismo_identificador(entorno):
    entorno.autorizar()
    entorno.correo(message_id="<m1@x>")
    prog = ProgramadorSondeo(entorno.adaptador, entorno.gestor, entorno.cfg)
    await prog.tick(T0)
    await prog.tick(T0 + timedelta(minutes=15))
    assert [m.id for m in await _vaciar(entorno.broker)] == ["<m1@x>", "<m1@x>"]


async def test_el_programador_recorre_todos_los_titulares_y_un_fallo_no_afecta_a_los_otros(entorno):
    from trotamundos.entrada.api_correo import ErrorApiCorreo

    entorno.autorizar("a", "ta")
    entorno.autorizar("b", "tb")
    entorno.correo(message_id="<a@x>", titular="a")
    entorno.correo(message_id="<b@x>", titular="b")
    original = entorno.api.leer_mensajes

    async def falla_a(token, desde):
        if token == "ta":
            raise ErrorApiCorreo("caída")
        return await original(token, desde)

    entorno.api.leer_mensajes = falla_a
    res = await ProgramadorSondeo(entorno.adaptador, entorno.gestor, entorno.cfg).tick(T0)
    assert isinstance(res["a"], ErrorApiCorreo) and res["b"].publicados == 1
    assert [m.id for m in await _vaciar(entorno.broker)] == ["<b@x>"]
