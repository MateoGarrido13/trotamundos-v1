# SPEC: SPEC-REF-03
# ELEMENTO PASO 5: Mensajes en revisión (ITERACION_3)
# ADRs: ADR-IT3-008
# DRIVERS: REF-03
import pytest

from trotamundos.config import (
    Configuracion,
    ConfiguracionCorreo,
    ConfiguracionIngesta,
    ConfiguracionRevision,
)


def test_AC_REF_03_11_retencion_por_defecto_es_30_dias_y_el_tope_50():
    cfg = Configuracion()
    assert cfg.revision.retencion_dias == 30 and cfg.revision.tope_pendientes == 50


def test_AC_REF_03_11_retencion_menor_que_la_ventana_de_sondeo_se_rechaza():
    with pytest.raises(ValueError, match="ventana de sondeo"):
        Configuracion(revision=ConfiguracionRevision(retencion_dias=3))
    with pytest.raises(ValueError, match="ventana de sondeo"):
        Configuracion(ingesta=ConfiguracionIngesta(retencion_ids_dias=3))
    # una ventana más corta vuelve válida una retención menor
    Configuracion(correo=ConfiguracionCorreo(ventana_sondeo_dias=2),
                  revision=ConfiguracionRevision(retencion_dias=3))
