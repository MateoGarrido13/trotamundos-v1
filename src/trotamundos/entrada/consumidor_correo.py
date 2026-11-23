# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Cola de correo del Broker / Parseo aislado hacia el Filtro de remitentes (ITERACION_3)
# ADRs: ADR-IT3-002, ADR-IT3-003, ADR-IT3-007
# DRIVERS: REF-02
"""Consumidor de la cola de correo: parsea y entrega al Filtro de remitentes.

Cualquier fallo (parseo o filtro) se propaga: el Broker reintenta (1 s, 2 s, 4 s) y luego el
mensaje va a mensajes muertos con aviso a operaciones. Un mensaje que el parseo descarta no
es un fallo: se descarta sin entregar."""
from __future__ import annotations

from trotamundos.broker import Broker, Mensaje, NombreCola, ResultadoEntrega
from trotamundos.entrada.filtro_remitentes import FiltroRemitentes
from trotamundos.entrada.parseo_aislado.cliente import ClienteParseo


class ConsumidorCorreo:
    def __init__(self, broker: Broker, parseo: ClienteParseo, filtro: FiltroRemitentes) -> None:
        self._broker = broker
        self._parseo = parseo
        self._filtro = filtro

    async def _manejar(self, mensaje: Mensaje) -> None:
        datos = mensaje.cuerpo
        reserva = await self._parseo.parsear(
            mensaje.id, datos["titular_id"], datos["remitente"], datos["cuerpo"]
        )
        if reserva is None:
            return  # inválido o malicioso: descartado
        await self._filtro.recibir(reserva)

    async def procesar_uno(self) -> ResultadoEntrega:
        return await self._broker.procesar_uno(NombreCola.CORREO, self._manejar)
