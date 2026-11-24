# SPEC: SPEC-COMP-06
# ELEMENTO PASO 5: Caché de borde (CDN) (ITERACION_2)
# ADRs: ADR-005, ADR-IT2-001, ADR-IT2-002
# DRIVERS: QA-PER-02
"""Caché de borde: guarda copias de la grilla de una fecha, un hospedaje y una compañía, y pone la
cota de 800 ms al pedido (Bound execution times).

* Copia vigente: se devuelve sin llamar al Orquestador.
* Sin copia vigente: se pide la grilla fresca. Si llega a tiempo, se entrega y se guarda.
* Si la cota vence (Graceful degradation, dos niveles): se entrega la copia que haya, aunque esté
  vencida; si no hay, la grilla parcial que el Orquestador ya armó; si no hay ningún origen,
  «cotización en curso».
* La consulta fresca **no se cancela** al vencer la cota: cuando llega, actualiza la copia."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from collections.abc import Callable

from trotamundos.config import ConfiguracionCotizacion
from trotamundos.dominio.cotizacion import Criterios, Grilla, ProgresoGrilla
from trotamundos.dominio.puertos_cotizacion import IDespachador

log = logging.getLogger(__name__)


class CacheBorde:
    def __init__(self, despachador: IDespachador, configuracion: ConfiguracionCotizacion | None = None,
                 reloj: Callable[[], float] = time.monotonic) -> None:
        self._despachador = despachador
        self._cfg = configuracion or ConfiguracionCotizacion()
        self._reloj = reloj
        self._copias: OrderedDict[tuple, tuple[float, Grilla]] = OrderedDict()
        self._pendientes: set[asyncio.Task] = set()

    # --- copias -----------------------------------------------------------------------
    def _copia(self, criterios: Criterios) -> tuple[float, Grilla] | None:
        """(edad en segundos, grilla) de la copia guardada, si hay."""
        guardada = self._copias.get(criterios.clave())
        if guardada is None:
            return None
        momento, grilla = guardada
        return self._reloj() - momento, grilla

    def _guardar(self, criterios: Criterios, grilla: Grilla) -> None:
        if not grilla.tiene_precios:  # PLAN-COMP-06, D5 y D7: «en curso» no se guarda
            return
        clave = criterios.clave()
        self._copias[clave] = (self._reloj(), grilla)
        self._copias.move_to_end(clave)
        while len(self._copias) > self._cfg.max_copias:
            self._copias.popitem(last=False)

    # --- consulta fresca ---------------------------------------------------------------
    async def _fresca(self, criterios: Criterios, progreso: ProgresoGrilla) -> Grilla | None:
        try:
            return await self._despachador.despachar(criterios, progreso)
        except Exception:  # noqa: BLE001 - se degrada a la copia o a lo parcial
            log.exception("la cotización fresca falló")
            return None

    def _al_terminar(self, criterios: Criterios, tarea: asyncio.Task) -> None:
        self._pendientes.discard(tarea)
        if tarea.cancelled():
            return
        grilla = tarea.result()  # _fresca no propaga excepciones: la tarea siempre termina bien
        if grilla is not None:
            self._guardar(criterios, grilla)  # también la que llega después de la cota

    # --- pedido ------------------------------------------------------------------------
    async def obtener(self, criterios: Criterios) -> Grilla:
        copia = self._copia(criterios)
        if copia is not None and copia[0] <= self._cfg.vigencia_copia_segundos:
            return copia[1].como_copia()

        progreso = ProgresoGrilla()
        tarea = asyncio.create_task(self._fresca(criterios, progreso))
        self._pendientes.add(tarea)
        tarea.add_done_callback(lambda t: self._al_terminar(criterios, t))
        hechas, _ = await asyncio.wait({tarea}, timeout=self._cfg.cota_cotizacion)

        fresca = tarea.result() if tarea in hechas else None
        if fresca is not None and not (fresca.en_curso and copia is not None):
            return fresca
        if copia is not None:
            return copia[1].como_copia()
        return fresca if fresca is not None else progreso.a_grilla()

    async def cerrar(self) -> None:
        """Cancela y espera las consultas que sigan en curso."""
        for tarea in list(self._pendientes):
            tarea.cancel()
        await asyncio.gather(*self._pendientes, return_exceptions=True)
