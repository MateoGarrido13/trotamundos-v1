# SPEC: SPEC-REF-07
# ELEMENTO PASO 5: Asistente y Orquestador, escrituras de primer nivel (RONDA_2/ITERACION_1)
# ADRs: ADR-IT6-002
# DRIVERS: REF-07, QA-SEG-02
"""T-REF-07-06: las escrituras de primer nivel, con el Orquestador real y las dos bases."""
import pytest

from tests.ref04_util import ANA, INTRUSO, ITIN, LUIS, app, asientos, contar, solicitud  # noqa: F401
from tests.ref07_util import CFG, confirmar
from trotamundos.asistente.asistente import MENU
from trotamundos.asistente.motor import MotorSimulado
from trotamundos.composicion import ensamblar_asistente

pytestmark = pytest.mark.db


@pytest.fixture
def motor():
    return MotorSimulado()


@pytest.fixture
def asistente(app, motor):
    return ensamblar_asistente(app, motor, CFG)


async def reserva(app, actor=LUIS, clave="alta", lugar="Coliseo"):
    r = await app.state.gestion.agregar(actor, ITIN, clave, solicitud(lugar=lugar))
    return r.reserva["identificador"]


def lugares(app):
    """Las reservas vigentes de los dos viajes: `roma` y el viaje por defecto del asistente."""
    return sorted(r.lugar for r in app.state.repositorio.reservas_de(["roma", "viaje-familia"]))


def de_asistente(app, operacion, resultado):
    return [a for a in asientos(app) if a["operacion"] == operacion and a["resultado"] == resultado]


async def test_AC_REF_07_01_reprogramar_se_propone_y_al_confirmar_llama_a_actualizar_reserva(app, asistente, motor):
    ident = await reserva(app)
    motor.respuestas = [{"tipo": "reprogramar", "referencia": "Coliseo", "cambios": {"lugar": "Foro Romano"}}]
    p = await asistente.turno(LUIS, ITIN, "reprogramar el Coliseo", None)
    assert p.tipo == "propuesta" and lugares(app) == ["Coliseo"]  # sin confirmar no se escribió nada

    r = await confirmar(asistente, p, LUIS, ITIN)
    assert r.tipo == "resultado" and lugares(app) == ["Foro Romano"]
    [asiento] = de_asistente(app, "actualizar", "permitido")  # con la identidad del actor y su auditoría
    assert (asiento["cuenta"], asiento["reserva"]) == (LUIS, ident) and asiento["clave"].startswith("asist-")


async def test_las_otras_escrituras_de_primer_nivel_tambien_se_hacen_al_confirmar(app, asistente, motor):
    ident = await reserva(app)
    a = await asistente.turno(LUIS, ITIN, "Quiero agregar una actividad en Florencia el 2026-12-12", None)
    assert a.tipo == "propuesta" and lugares(app) == ["Coliseo"]
    assert (await confirmar(asistente, a, LUIS, ITIN)).tipo == "resultado"
    assert lugares(app) == ["Coliseo", "Florencia"]
    [alta] = [r for r in app.state.repositorio.reservas_de(["viaje-familia"])]
    assert alta.creado_por == LUIS and alta.origen.value == "manual"

    motor.respuestas = [{"tipo": "eliminarReserva", "referencia": ident}]
    e = await asistente.turno(LUIS, ITIN, "eliminar", None)
    assert (await confirmar(asistente, e, LUIS, ITIN)).tipo == "resultado"
    assert lugares(app) == ["Florencia"]  # la baja lógica saca de la vista solo la reserva eliminada
    assert len(de_asistente(app, "eliminar", "permitido")) == 1


async def test_AC_REF_07_02_reintentar_la_confirmacion_no_aplica_la_reprogramacion_dos_veces(app, asistente, motor, bases_limpias):
    await reserva(app)
    motor.respuestas = [{"tipo": "reprogramar", "referencia": "Coliseo", "cambios": {"lugar": "Foro Romano"}}]
    p = await asistente.turno(LUIS, ITIN, "reprogramar", None)
    primera = await confirmar(asistente, p, LUIS, ITIN)
    segunda = await confirmar(asistente, p, LUIS, ITIN)  # el cliente reintenta con el mismo contexto
    assert primera.tipo == segunda.tipo == "resultado"
    assert len(de_asistente(app, "actualizar", "permitido")) == 1  # el Orquestador no la aplicó por segunda vez
    assert contar(bases_limpias, "auditoria") == [2, 2]  # el alta y una sola reprogramación
    # la misma clave viajó en las dos confirmaciones
    assert {a["clave"] for a in de_asistente(app, "actualizar", "permitido")} == {a["clave"] for a in de_asistente(app, "actualizar", "permitido")}


async def test_dos_acciones_propuestas_distintas_usan_claves_distintas(app, asistente, motor):
    await reserva(app)
    claves = []
    for lugar in ("Foro", "Vaticano"):
        motor.respuestas = [{"tipo": "reprogramar", "referencia": "Coliseo" if lugar == "Foro" else "Foro",
                             "cambios": {"lugar": lugar}}]
        p = await asistente.turno(LUIS, ITIN, "reprogramar", None)
        await confirmar(asistente, p, LUIS, ITIN)
        claves.append(asistente._firma.verificar(p.contexto, LUIS, ITIN).pendiente.clave)
    assert len(set(claves)) == 2 and lugares(app) == ["Vaticano"]


async def test_AC_REF_07_03_sin_permiso_no_se_escribe_queda_auditado_y_se_ofrece_derivar(app, asistente, motor, bases_limpias):
    ident = await reserva(app)
    # registrar: una cuenta sin membresía propone y confirma
    p = await asistente.turno(INTRUSO, ITIN, "Quiero agregar una actividad en Florencia el 2026-12-12", None)
    assert p.tipo == "propuesta"
    r = await confirmar(asistente, p, INTRUSO, ITIN)
    assert r.tipo == "denegado" and "derivar" in r.texto and "derivar_a_la_agencia" in r.menu
    assert lugares(app) == ["Coliseo"] and contar(bases_limpias, "reserva") == [1, 1]  # no se escribió
    [a] = de_asistente(app, "agregar", "denegado")
    assert (a["cuenta"], a["permiso"]) == (INTRUSO, "registrar")

    # reprogramar: la misma denegación y auditoría que en la gestión manual
    q = await asistente.accion(INTRUSO, ITIN, {"tipo": "reprogramar", "reserva_id": ident, "cambios": {"lugar": "X"}}, None)
    assert q.tipo == "propuesta"
    assert (await confirmar(asistente, q, INTRUSO, ITIN)).tipo == "denegado"
    assert lugares(app) == ["Coliseo"]
    [b] = de_asistente(app, "actualizar", "denegado")
    assert (b["cuenta"], b["permiso"], b["reserva"]) == (INTRUSO, "modificar", ident)


async def test_un_participante_no_modifica_lo_de_otro_ni_por_el_asistente(app, asistente, motor):
    ajena = await reserva(app, actor=ANA, clave="ana-1", lugar="Hotel de Ana")
    motor.respuestas = [{"tipo": "eliminarReserva", "referencia": ajena}]
    p = await asistente.turno(LUIS, ITIN, "eliminar la reserva de Ana", None)  # Luis puede verla
    assert p.tipo == "propuesta"
    r = await confirmar(asistente, p, LUIS, ITIN)
    assert r.tipo == "denegado"
    assert lugares(app) == ["Hotel de Ana"]
    assert [a["cuenta"] for a in de_asistente(app, "eliminar", "denegado")] == [LUIS]


async def test_un_rechazo_de_la_validacion_del_orquestador_se_informa_con_su_motivo(app, asistente):
    p = await asistente.accion(LUIS, ITIN, {"tipo": "reprogramar", "reserva_id": "no-existe", "cambios": {"lugar": "X"}}, None)
    r = await confirmar(asistente, p, LUIS, ITIN)
    assert (r.tipo, r.motivo) == ("rechazo", "no_existe") and "no existe" in r.texto


async def test_si_el_orquestador_falla_la_accion_sigue_pendiente_y_se_puede_reintentar(app, asistente, motor, monkeypatch):
    await reserva(app)
    motor.respuestas = [{"tipo": "reprogramar", "referencia": "Coliseo", "cambios": {"lugar": "Foro"}}]
    p = await asistente.turno(LUIS, ITIN, "reprogramar", None)
    real = app.state.gestion.actualizar

    async def falla(*a, **k):
        raise RuntimeError("el Orquestador no responde")
    monkeypatch.setattr(app.state.gestion, "actualizar", falla)
    r = await confirmar(asistente, p, LUIS, ITIN)
    assert (r.tipo, r.motivo) == ("rechazo", "error") and lugares(app) == ["Coliseo"]
    assert asistente._firma.verificar(r.contexto, LUIS, ITIN).pendiente is not None  # sigue pendiente
    monkeypatch.setattr(app.state.gestion, "actualizar", real)
    assert (await confirmar(asistente, r, LUIS, ITIN)).tipo == "resultado" and lugares(app) == ["Foro"]
