# SPEC: SPEC-REF-05
# ELEMENTO PASO 5: IAgencia, estados del caso (ITERACION_4)
# ADRs: ADR-IT4-010
# DRIVERS: REF-05
"""T-REF-05-01: los estados solo avanzan."""
import itertools

import pytest

from trotamundos.dominio.agencias import EstadoCaso, PedidoCaso, puede_pasar

E = EstadoCaso
AVANCE = [E.EN_TRAMITE, E.ABIERTO, E.EN_CURSO, E.RESUELTO]


def test_AC_REF_05_15_la_regla_de_avance_ignora_lo_que_retrocede():
    assert not puede_pasar(E.EN_CURSO, E.ABIERTO)  # el caso de la spec
    for actual, nuevo in itertools.product(AVANCE, AVANCE):
        assert puede_pasar(actual, nuevo) is (AVANCE.index(nuevo) > AVANCE.index(actual)), (actual, nuevo)


@pytest.mark.parametrize("actual,nuevo", [(E.EN_TRAMITE, E.ABIERTO), (E.EN_TRAMITE, E.EN_CURSO),
                                          (E.EN_TRAMITE, E.RESUELTO), (E.ABIERTO, E.EN_CURSO),
                                          (E.ABIERTO, E.RESUELTO), (E.EN_CURSO, E.RESUELTO)])
def test_los_estados_avanzan(actual, nuevo):
    assert puede_pasar(actual, nuevo)


def test_un_estado_repetido_no_es_un_avance():
    assert not any(puede_pasar(e, e) for e in AVANCE)


def test_sin_entregar_solo_se_alcanza_desde_en_tramite():
    assert puede_pasar(E.EN_TRAMITE, E.SIN_ENTREGAR)
    for actual in (E.ABIERTO, E.EN_CURSO, E.RESUELTO, E.SIN_ENTREGAR):
        assert not puede_pasar(actual, E.SIN_ENTREGAR)


def test_de_sin_entregar_solo_se_sale_reintentando_no_por_novedades():
    for nuevo in E:
        assert not puede_pasar(E.SIN_ENTREGAR, nuevo)


def test_resuelto_es_final():
    for nuevo in E:
        assert not puede_pasar(E.RESUELTO, nuevo)


def test_el_pedido_solo_lleva_lo_consentido():
    campos = set(PedidoCaso.model_fields)
    assert campos == {"id_caso", "agencia", "reserva", "descripcion", "resumen_dialogo"}
