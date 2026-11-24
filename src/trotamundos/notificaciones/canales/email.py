# SPEC: SPEC-COMP-08
# ELEMENTO PASO 5: ICanal, adaptador de Email (ITERACION_3)
# ADRs: ADR-IT3-004
# DRIVERS: QA-INT-02
"""Canal Email (simulado)."""
from trotamundos.notificaciones.canales.base import CanalSimulado, canal


@canal("email")
class CanalEmail(CanalSimulado):
    pass
