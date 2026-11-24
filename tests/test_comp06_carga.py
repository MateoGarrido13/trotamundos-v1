# SPEC: SPEC-COMP-06 | PLAN-COMP-06 T-COMP-06-07
import asyncio
import time

import pytest

from tests.comp06_util import borde_con, criterios, sistema

pytestmark = pytest.mark.carga


async def test_AC_COMP_06_11_percentil_90_en_800_ms_con_mil_pedidos():
    sis = sistema()
    for api in sis.apis.values():
        api.demora_segundos = 0.15  # 0,3 s por proveedor, como en el AC-01
    borde = borde_con(sis)

    async def pedido(i: int) -> float:
        inicio = time.perf_counter()
        grilla = await borde.obtener(criterios(i))  # criterios distintos: nada sale de la caché
        assert grilla.tiene_precios
        return time.perf_counter() - inicio

    tiempos = sorted(await asyncio.gather(*(pedido(i) for i in range(1000))))
    p90 = tiempos[899]
    print(f"p90={p90:.3f}s  max={tiempos[-1]:.3f}s")
    assert p90 <= 0.8
    await borde.cerrar()
