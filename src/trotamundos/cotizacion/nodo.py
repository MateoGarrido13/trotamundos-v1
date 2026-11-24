# SPEC: SPEC-COMP-06
# ELEMENTO PASO 5: Nodos del Orquestador de viajes (Redundant spare) (ITERACION_2)
# ADRs: ADR-IT2-005
# DRIVERS: QA-DIS-01
"""Un nodo de cotización. Cualquiera atiende cualquier pedido: no guarda estado. Admite inyectar
demora, falta de eco y una caída con el pedido en vuelo, para demostrar la táctica (`QA-DIS-01`)."""
from __future__ import annotations

import asyncio

from trotamundos.cotizacion.servicio import ServicioCotizacion
from trotamundos.dominio.cotizacion import Criterios, Grilla, ProgresoGrilla
from trotamundos.dominio.puertos_cotizacion import NodoCaido


class NodoCotizacion:
    def __init__(self, nombre: str, servicio: ServicioCotizacion) -> None:
        self.nombre = nombre
        self._servicio = servicio
        self.demora_segundos = 0.0
        self.sin_eco = False
        self.caer_en_vuelo = False
        self.atendidos = 0

    async def eco(self) -> bool:
        return not self.sin_eco

    async def atender(self, criterios: Criterios, progreso: ProgresoGrilla) -> Grilla:
        self.atendidos += 1
        if self.demora_segundos:
            await asyncio.sleep(self.demora_segundos)
        if self.caer_en_vuelo:
            self.sin_eco = True
            raise NodoCaido(self.nombre)
        return await self._servicio.cotizar(criterios, progreso)
