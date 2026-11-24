# SPEC: SPEC-COMP-05
# ELEMENTO PASO 5: API Gateway, limitación de tasa (ITERACION_4)
# ADRs: ADR-IT4-005
# DRIVERS: QA-SEG-01
"""Cuenta pedidos por endpoint y por origen en una ventana deslizante."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable


class LimitadorTasa:
    def __init__(self, cupos: dict[str, int], ventana_segundos: float = 60.0,
                 reloj: Callable[[], float] = time.monotonic) -> None:
        self._cupos = cupos
        self._ventana = ventana_segundos
        self._reloj = reloj
        self._pedidos: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self.rechazos: list[tuple[str, str]] = []  # evento registrado: (endpoint, origen)

    def limita(self, endpoint: str) -> bool:
        return endpoint in self._cupos

    def permitir(self, endpoint: str, origen: str) -> bool:
        cupo = self._cupos.get(endpoint)
        if cupo is None:
            return True
        ahora = self._reloj()
        with self._lock:
            cola = self._pedidos[(endpoint, origen)]
            while cola and cola[0] <= ahora - self._ventana:
                cola.popleft()
            if len(cola) >= cupo:
                self.rechazos.append((endpoint, origen))
                return False
            cola.append(ahora)
            return True
