# SPEC: SPEC-COMP-01
# ELEMENTO PASO 5: Consumidores del Broker (ITERACION_3)
# ADRs: ADR-IT3-001, ADR-IT3-002
# DRIVERS: REF-05, REF-06
"""Supervisor de consumidores: una tarea por cola, que sondea y entrega.

El Broker ya reintenta un handler que falla y manda el mensaje a muertos (ADR-IT3-002). Este
supervisor cubre lo que queda fuera del handler: si el consumidor mismo lanza una excepción,
se registra, se reinicia con espera creciente y los demás consumidores siguen."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from trotamundos.broker import ResultadoEntrega

log = logging.getLogger(__name__)

ProcesarUno = Callable[[], Awaitable[ResultadoEntrega]]


@dataclass(frozen=True)
class ConfiguracionConsumidores:
    intervalo_sondeo_cola: float = 0.2  # espera ante una cola vacía
    espera_reinicio: tuple[float, ...] = (1.0, 2.0, 4.0)  # luego se queda en el tope
    tope_reinicio: float = 30.0


class Supervisor:
    def __init__(self, configuracion: ConfiguracionConsumidores | None = None) -> None:
        self._cfg = configuracion or ConfiguracionConsumidores()
        self._consumidores: dict[str, ProcesarUno] = {}
        self._tareas: dict[str, asyncio.Task] = {}
        self.reinicios: dict[str, int] = {}

    def registrar(self, nombre: str, procesar_uno: ProcesarUno) -> None:
        self._consumidores[nombre] = procesar_uno
        self.reinicios[nombre] = 0

    @property
    def vivos(self) -> list[str]:
        return [n for n, t in self._tareas.items() if not t.done()]

    def iniciar(self) -> None:
        for nombre, procesar in self._consumidores.items():
            if nombre not in self._tareas or self._tareas[nombre].done():
                self._tareas[nombre] = asyncio.create_task(self._bucle(nombre, procesar), name=f"consumidor-{nombre}")

    async def detener(self) -> None:
        tareas = list(self._tareas.values())
        for t in tareas:
            t.cancel()
        await asyncio.gather(*tareas, return_exceptions=True)
        self._tareas.clear()

    async def _bucle(self, nombre: str, procesar: ProcesarUno) -> None:
        fallos = 0
        while True:
            try:
                resultado = await procesar()
                fallos = 0
                if resultado is ResultadoEntrega.VACIA:
                    await asyncio.sleep(self._cfg.intervalo_sondeo_cola)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - un consumidor caído no detiene a los demás
                self.reinicios[nombre] += 1
                espera = (self._cfg.espera_reinicio[fallos] if fallos < len(self._cfg.espera_reinicio)
                          else self._cfg.tope_reinicio)
                fallos += 1
                log.exception("el consumidor %s falló; se reinicia en %.1f s", nombre, espera)
                await asyncio.sleep(min(espera, self._cfg.tope_reinicio))
