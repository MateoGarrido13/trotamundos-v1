# SPEC: SPEC-COMP-08
# ELEMENTO PASO 5: Orquestador de viajes, publicación en la cola de notificaciones (ITERACION_3)
# ADRs: ADR-IT3-002, ADR-IT3-003
# DRIVERS: QA-INT-02
"""Publicador de pedidos de envío. No conoce a los canales: deja `{id, canal, destinatario, propuesta}`
en la cola de notificaciones. Con la cola llena reintenta 1 s, 2 s y 4 s (el Broker avisa a operaciones
en cada intento fallido); el pedido que agota sus reintentos va a mensajes muertos con aviso."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from trotamundos.broker import Broker, ColaLlena, Mensaje, NombreCola
from trotamundos.config import ConfiguracionNotificaciones

log = logging.getLogger(__name__)


def validar_pedido(pedido: Any) -> Mensaje:
    """El `Mensaje` de un pedido bien formado; `ValueError` si le falta algo (PLAN-COMP-08, D8)."""
    if not isinstance(pedido, dict):
        raise ValueError("el pedido de envío debe ser un diccionario")
    propuesta = pedido.get("propuesta")
    for campo in ("id", "canal", "destinatario"):
        if not isinstance(pedido.get(campo), str) or not pedido[campo]:
            raise ValueError(f"el pedido de envío no trae `{campo}`")
    if not (isinstance(propuesta, dict) and isinstance(propuesta.get("asunto"), str)
            and isinstance(propuesta.get("cuerpo"), str)):
        raise ValueError("el pedido de envío no trae `propuesta` con `asunto` y `cuerpo`")
    return Mensaje(pedido["id"], pedido)


class PublicadorNotificaciones:
    def __init__(
        self,
        broker: Broker,
        configuracion: ConfiguracionNotificaciones | None = None,
        *,
        dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._broker = broker
        self._cfg = configuracion or ConfiguracionNotificaciones()
        self._dormir = dormir
        self._bucle: asyncio.AbstractEventLoop | None = None

    def enlazar_bucle(self, bucle: asyncio.AbstractEventLoop) -> None:
        """El bucle donde corren los reintentos de lo publicado desde un hilo (se enlaza al arrancar)."""
        self._bucle = bucle

    async def publicar(self, pedido: dict) -> bool:
        """Publica y, con la cola llena, reintenta. `True` si quedó en la cola; `False` si fue a muertos."""
        mensaje = validar_pedido(pedido)
        for intento in range(self._cfg.reintentos_publicacion + 1):
            try:
                self._broker.publicar(NombreCola.NOTIFICACIONES, mensaje)
                return True
            except ColaLlena:
                if intento < self._cfg.reintentos_publicacion:
                    await self._dormir(self._cfg.backoff_publicacion_segundos * (2**intento))
        self._broker.enviar_a_muertos(NombreCola.NOTIFICACIONES, mensaje)
        return False

    def publicar_desde_hilo(self, pedido: dict) -> None:
        """Para los servicios que corren en hilos (SPEC-COMP-05). Intenta publicar al instante; si la cola
        está llena, programa los reintentos en el bucle de eventos. Sin bucle enlazado el pedido va a
        muertos con aviso en lugar de perderse. Un pedido mal formado lanza `ValueError`."""
        mensaje = validar_pedido(pedido)
        try:
            self._broker.publicar(NombreCola.NOTIFICACIONES, mensaje)
            return
        except ColaLlena:
            pass
        if self._bucle is None or self._bucle.is_closed():
            self._broker.enviar_a_muertos(NombreCola.NOTIFICACIONES, mensaje)
            return
        asyncio.run_coroutine_threadsafe(self._reintentar(mensaje), self._bucle)

    async def _reintentar(self, mensaje: Mensaje) -> None:
        for intento in range(self._cfg.reintentos_publicacion):
            await self._dormir(self._cfg.backoff_publicacion_segundos * (2**intento))
            try:
                self._broker.publicar(NombreCola.NOTIFICACIONES, mensaje)
                return
            except ColaLlena:
                continue
        self._broker.enviar_a_muertos(NombreCola.NOTIFICACIONES, mensaje)
