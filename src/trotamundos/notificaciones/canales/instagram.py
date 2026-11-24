# SPEC: SPEC-COMP-08
# ELEMENTO PASO 5: ICanal, adaptador de Instagram (ITERACION_3)
# ADRs: ADR-IT3-004
# DRIVERS: QA-INT-02
"""Canal Instagram (simulado)."""
from trotamundos.notificaciones.canales.base import CanalSimulado, canal


@canal("instagram")
class CanalInstagram(CanalSimulado):
    pass
