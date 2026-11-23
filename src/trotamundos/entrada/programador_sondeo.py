# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Adaptador de correo (sondeo periódico) (ITERACION_3)
# ADRs: ADR-IT3-003, ADR-IT3-006
# DRIVERS: REF-02
"""Programador de sondeo: recorre los titulares autorizados cada N minutos (15 por defecto).
`tick(ahora)` se invoca a demanda en los tests; `ejecutar` es el bucle real."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from trotamundos.config import ConfiguracionCorreo
from trotamundos.entrada.adaptador_correo import AdaptadorCorreo, ResultadoSondeo
from trotamundos.entrada.api_correo import ErrorApiCorreo
from trotamundos.entrada.gestor_autorizacion import GestorAutorizacion

log = logging.getLogger(__name__)


class ProgramadorSondeo:
    def __init__(
        self,
        adaptador: AdaptadorCorreo,
        gestor: GestorAutorizacion,
        configuracion: ConfiguracionCorreo | None = None,
        *,
        dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._adaptador = adaptador
        self._gestor = gestor
        self._cfg = configuracion or ConfiguracionCorreo()
        self._dormir = dormir

    async def tick(self, ahora: datetime | None = None) -> dict[str, ResultadoSondeo | ErrorApiCorreo]:
        """Un sondeo por titular autorizado. Si la API falla, falla solo ese sondeo."""
        ahora = ahora or datetime.now(UTC)
        resultados: dict[str, ResultadoSondeo | ErrorApiCorreo] = {}
        for titular in self._gestor.titulares_autorizados():
            try:
                resultados[titular] = await self._adaptador.sondear(titular, ahora)
            except ErrorApiCorreo as e:
                log.warning("sondeo fallido para %s: %s", titular, e)
                resultados[titular] = e
        return resultados

    async def ejecutar(self) -> None:
        while True:
            await self.tick()
            await self._dormir(self._cfg.frecuencia_sondeo_minutos * 60)
