# SPEC: SPEC-REF-01
# ELEMENTO PASO 5: Orquestador de viajes, agrupación y vista principal (ITERACION_1)
# ADRs: ADR-001, ADR-IT3-005
# DRIVERS: REF-01, CON-01, QA-EVO-01
"""Agrupación de reservas por viaje. Trabaja contra `Reserva`; no conoce tipos concretos."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from trotamundos.dominio.reserva import Reserva


class FuenteViajes(Protocol):
    def listar_viajes(self, viajero_id: str, estado: str) -> list: ...
    def reservas_de(self, viaje_ids: list[str]) -> list[Reserva]: ...


@dataclass
class ViajeAgrupado:
    id: str
    estado: str
    reservas: list[Reserva] = field(default_factory=list)


class Agrupacion:
    def __init__(self, fuente: FuenteViajes) -> None:
        self._fuente = fuente

    def vista_principal(self, viajero_id: str) -> list[ViajeAgrupado]:
        """Viajes activos del viajero con sus reservas. Sin viajes: lista vacía."""
        return self._agrupar(viajero_id, "activo")

    def archivados(self, viajero_id: str) -> list[ViajeAgrupado]:
        """Viajes archivados del viajero con sus reservas. Sin viajes: lista vacía."""
        return self._agrupar(viajero_id, "archivado")

    def _agrupar(self, viajero_id: str, estado: str) -> list[ViajeAgrupado]:
        viajes = self._fuente.listar_viajes(viajero_id, estado)
        grupos = {v.id: ViajeAgrupado(id=v.id, estado=v.estado) for v in viajes}
        for reserva in self._fuente.reservas_de(list(grupos)):
            grupos[reserva.viaje_id].reservas.append(reserva)
        return list(grupos.values())
