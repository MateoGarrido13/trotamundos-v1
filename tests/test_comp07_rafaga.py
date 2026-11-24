# SPEC: SPEC-COMP-07 | PLAN-COMP-07 T-COMP-07-07
# ELEMENTO PASO 5: Servicio de ingesta, límite de tasa de entrega (ITERACION_3)
# ADRs: ADR-IT3-010
# DRIVERS: QA-PER-01
"""La ráfaga de las 8 am: la ingesta no supera su límite de entrega y la cotización no se degrada."""
import asyncio
import time

import pytest

from tests.comp06_util import borde_con, criterios, sistema
from tests.comp07_util import Entorno
from trotamundos.broker import ResultadoEntrega
from trotamundos.config import ConfiguracionIngesta
from trotamundos.entrada.booking.simulado import BookingSimulado
from trotamundos.entrada.ingesta import LimitadorTasa, ServicioIngesta

pytestmark = pytest.mark.carga


class EntregaReservas:
    async def incorporar(self, reserva):
        raise AssertionError("una ráfaga de anuncios no toca reservas")


class AnunciosRegistrados:
    """Registra cuándo (en el reloj de la prueba) le entregan cada anuncio."""

    def __init__(self, reloj):
        self._reloj = reloj
        self.momentos: list[float] = []

    async def guardar_anuncio(self, anuncio):
        self.momentos.append(self._reloj())
        return True


async def test_AC_COMP_07_06_la_rafaga_no_supera_el_limite_de_entrega():
    e = Entorno()
    ahora = [0.0]

    async def dormir(segundos):  # el reloj falso avanza lo que la ingesta pide esperar
        ahora[0] += segundos

    por_segundo = ConfiguracionIngesta().tasa_por_segundo
    entrega = AnunciosRegistrados(lambda: ahora[0])
    ingesta = ServicioIngesta(e.broker, EntregaReservas(), entrega_anuncios=entrega,
                              limitador=LimitadorTasa(por_segundo, reloj=lambda: ahora[0], dormir=dormir))
    resultados = await e.booking.rafaga(e.post, 90, espera=0.3, reintentos=6)  # todos los avisos a la vez
    assert all(r.entregado for r in resultados) and e.en_cola() == 90
    while await ingesta.procesar_uno() is not ResultadoEntrega.VACIA:
        pass
    m = entrega.momentos
    assert len(m) == 90
    huecos = [b - a for a, b in zip(m, m[1:])]
    assert min(huecos) >= 1 / por_segundo - 1e-9  # nunca más rápido que el límite
    assert m[-1] - m[0] >= 89 / por_segundo - 1e-9  # y la ráfaga entera se espació


def _p90(tiempos: list[float]) -> float:
    return sorted(tiempos)[int(len(tiempos) * 0.9) - 1]


async def _cotizaciones(oleadas: int = 10, por_oleada: int = 20, pausa: float = 0.25) -> list[float]:
    sis = sistema()
    for api in sis.apis.values():
        api.demora_segundos = 0.15  # 0,3 s por proveedor
    borde = borde_con(sis)
    tiempos: list[float] = []

    async def una(i: int) -> None:
        inicio = time.perf_counter()
        assert (await borde.obtener(criterios(i))).tiene_precios
        tiempos.append(time.perf_counter() - inicio)

    tareas = []
    for o in range(oleadas):
        tareas += [asyncio.create_task(una(o * por_oleada + i)) for i in range(por_oleada)]
        await asyncio.sleep(pausa)
    await asyncio.gather(*tareas)
    await borde.cerrar()
    return tiempos


@pytest.mark.db
async def test_AC_COMP_07_07_la_cotizacion_no_se_degrada_con_la_rafaga(bases_limpias):
    from trotamundos.config import ConfiguracionBooking
    from trotamundos.orquestador.anuncios import ServicioAnuncios
    from trotamundos.persistencia.base_viajes import BaseViajes

    base = _p90(await _cotizaciones())  # sin ráfaga

    e = Entorno()
    anuncios = ServicioAnuncios(BaseViajes.desde_config(bases_limpias), ConfiguracionBooking(clave_proveedor="x"))
    ingesta = ServicioIngesta(e.broker, EntregaReservas(), entrega_anuncios=anuncios)
    terminada = asyncio.Event()

    async def consumidor():  # el consumidor de la ingesta, con su límite de entrega real (20 por segundo)
        while not terminada.is_set() or e.en_cola():
            if await ingesta.procesar_uno() is ResultadoEntrega.VACIA:
                await asyncio.sleep(0.01)

    tarea = asyncio.create_task(consumidor())
    rafaga = asyncio.create_task(e.booking.rafaga(e.post, 90, espera=0.3, reintentos=6))
    con = _p90(await _cotizaciones())  # con la ráfaga corriendo
    resultados = await rafaga
    terminada.set()
    await tarea
    assert all(r.entregado for r in resultados)
    assert len(await anuncios.recientes()) == 90  # la ráfaga se entregó entera mientras se cotizaba
    print(f"p90 cotización: sin ráfaga {base:.3f}s, con ráfaga {con:.3f}s")
    assert con <= max(base * 1.10, base + 0.05)  # no se degrada (10 % o 50 ms de margen de medición)
    assert con < 0.8  # y sigue dentro de la cota de QA-PER-02
