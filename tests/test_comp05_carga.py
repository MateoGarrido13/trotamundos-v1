# SPEC: SPEC-COMP-05
# ELEMENTO PASO 5: Cuentas, alta y autenticación (ITERACION_4)
# ADRs: ADR-IT4-001, ADR-IT4-002, ADR-IT4-003
# DRIVERS: QA-ESC-01
"""1.000 altas repartidas en las tres regiones, con 100 en vuelo a la vez (PLAN-COMP-05, D12)."""
import asyncio
import time
from dataclasses import replace

import httpx
import pytest

from trotamundos.app import create_app
from trotamundos.config import Configuracion

pytestmark = [pytest.mark.db, pytest.mark.carga]
ALTAS = 1000
COTA_CONFIRMACION_SEGUNDOS = 2.0
EN_VUELO = 100  # altas simultáneas; las 1.000 se envían todas, de a tandas


async def test_AC_COMP_05_13_mil_altas_con_cien_en_vuelo(cuentas_limpias, bases_limpias, analitica_limpia):
    cfg = Configuracion(bases=bases_limpias, analitica=analitica_limpia,
                        identidad=replace(cuentas_limpias, exigir_gateway=True))
    app = create_app(cfg)
    regiones = cfg.identidad.regiones
    tiempos: list[float] = []
    estados: list[int] = []

    cupo = asyncio.Semaphore(EN_VUELO)

    async def alta(c: httpx.AsyncClient, i: int) -> None:
        async with cupo:  # el tiempo se mide desde que el pedido sale, no desde que espera su turno
            inicio = time.monotonic()
            r = await c.post("/auth/alta", json={"correo": f"usuario{i}@mail.com", "contrasena": "clave-1",
                                                 "region": regiones[i % len(regiones)]})
            tiempos.append(time.monotonic() - inicio)
            estados.append(r.status_code)

    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            await asyncio.gather(*(alta(c, i) for i in range(ALTAS)))
    finally:
        app.state.red_regiones.cerrar()
    rechazos = [e for e in estados if e != 201]
    print(f"\naltas={len(estados)} rechazos={len(rechazos)} max={max(tiempos):.2f}s p95={sorted(tiempos)[949]:.2f}s")
    assert len(estados) == ALTAS and not rechazos  # 0 rechazos por saturación o timeout
    assert max(tiempos) < COTA_CONFIRMACION_SEGUNDOS
