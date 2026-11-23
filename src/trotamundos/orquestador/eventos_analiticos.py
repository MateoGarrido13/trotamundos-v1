# SPEC: SPEC-REF-06
# ELEMENTO PASO 5: Orquestador de viajes, publicación en la cola de eventos analíticos (ITERACION_5)
# ADRs: ADR-IT5-001, ADR-IT3-002, ADR-IT3-003
# DRIVERS: REF-06, QA-PER-02, QA-DIS-01
"""Publica un evento anonimizado en la quinta cola después de confirmar una escritura.

La publicación **no demora la respuesta al viajero**: corre en una tarea en segundo plano, con
reintentos de 1 s, 2 s y 4 s si la cola está llena. El evento que agota sus reintentos va a la
cola de mensajes muertos con aviso a operaciones. Un fallo de este camino nunca afecta a la
operación del viajero, y el Orquestador solo habla con el Broker: no escribe la Base analítica.

Un corte entre la escritura y la publicación puede perder el evento: la spec lo acepta (el informe
es eventual y no exige entrega garantizada)."""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from trotamundos.broker import Broker, ColaLlena, Mensaje, NombreCola
from trotamundos.config import ConfiguracionAnalitica
from trotamundos.dominio.eventos import EventoAnalitico

log = logging.getLogger(__name__)


class EmisorEventos:
    def __init__(
        self,
        broker: Broker,
        configuracion: ConfiguracionAnalitica | None = None,
        *,
        dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._broker = broker
        self._cfg = configuracion or ConfiguracionAnalitica()
        self._dormir = dormir
        self._tareas: set[asyncio.Task] = set()

    def emitir(self, datos: dict[str, Any], ahora: datetime) -> None:
        """Publica un evento en segundo plano y vuelve enseguida. `datos` lleva el `tipo` y los
        campos opcionales del evento. Nunca lanza: si algo falla, la operación ya confirmada
        no se entera."""
        try:
            evento = EventoAnalitico(id=f"evt-{uuid.uuid4().hex}", ocurrido_en=ahora, **datos)
            tarea = asyncio.get_running_loop().create_task(self._publicar(evento))
        except Exception:  # noqa: BLE001 - el camino analítico no puede romper la escritura
            log.exception("no se pudo emitir el evento analítico")
            return
        self._tareas.add(tarea)
        tarea.add_done_callback(self._tareas.discard)

    async def esperar(self) -> None:
        """Espera las publicaciones en curso (para las pruebas y para un cierre ordenado)."""
        while self._tareas:
            await asyncio.gather(*list(self._tareas))

    async def _publicar(self, evento: EventoAnalitico) -> None:
        mensaje = Mensaje(evento.id, evento.model_dump(mode="json"))
        for intento in range(self._cfg.reintentos_publicacion + 1):
            try:
                self._broker.publicar(NombreCola.EVENTOS_ANALITICOS, mensaje)
                return
            except ColaLlena:
                if intento < self._cfg.reintentos_publicacion:
                    await self._dormir(self._cfg.backoff_publicacion_segundos * (2**intento))
        self._broker.enviar_a_muertos(NombreCola.EVENTOS_ANALITICOS, mensaje)
