# SPEC: SPEC-REF-01
# ELEMENTO PASO 5: Base primaria + Base pasiva y Reconfiguration (ITERACION_2)
# ADRs: ADR-IT2-004, ADR-IT2-005
# DRIVERS: QA-DIS-01, REF-01
"""Acceso del Orquestador a la Base de viajes: escritura con commit en dos fases y
conmutación a la pasiva tras N errores de conexión consecutivos de la primaria."""
from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import psycopg

from trotamundos.config import ConfiguracionBases
from trotamundos.persistencia.conexion import conectar
from trotamundos.persistencia.coordinador_2pc import (
    CoordinadorDosFases,
    ErrorDeConexion,
    Operacion,
)

FabricaConexion = Callable[[], psycopg.Connection]


class ErrorBaseNoDisponible(Exception):
    """Ninguna base puede atender (error de servicio no disponible)."""


class BaseViajes:
    def __init__(self, fabrica_primaria: FabricaConexion, fabrica_pasiva: FabricaConexion,
                 umbral: int = 3, coordinador: CoordinadorDosFases | None = None) -> None:
        self._fabricas = {"primaria": fabrica_primaria, "pasiva": fabrica_pasiva}
        self.umbral = umbral
        self._coordinador = coordinador or CoordinadorDosFases()
        self._lock = threading.RLock()
        self.fallos_consecutivos = 0
        self.conmutada = False
        # Tras conmutar, la primaria vieja queda bloqueada hasta resincronizarla a mano.
        self.primaria_no_escribible = False

    @classmethod
    def desde_config(cls, cfg: ConfiguracionBases) -> BaseViajes:
        return cls(lambda: conectar(cfg.viajes_primaria, autocommit=True),
                   lambda: conectar(cfg.viajes_pasiva, autocommit=True),
                   umbral=cfg.umbral_conmutacion)

    @property
    def atiende(self) -> str:
        return "pasiva" if self.conmutada else "primaria"

    # --- API ----------------------------------------------------------------
    def escribir(self, operacion: Operacion) -> Any:
        with self._lock:
            if not self.conmutada:
                try:
                    return self._escribir_2pc(operacion)
                except ErrorDeConexion as e:
                    if e.lado == "pasiva":
                        raise ErrorBaseNoDisponible(
                            "la base pasiva no acordó la escritura; no se confirma") from e
                    self._fallo_primaria(e)
            return self._escribir_solo_pasiva(operacion)

    def leer(self, consulta: Operacion) -> Any:
        with self._lock:
            if not self.conmutada:
                try:
                    r = self._leer_de("primaria", consulta)
                    self.fallos_consecutivos = 0
                    return r
                except ErrorDeConexion as e:
                    self._fallo_primaria(e)
            try:
                return self._leer_de("pasiva", consulta)
            except ErrorDeConexion as e:
                raise ErrorBaseNoDisponible("ninguna base de viajes disponible") from e

    # --- internos -----------------------------------------------------------
    def _fallo_primaria(self, causa: ErrorDeConexion) -> None:
        """Cuenta el fallo; si alcanza el umbral conmuta, si no avisa que no hay servicio."""
        self.fallos_consecutivos += 1
        if self.fallos_consecutivos >= self.umbral:
            self.conmutada = True
            self.primaria_no_escribible = True
        else:
            raise ErrorBaseNoDisponible(
                f"la primaria falló ({self.fallos_consecutivos}/{self.umbral}); "
                "todavía no se conmuta") from causa

    def _abrir(self, lado: str) -> psycopg.Connection:
        try:
            return self._fabricas[lado]()
        except psycopg.OperationalError as e:
            raise ErrorDeConexion(lado, e) from e

    def _escribir_2pc(self, operacion: Operacion) -> Any:
        primaria = self._abrir("primaria")
        try:
            pasiva = self._abrir("pasiva")
            try:
                r = self._coordinador.ejecutar(operacion, primaria, pasiva)
            finally:
                pasiva.close()
        finally:
            primaria.close()
        self.fallos_consecutivos = 0
        return r

    def _escribir_solo_pasiva(self, operacion: Operacion) -> Any:
        try:
            conn = self._abrir("pasiva")
            try:
                return self._coordinador.ejecutar_en_una(operacion, conn)
            finally:
                conn.close()
        except ErrorDeConexion as e:
            raise ErrorBaseNoDisponible("ninguna base de viajes disponible") from e

    def _leer_de(self, lado: str, consulta: Operacion) -> Any:
        conn = self._abrir(lado)
        try:
            try:
                return consulta(conn)
            except psycopg.OperationalError as e:
                raise ErrorDeConexion(lado, e) from e
        finally:
            conn.close()
