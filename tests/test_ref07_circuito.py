# SPEC: SPEC-REF-07
# ELEMENTO PASO 5: Circuit Breaker del proveedor de modelo (RONDA_2/ITERACION_2)
# ADRs: ADR-IT7-004
# DRIVERS: REF-07, QA-DIS-02
"""T-REF-07-04: el Circuit Breaker, con reloj inyectado."""
import pytest

from trotamundos.asistente.circuito import CircuitBreaker, EstadoCircuito

E = EstadoCircuito


class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def cb(reloj):
    return CircuitBreaker(umbral=5, apertura_segundos=30, reloj=reloj)


def fallar(cb, n):
    for _ in range(n):
        assert cb.permitir()
        cb.fallo()


def test_arranca_cerrado_y_permite_llamar_al_proveedor(cb):
    assert cb.estado is E.CERRADO and cb.permitir()


def test_a_los_cinco_fallos_consecutivos_se_abre(cb):
    fallar(cb, 4)
    assert cb.estado is E.CERRADO and cb.permitir()
    cb.fallo()
    assert cb.estado is E.ABIERTO and not cb.permitir()


def test_AC_REF_07_12_un_exito_reinicia_la_cuenta_y_hacen_falta_cinco_nuevos(cb):
    fallar(cb, 4)
    cb.exito()
    assert cb.fallos_consecutivos == 0
    fallar(cb, 4)
    assert cb.estado is E.CERRADO  # cuatro nuevos no alcanzan
    fallar(cb, 1)
    assert cb.estado is E.ABIERTO  # el quinto sí


def test_abierto_no_deja_pasar_ninguna_llamada(cb):
    fallar(cb, 5)
    assert [cb.permitir() for _ in range(20)] == [False] * 20


def test_AC_REF_07_11_a_los_30_segundos_pasa_a_semiabierto_y_deja_pasar_una_sola_llamada(cb, reloj):
    fallar(cb, 5)
    reloj.t += 29.9
    assert cb.estado is E.ABIERTO and not cb.permitir()
    reloj.t += 0.2
    assert cb.estado is E.SEMIABIERTO
    assert cb.permitir() is True  # la llamada de prueba
    assert cb.permitir() is False  # una sola: las demás esperan el resultado
    assert cb.permitir() is False


def test_AC_REF_07_11_si_la_llamada_de_prueba_responde_se_cierra(cb, reloj):
    fallar(cb, 5)
    reloj.t += 30
    assert cb.permitir()
    cb.exito()
    assert cb.estado is E.CERRADO and cb.fallos_consecutivos == 0
    assert cb.permitir() and cb.permitir()


def test_AC_REF_07_11_si_la_llamada_de_prueba_falla_vuelve_a_abrirse_otros_30_segundos(cb, reloj):
    fallar(cb, 5)
    reloj.t += 30
    assert cb.permitir()
    cb.fallo()
    assert cb.estado is E.ABIERTO and not cb.permitir()
    reloj.t += 29
    assert cb.estado is E.ABIERTO  # volvió a contar desde la reapertura
    reloj.t += 1
    assert cb.estado is E.SEMIABIERTO


def test_los_parametros_son_configurables(reloj):
    cb = CircuitBreaker(umbral=2, apertura_segundos=0.3, reloj=reloj)
    fallar(cb, 2)
    assert cb.estado is E.ABIERTO
    reloj.t += 0.3
    assert cb.estado is E.SEMIABIERTO
