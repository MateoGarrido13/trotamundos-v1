# SPEC: SPEC-REF-07
# ELEMENTO PASO 5: IMotorConversacional, intención tipada (RONDA_2/ITERACION_1)
# ADRs: ADR-IT6-004
# DRIVERS: REF-07, QA-SEG-04
"""T-REF-07-01: el conjunto cerrado de intenciones y el motor simulado."""
import pytest

from trotamundos.asistente.intenciones import FUERA_DE_ALCANCE, Intencion, TipoIntencion, normalizar
from trotamundos.asistente.motor import ContextoMotor, ErrorMotor, MotorSimulado

T = TipoIntencion


@pytest.mark.parametrize("crudo", [
    {"tipo": "borrarBaseDeDatos"}, {"tipo": "ejecutarCodigo", "datos": {"cmd": "rm -rf /"}},
    {"tipo": "reprogramar", "cambios": "no es un objeto"}, {"tipo": "consultarEstado", "referencia": 42},
    {"sin_tipo": True}, {}, "consultarEstado", "texto libre del modelo", None, 42, ["consultarEstado"],
    {"tipo": None}, {"tipo": "FUERADEALCANCE"},
])
def test_AC_REF_07_07_una_intencion_fuera_del_conjunto_cerrado_se_trata_como_fuera_de_alcance(crudo):
    assert normalizar(crudo) == FUERA_DE_ALCANCE


@pytest.mark.parametrize("tipo", [t.value for t in T])
def test_las_seis_intenciones_del_conjunto_cerrado_se_aceptan(tipo):
    assert normalizar({"tipo": tipo}).tipo.value == tipo


def test_una_intencion_valida_conserva_sus_datos_y_ignora_lo_que_no_conoce():
    i = normalizar({"tipo": "reprogramar", "referencia": "Roma", "cambios": {"inicio": "2026-12-10"},
                    "campo_inventado": "x"})
    assert (i.tipo, i.referencia, i.cambios) == (T.REPROGRAMAR, "Roma", {"inicio": "2026-12-10"})
    assert not hasattr(i, "campo_inventado")
    assert normalizar(i) is i  # una intención ya tipada pasa tal cual


RESERVAS = ({"identificador": "res-1", "tipo": "hotel", "lugar": "Roma"},
            {"identificador": "res-2", "tipo": "vuelo", "lugar": "Lima"})


@pytest.mark.parametrize("mensaje,tipo,referencia", [
    ("Quiero reprogramar mi hotel de Roma al 2026-12-10", T.REPROGRAMAR, "Roma"),
    ("¿Cómo está mi reserva de Lima?", T.CONSULTAR_ESTADO, "Lima"),
    ("Quiero eliminar la reserva res-2", T.ELIMINAR_RESERVA, "res-2"),
    ("Necesito un reembolso del vuelo", T.CASO_COMPLEJO, "vuelo"),
    ("El proveedor no responde y quiero escalar esto", T.CASO_COMPLEJO, None),
    ("Cuál es la capital de Francia", T.FUERA_DE_ALCANCE, None),
    ("Contame un chiste", T.FUERA_DE_ALCANCE, None),
])
async def test_el_motor_simulado_interpreta_por_reglas(mensaje, tipo, referencia):
    i = normalizar(await MotorSimulado().interpretar(mensaje, ContextoMotor(reservas=RESERVAS)))
    assert (i.tipo, i.referencia) == (tipo, referencia)


async def test_el_motor_simulado_extrae_fechas_y_datos_de_una_actividad_nueva():
    motor = MotorSimulado()
    r = normalizar(await motor.interpretar("Reprogramar mi hotel de Roma del 2026-12-10 al 2026-12-15", ContextoMotor(reservas=RESERVAS)))
    assert r.cambios == {"inicio": "2026-12-10", "fin": "2026-12-15"}
    a = normalizar(await motor.interpretar("Quiero agregar una actividad en Florencia el 2026-12-12", ContextoMotor()))
    assert a.tipo is T.AGREGAR_RESERVA
    assert a.datos == {"tipo": "actividad", "lugar": "Florencia", "inicio": "2026-12-12", "fin": "2026-12-12"}


async def test_el_motor_simulado_permite_inyectar_demora_caida_y_respuestas():
    esperas = []

    async def dormir(s):
        esperas.append(s)
    motor = MotorSimulado(dormir=dormir)
    motor.demora_segundos = 7
    await motor.interpretar("hola", ContextoMotor())
    assert esperas == [7]
    motor.caida = True
    with pytest.raises(ErrorMotor):
        await motor.interpretar("hola", ContextoMotor())
    motor.caida = False
    motor.respuestas = [{"tipo": "consultarEstado"}]
    assert (await motor.interpretar("cualquier cosa", ContextoMotor()))["tipo"] == "consultarEstado"
    assert motor.llamadas == 3
