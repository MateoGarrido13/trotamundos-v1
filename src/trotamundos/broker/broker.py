from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from trotamundos.config import ConfiguracionBroker

log = logging.getLogger(__name__)


class NombreCola(StrEnum):
    """Las cinco colas del Broker (Plan Maestro, sección 2)."""

    NOVEDADES = "novedades"
    CORREO = "correo"
    NOTIFICACIONES = "notificaciones"
    CASOS_AYUDA = "casos_ayuda"
    EVENTOS_ANALITICOS = "eventos_analiticos"


@dataclass(frozen=True)
class Mensaje:
    """`id` lo asigna quien publica, no el broker (ADR-IT3-003)."""

    id: str
    cuerpo: Any


@dataclass(frozen=True)
class Aviso:
    """Aviso a operaciones (ADR-IT3-002)."""

    tipo: str  # "cola_llena" | "mensaje_muerto"
    cola: NombreCola
    id_mensaje: str


class ColaLlena(Exception):
    """La cola alcanzó su tamaño máximo. El broker no descarta por su cuenta (ADR-IT3-002):
    cada productor decide qué hace (contrapresión, rechazo explícito o reintento)."""

    def __init__(self, cola: NombreCola) -> None:
        super().__init__(f"La cola {cola.value!r} está llena")
        self.cola = cola


class ResultadoEntrega(StrEnum):
    VACIA = "vacia"
    ENTREGADO = "entregado"
    MUERTO = "muerto"


Handler = Callable[[Mensaje], Awaitable[None]]


class Broker:
    def __init__(
        self,
        configuracion: ConfiguracionBroker | None = None,
        *,
        tamanos: dict[NombreCola, int] | None = None,
        avisar: Callable[[Aviso], None] | None = None,
        dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._cfg = configuracion or ConfiguracionBroker()
        tamanos = tamanos or {}
        self._tamano = {c: tamanos.get(c, self._cfg.tamano_maximo_cola) for c in NombreCola}
        self._colas: dict[NombreCola, deque[Mensaje]] = {c: deque() for c in NombreCola}
        self._muertos: dict[NombreCola, list[Mensaje]] = {c: [] for c in NombreCola}
        self._avisar = avisar or (lambda a: log.warning("aviso a operaciones: %s", a))
        self._dormir = dormir

    # --- productores -----------------------------------------------------------
    def publicar(self, cola: NombreCola, mensaje: Mensaje) -> None:
        """Encola el mensaje o lanza `ColaLlena` (y avisa a operaciones)."""
        if len(self._colas[cola]) >= self._tamano[cola]:
            self._avisar(Aviso("cola_llena", cola, mensaje.id))
            raise ColaLlena(cola)
        self._colas[cola].append(mensaje)

    def enviar_a_muertos(self, cola: NombreCola, mensaje: Mensaje) -> None:
        """Manda a la cola de mensajes muertos un mensaje que su **publicador** no pudo encolar
        tras agotar sus reintentos (SPEC-REF-06), con aviso a operaciones. Es el mismo destino
        que el de un mensaje que agota los reintentos de un consumidor."""
        self._muertos[cola].append(mensaje)
        self._avisar(Aviso("mensaje_muerto", cola, mensaje.id))

    # --- consumidores ----------------------------------------------------------
    def _tomar(self, cola: NombreCola, donde: Callable[[Mensaje], bool] | None) -> Mensaje | None:
        pendientes = self._colas[cola]
        if donde is None:
            return pendientes.popleft() if pendientes else None
        for posicion, mensaje in enumerate(pendientes):
            if donde(mensaje):
                del pendientes[posicion]
                return mensaje
        return None

    async def procesar_uno(self, cola: NombreCola, handler: Handler, *,
                           donde: Callable[[Mensaje], bool] | None = None) -> ResultadoEntrega:
        """Toma el siguiente mensaje y se lo entrega al handler.

        Si el handler falla, reintenta con espera exponencial (base, 2*base, 4*base...).
        Agotados los reintentos, el mensaje va a la cola de mensajes muertos y se avisa
        a operaciones.

        `donde` (SPEC-COMP-08): si se indica, toma el primer mensaje que lo cumple y deja los
        demás en su lugar. Así cada consumidor atiende lo suyo (un canal por consumidor) con el
        Retry y los mensajes muertos del propio Broker. Sin `donde` el comportamiento no cambia.
        """
        mensaje = self._tomar(cola, donde)
        if mensaje is None:
            return ResultadoEntrega.VACIA
        for intento in range(self._cfg.reintentos + 1):
            try:
                await handler(mensaje)
                return ResultadoEntrega.ENTREGADO
            except Exception:  # noqa: BLE001 - cualquier fallo del consumidor se reintenta
                log.exception("fallo entregando %s de %s (intento %d)", mensaje.id, cola, intento)
                if intento < self._cfg.reintentos:
                    await self._dormir(self._cfg.backoff_base_segundos * (2**intento))
        self._muertos[cola].append(mensaje)
        self._avisar(Aviso("mensaje_muerto", cola, mensaje.id))
        return ResultadoEntrega.MUERTO

    # --- inspección (tests y operación) ----------------------------------------
    def tamano_actual(self, cola: NombreCola) -> int:
        return len(self._colas[cola])

    def mensajes_muertos(self, cola: NombreCola) -> list[Mensaje]:
        return list(self._muertos[cola])
