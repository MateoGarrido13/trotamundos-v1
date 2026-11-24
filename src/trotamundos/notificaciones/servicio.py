# SPEC: SPEC-COMP-08
# ELEMENTO PASO 5: Servicio de notificaciones (ITERACION_3)
# ADRs: ADR-IT3-001, ADR-IT3-003, ADR-IT3-004
# DRIVERS: QA-INT-02
"""Servicio de notificaciones: consume la cola `notificaciones` y entrega cada pedido por su canal.

Hay **un consumidor por canal**: cada uno toma de la cola solo los pedidos de su canal (`donde` del
Broker) y deja los demás. El Retry, la cola de mensajes muertos y el aviso a operaciones son los del
Broker, y un canal lento o caído solo atrasa a su propio consumidor (`QA-INT-02`). Un pedido de un canal
que no está registrado va directo a mensajes muertos. El servicio entrega el contenido tal como lo recibe.

Recibe los canales por contrato (`ICanal`): no conoce a ninguno en particular."""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from trotamundos.broker import Broker, Mensaje, NombreCola, ResultadoEntrega
from trotamundos.config import ConfiguracionIngesta
from trotamundos.dominio.puertos_notificaciones import ICanal, Propuesta

PREFIJO = "notificaciones:"
SIN_CANAL = PREFIJO + "sin_canal"


def _ahora_utc() -> datetime:
    return datetime.now(UTC)


def canal_de(mensaje: Mensaje) -> str | None:
    cuerpo = mensaje.cuerpo
    canal = cuerpo.get("canal") if isinstance(cuerpo, dict) else None
    return canal if isinstance(canal, str) else None


def _pedido(mensaje: Mensaje) -> tuple[str, Propuesta] | None:
    """(destinatario, propuesta) de un pedido bien formado, o `None`."""
    cuerpo: Any = mensaje.cuerpo
    propuesta = cuerpo.get("propuesta") if isinstance(cuerpo, dict) else None
    destinatario = cuerpo.get("destinatario") if isinstance(cuerpo, dict) else None
    if not (isinstance(destinatario, str) and destinatario and isinstance(propuesta, dict)
            and isinstance(propuesta.get("asunto"), str) and isinstance(propuesta.get("cuerpo"), str)):
        return None
    return destinatario, Propuesta(propuesta["asunto"], propuesta["cuerpo"])


class ServicioNotificaciones:
    def __init__(
        self,
        broker: Broker,
        canales: Mapping[str, ICanal] | Iterable[ICanal],
        configuracion: ConfiguracionIngesta | None = None,
        *,
        reloj: Callable[[], datetime] = _ahora_utc,
    ) -> None:
        self._broker = broker
        self._canales: dict[str, ICanal] = (
            dict(canales) if isinstance(canales, Mapping) else {c.nombre: c for c in canales})
        self._retencion = timedelta(days=(configuracion or ConfiguracionIngesta()).retencion_ids_dias)
        self._reloj = reloj
        self._enviados: dict[str, datetime] = {}

    @property
    def canales(self) -> dict[str, ICanal]:
        return dict(self._canales)

    # --- consumidores ---------------------------------------------------------------------
    def consumidores(self) -> dict[str, Callable[[], object]]:
        """`{nombre: procesar_uno}`: uno por canal registrado y uno para los pedidos sin canal."""
        consumidores: dict[str, Callable[[], object]] = {
            PREFIJO + nombre: (lambda n=nombre: self.procesar_canal(n)) for nombre in self._canales}
        consumidores[SIN_CANAL] = self.procesar_sin_canal
        return consumidores

    async def procesar_canal(self, nombre: str) -> ResultadoEntrega:
        canal = self._canales[nombre]

        async def entregar(mensaje: Mensaje) -> None:
            await self._entregar(canal, mensaje)

        return await self._broker.procesar_uno(
            NombreCola.NOTIFICACIONES, entregar, donde=lambda m: canal_de(m) == nombre)

    async def procesar_sin_canal(self) -> ResultadoEntrega:
        """Los pedidos de un canal que no existe (o sin canal) van a muertos con aviso, sin reintentar."""
        return await self._broker.procesar_uno(
            NombreCola.NOTIFICACIONES, self._a_muertos, donde=lambda m: canal_de(m) not in self._canales)

    # --- internos -------------------------------------------------------------------------
    async def _a_muertos(self, mensaje: Mensaje) -> None:
        self._broker.enviar_a_muertos(NombreCola.NOTIFICACIONES, mensaje)

    async def _entregar(self, canal: ICanal, mensaje: Mensaje) -> None:
        if self._ya_enviado(mensaje.id):
            return  # el Broker entregó dos veces el mismo pedido: no se repite el envío
        pedido = _pedido(mensaje)
        if pedido is None:  # mal formado: reintentarlo no lo arregla
            self._broker.enviar_a_muertos(NombreCola.NOTIFICACIONES, mensaje)
            return
        await canal.enviar(*pedido)
        # Se marca recién después de enviar: si se marcara antes, el reintento tras una falla se descartaría.
        self._enviados[mensaje.id] = self._reloj()

    def _ya_enviado(self, identificador: str) -> bool:
        limite = self._reloj() - self._retencion
        for k in [k for k, t in self._enviados.items() if t < limite]:
            del self._enviados[k]
        return identificador in self._enviados
