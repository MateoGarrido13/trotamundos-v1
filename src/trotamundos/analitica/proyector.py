# SPEC: SPEC-REF-06
# ELEMENTO PASO 5: Proyector analítico (ITERACION_5)
# ADRs: ADR-IT5-001, ADR-IT5-002, ADR-IT3-003
# DRIVERS: REF-06, QA-DIS-01
"""Proyector analítico: consume la quinta cola y mantiene la Base analítica.

Guarda cada evento y suma a un contador según su **tipo de evento**, por destino, día y tipo de
reserva (preagregación incremental). No recalcula el estado de ninguna reserva y no necesita saber
a qué reserva pertenece el evento. Es idempotente: un identificador ya guardado no vuelve a sumar,
así un reintento tras una falla de escritura no cuenta dos veces.

Corre en nodos propios y **no lee la Base de viajes**. El Retry y la cola de mensajes muertos (con
aviso a operaciones) son los del Broker; una Base analítica caída no afecta al Orquestador, que
solo publica en la cola."""
from __future__ import annotations

import asyncio
import threading
from datetime import UTC

import psycopg

from trotamundos.analitica.base import conectar
from trotamundos.broker import Broker, Mensaje, NombreCola, ResultadoEntrega
from trotamundos.dominio.eventos import EventoAnalitico


class Proyector:
    def __init__(self, broker: Broker, dsn: str) -> None:
        self._broker = broker
        self._dsn = dsn
        self._conn: psycopg.Connection | None = None
        self._lock = threading.Lock()

    async def procesar_uno(self) -> ResultadoEntrega:
        return await self._broker.procesar_uno(NombreCola.EVENTOS_ANALITICOS, self._manejar)

    async def _manejar(self, mensaje: Mensaje) -> None:
        evento = EventoAnalitico.model_validate(mensaje.cuerpo)
        await asyncio.to_thread(self.proyectar, evento)

    def proyectar(self, e: EventoAnalitico) -> bool:
        """Guarda el evento y suma a su contador. Devuelve `False` si ya estaba (se descarta)."""
        dia = e.ocurrido_en.astimezone(UTC).date()  # el día en que ocurrió el evento
        destino, tipo_reserva = e.destino or "", e.tipo_reserva or ""
        with self._lock:
            try:
                conn = self._conexion()
                with conn.transaction():
                    nuevo = conn.execute(
                        "INSERT INTO evento (id, tipo, tipo_reserva, destino, inicio, fin, origen, estado,"
                        " ocurrido_en, dia) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                        " ON CONFLICT (id) DO NOTHING",
                        (e.id, e.tipo, tipo_reserva, destino, e.inicio, e.fin, e.origen or "",
                         e.estado or "", e.ocurrido_en, dia)).rowcount > 0
                    if nuevo:  # un identificador repetido no vuelve a sumar
                        conn.execute(
                            "INSERT INTO contador (dia, destino, tipo_reserva, tipo_evento, cantidad)"
                            " VALUES (%s, %s, %s, %s, 1) ON CONFLICT (dia, destino, tipo_reserva, tipo_evento)"
                            " DO UPDATE SET cantidad = contador.cantidad + 1",
                            (dia, destino, tipo_reserva, e.tipo))
                return nuevo
            except psycopg.OperationalError:
                self._cerrar()  # la próxima vez se reconecta
                raise

    def cerrar(self) -> None:
        with self._lock:
            self._cerrar()

    def _conexion(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            self._conn = conectar(self._dsn, autocommit=True)
        return self._conn

    def _cerrar(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None
