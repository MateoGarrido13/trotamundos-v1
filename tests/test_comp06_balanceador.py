# SPEC: SPEC-COMP-06 | PLAN-COMP-06 T-COMP-06-04
import asyncio

import pytest

from tests.comp06_util import CRITERIOS, Cronometro, sistema
from trotamundos.dominio.cotizacion import ProgresoGrilla
from trotamundos.dominio.puertos_cotizacion import SinNodosDisponibles


async def test_AC_COMP_06_10_nodo_sin_eco_sale_y_se_reenvia_lo_que_estaba_en_vuelo():
    sis = sistema()
    a, b = sis.nodos
    a.demora_segundos = 0.1
    a.caer_en_vuelo = True  # el pedido llega a `a` y `a` cae con él en vuelo
    with Cronometro() as t:
        grilla = await sis.balanceador.despachar(CRITERIOS, ProgresoGrilla())
    assert grilla.completa and t.segundos < 0.8  # el reenvío llegó a un nodo sano a tiempo
    assert (a.atendidos, b.atendidos) == (1, 1)
    assert sis.balanceador.nodos_sanos == ["cotizacion-2"]
    assert len(sis.balanceador.avisos) == 1 and "cotizacion-1" in sis.balanceador.avisos[0]
    # El nodo caído ya no recibe pedidos.
    for _ in range(5):
        await sis.balanceador.despachar(CRITERIOS, ProgresoGrilla())
    assert a.atendidos == 1


async def test_nodo_sin_eco_en_el_health_check_sale_de_rotacion_y_vuelve():
    sis = sistema()
    a, b = sis.nodos
    a.sin_eco = True
    await sis.balanceador.verificar_nodos()
    assert sis.balanceador.nodos_sanos == ["cotizacion-2"] and len(sis.balanceador.avisos) == 1
    await sis.balanceador.verificar_nodos()  # no repite el aviso
    assert len(sis.balanceador.avisos) == 1
    for _ in range(4):
        await sis.balanceador.despachar(CRITERIOS, ProgresoGrilla())
    assert (a.atendidos, b.atendidos) == (0, 4)
    a.sin_eco = False
    await sis.balanceador.verificar_nodos()
    assert sis.balanceador.nodos_sanos == ["cotizacion-1", "cotizacion-2"]


async def test_los_pedidos_se_reparten_entre_los_nodos_sanos():
    sis = sistema()
    for _ in range(6):
        await sis.balanceador.despachar(CRITERIOS, ProgresoGrilla())
    assert [n.atendidos for n in sis.nodos] == [3, 3]


async def test_sin_nodos_sanos_se_avisa_y_no_se_cuelga():
    sis = sistema()
    for n in sis.nodos:
        n.sin_eco = True
    await sis.balanceador.verificar_nodos()
    with pytest.raises(SinNodosDisponibles):
        await sis.balanceador.despachar(CRITERIOS, ProgresoGrilla())


async def test_el_health_check_corre_periodicamente_hasta_que_se_cancela():
    sis = sistema(intervalo_eco_ms=20)
    tarea = asyncio.create_task(sis.balanceador.ejecutar())
    sis.nodos[0].sin_eco = True
    await asyncio.sleep(0.15)
    assert sis.balanceador.nodos_sanos == ["cotizacion-2"]
    tarea.cancel()
    await asyncio.gather(tarea, return_exceptions=True)
    assert tarea.cancelled()
