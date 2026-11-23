# SPEC: SPEC-REF-06
# ELEMENTO PASO 5: Servicio de consultas analíticas (ITERACION_5)
# ADRs: ADR-IT5-001, ADR-IT5-002
# DRIVERS: REF-06, QA-PER-04*, QA-PER-02, QA-DIS-01
"""Servicio de consultas analíticas: el informe del equipo de datos.

Lee **solo** los contadores preagregados de la Base analítica: no toca la Base de viajes ni llama
a un nodo del Orquestador. Tiene una cota de 10 segundos; si vence devuelve un error de tiempo
agotado y ningún informe parcial. La cota es doble: `statement_timeout` cancela de verdad la
consulta en PostgreSQL y `asyncio.wait_for` libera al llamador (el solo `wait_for` no cancelaría
la consulta que sigue corriendo en su hilo)."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date

import psycopg

from trotamundos.analitica.base import conectar
from trotamundos.config import ConfiguracionAnalitica

LIMITE_RANKING = 100  # el ranking de destinos devuelve los 100 primeros


class AccesoDenegado(Exception):
    """La cuenta no es del equipo de datos."""


class ErrorTiempoAgotado(Exception):
    """El informe superó la cota. No hay informe parcial."""


class ServicioConsultas:
    def __init__(self, configuracion: ConfiguracionAnalitica | None = None, *,
                 antes_de_consultar: Callable[[psycopg.Connection], None] | None = None) -> None:
        self._cfg = configuracion or ConfiguracionAnalitica()
        # Solo para pruebas: corre dentro de la transacción, antes de las consultas (p. ej. una demora).
        self._antes = antes_de_consultar

    async def informe(self, cuenta: str, desde: date, hasta: date, destino: str | None = None,
                      tipo_reserva: str | None = None) -> dict:
        """Tendencias (altas por día), destinos (ranking por cantidad de altas) y cancelaciones
        (bajas por día y destino) del rango pedido. Sin datos: secciones vacías, no es un error."""
        if cuenta not in self._cfg.cuentas_datos:  # antes de tocar la base
            raise AccesoDenegado(f"{cuenta} no es del equipo de datos")
        if desde > hasta:
            raise ValueError("`desde` es posterior a `hasta`")
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._consultar, desde, hasta, destino, tipo_reserva),
                timeout=self._cfg.cota_informe_segundos)
        except (TimeoutError, psycopg.errors.QueryCanceled):
            raise ErrorTiempoAgotado(
                f"el informe superó la cota de {self._cfg.cota_informe_segundos} s") from None

    def _consultar(self, desde: date, hasta: date, destino: str | None, tipo_reserva: str | None) -> dict:
        filtros, params = "", [desde, hasta]
        if destino is not None:
            filtros += " AND destino = %s"
            params.append(destino)
        if tipo_reserva is not None:
            filtros += " AND tipo_reserva = %s"
            params.append(tipo_reserva)
        ms = max(1, int(self._cfg.cota_informe_segundos * 1000))
        with conectar(self._cfg.dsn) as conn, conn.transaction():
            conn.execute(f"SET LOCAL statement_timeout = {ms}")
            if self._antes:
                self._antes(conn)
            base = f"FROM contador WHERE dia BETWEEN %s AND %s{filtros}"
            tendencias = conn.execute(
                f"SELECT dia, sum(cantidad) {base} AND tipo_evento = 'alta' GROUP BY dia ORDER BY dia",
                params).fetchall()
            destinos = conn.execute(
                f"SELECT destino, sum(cantidad) AS n {base} AND tipo_evento = 'alta'"
                f" GROUP BY destino ORDER BY n DESC, destino LIMIT {LIMITE_RANKING}", params).fetchall()
            cancelaciones = conn.execute(
                f"SELECT dia, destino, sum(cantidad) {base} AND tipo_evento = 'baja'"
                f" GROUP BY dia, destino ORDER BY dia, destino", params).fetchall()
        return {
            "desde": desde.isoformat(), "hasta": hasta.isoformat(),
            "destino": destino, "tipo_reserva": tipo_reserva,
            "tendencias": [{"dia": d.isoformat(), "altas": int(n)} for d, n in tendencias],
            "destinos": [{"destino": d or None, "reservas": int(n)} for d, n in destinos],
            "cancelaciones": [{"dia": d.isoformat(), "destino": dest or None, "bajas": int(n)}
                              for d, dest, n in cancelaciones],
        }
