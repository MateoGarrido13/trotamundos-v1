# SPEC: SPEC-COMP-06
# ELEMENTO PASO 5: Balanceador de Carga (ITERACION_2)
# ADRs: ADR-004, ADR-IT2-005
# DRIVERS: QA-DIS-01
"""Balanceador de Carga: Ping/Echo periódico a cada nodo (health check). Un nodo sin eco sale de
rotación (Reconfiguration) y vuelve cuando da eco. El pedido en vuelo hacia un nodo que cae se
reenvía a otro sano: la cotización es de solo lectura, repetirla no duplica nada. Cada baja se avisa
a operaciones. Sin Heartbeat ni Retry hacia el nodo: el Balanceador es nuestro y consulta él mismo."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

from trotamundos.dominio.cotizacion import Criterios, Grilla, ProgresoGrilla
from trotamundos.dominio.puertos_cotizacion import INodo, NodoCaido, SinNodosDisponibles

log = logging.getLogger(__name__)
operaciones = logging.getLogger("trotamundos.operaciones")


class Balanceador:
    def __init__(self, nodos: Sequence[INodo], intervalo_eco_segundos: float = 1.0) -> None:
        self._nodos = tuple(nodos)
        self._intervalo = intervalo_eco_segundos
        self._caidos: set[str] = set()
        self._turno = 0
        self.avisos: list[str] = []

    @property
    def nodos_sanos(self) -> list[str]:
        return [n.nombre for n in self._nodos if n.nombre not in self._caidos]

    def _avisar(self, texto: str) -> None:
        self.avisos.append(texto)
        operaciones.error(texto)

    def _marcar_caido(self, nodo: INodo, motivo: str) -> None:
        if nodo.nombre not in self._caidos:
            self._caidos.add(nodo.nombre)
            self._avisar(f"nodo de cotización {nodo.nombre} fuera de rotación: {motivo}")

    async def verificar_nodos(self) -> None:
        """Un ciclo de health check. Un eco que no llega en el intervalo cuenta como sin eco."""
        for nodo in self._nodos:
            try:
                eco = await asyncio.wait_for(nodo.eco(), self._intervalo)
            except Exception:  # noqa: BLE001 - cualquier falla del nodo es «sin eco»
                eco = False
            if eco and nodo.nombre in self._caidos:
                self._caidos.discard(nodo.nombre)
                log.info("el nodo de cotización %s volvió a rotación", nodo.nombre)
            elif not eco:
                self._marcar_caido(nodo, "sin eco")

    async def ejecutar(self) -> None:
        """Tarea periódica del health check; se cancela al cerrar la app."""
        while True:
            await self.verificar_nodos()
            await asyncio.sleep(self._intervalo)

    def _elegir(self, ya_probados: set[str]) -> INodo | None:
        candidatos = [n for n in self._nodos if n.nombre not in self._caidos and n.nombre not in ya_probados]
        if not candidatos:
            return None
        nodo = candidatos[self._turno % len(candidatos)]
        self._turno += 1
        return nodo

    async def despachar(self, criterios: Criterios, progreso: ProgresoGrilla) -> Grilla:
        probados: set[str] = set()
        while True:
            nodo = self._elegir(probados)
            if nodo is None:
                raise SinNodosDisponibles("ningún nodo de cotización sano")
            try:
                return await nodo.atender(criterios, progreso)
            except NodoCaido:
                probados.add(nodo.nombre)
                self._marcar_caido(nodo, "cayó con un pedido en vuelo")
                progreso.reiniciar()  # el reenvío empieza de cero
