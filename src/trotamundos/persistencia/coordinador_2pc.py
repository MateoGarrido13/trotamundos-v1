# SPEC: SPEC-REF-01
# ELEMENTO PASO 5: Commit en dos fases del Orquestador (ITERACION_2)
# ADRs: ADR-IT2-004
# DRIVERS: QA-DIS-01
"""Commit en dos fases sobre las dos bases con PREPARE TRANSACTION / COMMIT PREPARED.

Las conexiones deben estar en autocommit: el coordinador abre y cierra las transacciones
con BEGIN explícito. Orden: ejecutar en ambas, preparar la pasiva (su acuerdo), preparar la
primaria y recién entonces confirmar. Ante cualquier fallo se revierte en ambas.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import psycopg

Operacion = Callable[[psycopg.Connection], Any]


class ErrorDeConexion(Exception):
    """Error de conexión en una de las dos bases; `lado` es 'primaria' o 'pasiva'."""

    def __init__(self, lado: str, causa: Exception) -> None:
        super().__init__(f"error de conexión en la base {lado}: {causa}")
        self.lado = lado
        self.causa = causa


def _en(lado: str, fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except psycopg.OperationalError as e:
        raise ErrorDeConexion(lado, e) from e


class CoordinadorDosFases:
    def ejecutar(self, operacion: Operacion, primaria: psycopg.Connection,
                 pasiva: psycopg.Connection) -> Any:
        gid = f"trota_{uuid.uuid4().hex}"
        conexiones = {"primaria": primaria, "pasiva": pasiva}
        abiertas: set[str] = set()
        preparadas: set[str] = set()
        confirmada: set[str] = set()
        try:
            resultado = None
            for lado, conn in conexiones.items():
                _en(lado, lambda c=conn: c.execute("BEGIN"))
                abiertas.add(lado)
                r = _en(lado, lambda c=conn: operacion(c))
                if lado == "primaria":
                    resultado = r
            for lado in ("pasiva", "primaria"):  # el acuerdo de la pasiva va primero
                _en(lado, lambda c=conexiones[lado]: c.execute(f"PREPARE TRANSACTION '{gid}'"))
                preparadas.add(lado)
                abiertas.discard(lado)
            for lado in ("primaria", "pasiva"):
                _en(lado, lambda c=conexiones[lado]: c.execute(f"COMMIT PREPARED '{gid}'"))
                confirmada.add(lado)
                preparadas.discard(lado)
            return resultado
        except BaseException:
            for lado in preparadas:
                self._silencio(conexiones[lado], f"ROLLBACK PREPARED '{gid}'")
            for lado in abiertas:
                self._silencio(conexiones[lado], "ROLLBACK")
            raise

    def ejecutar_en_una(self, operacion: Operacion, conn: psycopg.Connection) -> Any:
        """Escritura sin segunda copia (tras la conmutación). Usa el lado 'pasiva'."""
        _en("pasiva", lambda: conn.execute("BEGIN"))
        try:
            r = _en("pasiva", lambda: operacion(conn))
            _en("pasiva", lambda: conn.execute("COMMIT"))
            return r
        except BaseException:
            self._silencio(conn, "ROLLBACK")
            raise

    @staticmethod
    def _silencio(conn: psycopg.Connection, sql: str) -> None:
        try:
            conn.execute(sql)
        except Exception:
            pass
