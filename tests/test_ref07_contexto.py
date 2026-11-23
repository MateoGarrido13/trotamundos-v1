# SPEC: SPEC-REF-07
# ELEMENTO PASO 5: Contexto firmado (RONDA_2/ITERACION_1)
# ADRs: ADR-IT6-001
# DRIVERS: REF-07
"""T-REF-07-03: el contexto firmado."""
import pytest

from trotamundos.asistente.contexto import AccionPendiente, FirmaContexto

PENDIENTE = AccionPendiente(tipo="reprogramar", clave="asist-1", datos={"reserva_id": "r1", "cambios": {"lugar": "X"}},
                            descripcion="Cambiar el lugar a X")


class Reloj:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def firma(reloj):
    return FirmaContexto("clave-de-prueba", vigencia_segundos=30 * 60, reloj=reloj)


def contexto(firma, **extra):
    c = firma.nuevo("luis", "familia")
    c.mensajes, c.pendiente = ["hola"], PENDIENTE
    for k, v in extra.items():
        setattr(c, k, v)
    return c


def test_ida_y_vuelta_conserva_la_accion_pendiente_con_su_clave_y_los_mensajes(firma):
    token = firma.firmar(contexto(firma))
    c = firma.verificar(token, "luis", "familia")
    assert c is not None and c.mensajes == ["hola"]
    assert (c.pendiente.tipo, c.pendiente.clave, c.pendiente.datos) == (
        "reprogramar", "asist-1", {"reserva_id": "r1", "cambios": {"lugar": "X"}})


def test_AC_REF_07_16_un_contexto_con_la_firma_alterada_se_descarta(firma):
    cuerpo, mac = firma.firmar(contexto(firma)).split(".")
    assert firma.verificar(f"{cuerpo}.{'A' * len(mac)}", "luis", "familia") is None  # firma cambiada
    otro = firma.firmar(contexto(firma, mensajes=["otro"])).split(".")[0]
    assert firma.verificar(f"{otro}.{mac}", "luis", "familia") is None  # cuerpo cambiado, firma vieja
    assert FirmaContexto("otra-clave").verificar(f"{cuerpo}.{mac}", "luis", "familia") is None  # otra clave


@pytest.mark.parametrize("token", [None, "", "sin-punto", "a.b.c", "....", "x.y", 42])
def test_un_contexto_ausente_o_mal_formado_se_descarta(firma, token):
    assert firma.verificar(token, "luis", "familia") is None


def test_AC_REF_07_17_un_contexto_vencido_se_descarta(firma, reloj):
    token = firma.firmar(contexto(firma))
    reloj.t += 30 * 60 - 1
    assert firma.verificar(token, "luis", "familia") is not None  # aún vale
    reloj.t += 2
    assert firma.verificar(token, "luis", "familia") is None  # venció


def test_un_contexto_firmado_para_una_cuenta_o_un_itinerario_no_sirve_para_otro(firma):
    token = firma.firmar(contexto(firma))
    assert firma.verificar(token, "ana", "familia") is None  # otra cuenta no confirma lo que propuso Luis
    assert firma.verificar(token, "luis", "otro-itinerario") is None


def test_sin_clave_no_se_puede_firmar():
    with pytest.raises(ValueError, match="TROTA_CLAVE_ASISTENTE"):
        FirmaContexto("")


def test_cada_firma_renueva_la_vigencia(firma, reloj):
    c = contexto(firma)
    reloj.t += 20 * 60
    token = firma.firmar(c)  # un turno nuevo: vuelve a valer 30 minutos
    reloj.t += 20 * 60
    assert firma.verificar(token, "luis", "familia") is not None
