# SPEC: SPEC-REF-05
# ELEMENTO PASO 5: Servicio de ingesta y Orquestador de viajes (ITERACION_4)
# ADRs: ADR-IT4-010, ADR-IT3-003
# DRIVERS: REF-05
"""Frontera de la ingesta hacia el Orquestador para los cambios de estado de un caso. El
Orquestador la implementa; la ingesta no lo importa ni escribe la base."""
from __future__ import annotations

from typing import Protocol

from trotamundos.dominio.agencias import EstadoCaso


class EntregaNovedadCaso(Protocol):
    async def aplicar_estado_caso(self, id_caso: str, estado: EstadoCaso) -> None: ...
