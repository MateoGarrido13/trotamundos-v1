# SPEC: SPEC-COMP-05
# ELEMENTO PASO 5: Base de cuentas de la región (ITERACION_4)
# ADRs: ADR-IT4-001, ADR-IT2-004
# DRIVERS: QA-ESC-01
"""Esquema y acceso a la Base de cuentas de una región: primaria y pasiva con commit en dos fases."""
from __future__ import annotations

import threading
from pathlib import Path

import psycopg
from psycopg.pq import TransactionStatus

from trotamundos.persistencia.base_viajes import BaseViajes
from trotamundos.persistencia.conexion import conectar

TABLAS = ("aviso_recuperacion", "intento_recuperacion", "recuperacion", "token_renovacion", "cuenta")


def aplicar_esquema(conn: psycopg.Connection) -> None:
    conn.execute((Path(__file__).parent / "esquema.sql").read_text())


class _Prestada:
    """La conexión que se le presta a un hilo: `close()` no la cierra, queda para el próximo uso."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def close(self) -> None:
        pass

    def __getattr__(self, nombre: str):
        return getattr(self._conn, nombre)


class ConexionesPorHilo:
    """Una conexión por hilo y por base. Abrir una conexión nueva en cada operación cuesta más que
    la operación (QA-ESC-01: 1.000 altas en menos de 2 s); `BaseViajes` las cierra al terminar, así
    que se las presta con un `close()` que no cierra."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._local = threading.local()
        self._todas: list[psycopg.Connection] = []
        self._lock = threading.Lock()

    def __call__(self) -> _Prestada:
        conn = getattr(self._local, "conn", None)
        if conn is None or conn.closed or conn.broken:
            conn = conectar(self._dsn, autocommit=True)  # si falla, lanza OperationalError como siempre
            self._local.conn = conn
            with self._lock:
                self._todas.append(conn)
        elif conn.info.transaction_status != TransactionStatus.IDLE:
            conn.execute("ROLLBACK")
        return _Prestada(conn)

    def cerrar(self) -> None:
        with self._lock:
            for conn in self._todas:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass
            self._todas.clear()


def base_de_region(dsn_primaria: str, dsn_pasiva: str) -> BaseViajes:
    """Misma mecánica de escritura de las bases de viajes (D8): 2PC entre primaria y pasiva."""
    primaria, pasiva = ConexionesPorHilo(dsn_primaria), ConexionesPorHilo(dsn_pasiva)
    base = BaseViajes(primaria, pasiva)
    base.cerrar_conexiones = lambda: (primaria.cerrar(), pasiva.cerrar())  # type: ignore[attr-defined]
    return base
