# SPEC: SPEC-COMP-08
# ELEMENTO PASO 5: ICanal, adaptador de Whatsapp (ITERACION_3)
# ADRs: ADR-IT3-004
# DRIVERS: QA-INT-02
"""Canal Whatsapp (simulado)."""
from trotamundos.notificaciones.canales.base import CanalSimulado, canal


@canal("whatsapp")
class CanalWhatsapp(CanalSimulado):
    pass
