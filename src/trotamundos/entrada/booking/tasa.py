# SPEC: SPEC-COMP-07
# ELEMENTO PASO 5: Adaptador de anuncios (Booking), listener (ITERACION_3)
# ADRs: ADR-IT3-009
# DRIVERS: QA-PER-01
"""Límite de tasa del listener: ventana deslizante de un segundo por origen. No depende de nadie."""
from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable


class LimitadorVentana:
    def __init__(self, por_segundo: int, reloj: Callable[[], float] = time.monotonic) -> None:
        self._por_segundo = por_segundo
        self._reloj = reloj
        self._marcas: dict[str, deque[float]] = {}

    def permitir(self, origen: str) -> bool:
        ahora = self._reloj()
        marcas = self._marcas.setdefault(origen, deque())
        while marcas and marcas[0] <= ahora - 1.0:
            marcas.popleft()
        if len(marcas) >= self._por_segundo:
            return False
        marcas.append(ahora)
        return True
