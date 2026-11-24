# SPEC: SPEC-COMP-06
# ELEMENTO PASO 5: Orquestador de viajes, en su rol de cotización (ITERACION_2)
# ADRs: ADR-006, ADR-IT2-002, ADR-IT2-003, ADR-IT3-004
# DRIVERS: QA-PER-02, QA-INT-01
"""Scatter-Gather: pide el precio a todos los cotizadores a la vez, de modo que las latencias no se
suman, y arma la grilla con los que responden (Graceful degradation). Conoce a los cotizadores solo
por el contrato `ICotizador`: un proveedor nuevo es un adaptador más, sin tocar este módulo."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

from trotamundos.dominio.cotizacion import Criterios, EstadoOrigen, Grilla, ProgresoGrilla, ResultadoOrigen
from trotamundos.dominio.puertos_cotizacion import ICotizador

log = logging.getLogger(__name__)


class ServicioCotizacion:
    def __init__(self, cotizadores: Sequence[ICotizador]) -> None:
        self._cotizadores = tuple(cotizadores)

    async def cotizar(self, criterios: Criterios, progreso: ProgresoGrilla | None = None) -> Grilla:
        progreso = progreso if progreso is not None else ProgresoGrilla()
        progreso.iniciar(tuple(c.nombre for c in self._cotizadores))

        async def uno(cotizador: ICotizador) -> None:
            try:
                resultado = await cotizador.cotizar(criterios)
            except Exception:  # noqa: BLE001 - un proveedor roto solo afecta a su origen
                log.exception("el cotizador %s falló", cotizador.nombre)
                resultado = ResultadoOrigen(cotizador.nombre, EstadoOrigen.NO_RESPONDIO)
            progreso.registrar(resultado)

        await asyncio.gather(*(uno(c) for c in self._cotizadores))
        return progreso.a_grilla()
