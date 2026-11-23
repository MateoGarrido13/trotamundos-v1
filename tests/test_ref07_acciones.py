# SPEC: SPEC-REF-07
# ELEMENTO PASO 5: Asistente, acciones guiadas sin motor (RONDA_2/ITERACION_1)
# ADRs: ADR-IT6-004
# DRIVERS: REF-07, QA-DIS-02
"""T-REF-07-08: con el motor caído, el menú guiado sigue funcionando."""
import pytest

from tests.ref04_util import ITIN, LUIS, app, solicitud  # noqa: F401
from tests.ref07_util import CFG, confirmar
from trotamundos.asistente.motor import MotorSimulado
from trotamundos.composicion import ensamblar_asistente

pytestmark = pytest.mark.db


@pytest.fixture
def motor():
    m = MotorSimulado()
    m.caida = True  # el proveedor de modelo no responde
    return m


@pytest.fixture
def asistente(app, motor):
    return ensamblar_asistente(app, motor, CFG)


async def test_AC_REF_07_15_consultar_y_reprogramar_por_el_menu_funcionan_sin_motor(app, asistente, motor):
    r = await app.state.gestion.agregar(LUIS, ITIN, "alta", solicitud(lugar="Coliseo"))
    ident = r.reserva["identificador"]

    estado = await asistente.accion(LUIS, ITIN, {"tipo": "consultar_estado"}, None)
    assert estado.tipo == "respuesta" and "Coliseo" in estado.texto

    p = await asistente.accion(LUIS, ITIN, {"tipo": "reprogramar", "reserva_id": ident,
                                            "cambios": {"lugar": "Foro Romano"}}, estado.contexto)
    assert p.tipo == "propuesta"
    assert (await confirmar(asistente, p, LUIS, ITIN)).tipo == "resultado"
    assert [x.lugar for x in app.state.repositorio.reservas_de(["roma"])] == ["Foro Romano"]
    assert motor.llamadas == 0  # ni una llamada al proveedor


async def test_consultar_el_estado_de_una_reserva_puntual_por_el_menu(app, asistente):
    for i, lugar in enumerate(("Coliseo", "Foro")):
        await app.state.gestion.agregar(LUIS, ITIN, f"k{i}", solicitud(lugar=lugar))
    r = await asistente.accion(LUIS, ITIN, {"tipo": "consultar_estado", "reserva_id": "Foro"}, None)
    assert "Foro" in r.texto and "Coliseo" not in r.texto


@pytest.mark.parametrize("accion", [
    {"tipo": "reprogramar"}, {"tipo": "reprogramar", "reserva_id": "r1"},
    {"tipo": "reprogramar", "reserva_id": "r1", "cambios": {}}, {"tipo": "reprogramar", "reserva_id": 5, "cambios": {"a": 1}},
    {"tipo": "derivar"}, {"tipo": "derivar", "reserva_id": "r1"}, {"tipo": "borrar_todo"}, {}, {"tipo": None},
])
async def test_una_accion_incompleta_o_desconocida_se_rechaza_sin_efecto(app, asistente, accion):
    r = await asistente.accion(LUIS, ITIN, accion, None)
    assert r.tipo == "rechazo" and r.propuesta is None


async def test_una_accion_que_no_es_un_objeto_se_rechaza(asistente):
    r = await asistente.accion(LUIS, ITIN, "confirmar", None)
    assert r.tipo == "rechazo"
