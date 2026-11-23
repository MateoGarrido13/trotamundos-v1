# SPEC: SPEC-REF-07
# ELEMENTO PASO 5: Circuit Breaker del proveedor de modelo (RONDA_2/ITERACION_2)
# ADRs: ADR-IT7-004
# DRIVERS: REF-07, QA-DIS-02
"""Circuit Breaker por proveedor de modelo, con tres estados.

Cerrado: las consultas llegan al proveedor; a los 5 fallos consecutivos pasa a abierto, y un turno
exitoso reinicia la cuenta. Abierto: no se llama al proveedor y la respuesta por defecto sale de
inmediato; a los 30 segundos pasa a semi-abierto. Semi-abierto: deja pasar **una sola** llamada de
prueba; si responde, vuelve a cerrado, y si no, a abierto. El reloj es inyectable."""
from __future__ import annotations

import time
from collections.abc import Callable
from enum import StrEnum


class EstadoCircuito(StrEnum):
    CERRADO = "cerrado"
    ABIERTO = "abierto"
    SEMIABIERTO = "semiabierto"


class CircuitBreaker:
    def __init__(self, umbral: int = 5, apertura_segundos: float = 30.0,
                 reloj: Callable[[], float] = time.monotonic) -> None:
        self._umbral = umbral
        self._apertura = apertura_segundos
        self._reloj = reloj
        self._fallos = 0
        self._estado = EstadoCircuito.CERRADO
        self._abierto_en = 0.0
        self._prueba_en_curso = False

    @property
    def estado(self) -> EstadoCircuito:
        self._actualizar()
        return self._estado

    @property
    def fallos_consecutivos(self) -> int:
        return self._fallos

    def permitir(self) -> bool:
        """¿Se puede llamar al proveedor? En semi-abierto deja pasar una sola llamada de prueba."""
        self._actualizar()
        if self._estado is EstadoCircuito.CERRADO:
            return True
        if self._estado is EstadoCircuito.SEMIABIERTO and not self._prueba_en_curso:
            self._prueba_en_curso = True
            return True
        return False

    def exito(self) -> None:
        self._fallos = 0
        self._estado = EstadoCircuito.CERRADO
        self._prueba_en_curso = False

    def fallo(self) -> None:
        self._actualizar()
        if self._estado is EstadoCircuito.SEMIABIERTO:  # la llamada de prueba falló
            self._abrir()
            return
        self._fallos += 1
        if self._fallos >= self._umbral:
            self._abrir()

    def _abrir(self) -> None:
        self._estado = EstadoCircuito.ABIERTO
        self._abierto_en = self._reloj()
        self._prueba_en_curso = False

    def _actualizar(self) -> None:
        if self._estado is EstadoCircuito.ABIERTO and self._reloj() - self._abierto_en >= self._apertura:
            self._estado = EstadoCircuito.SEMIABIERTO
            self._prueba_en_curso = False
