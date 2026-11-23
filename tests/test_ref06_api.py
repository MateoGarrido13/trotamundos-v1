# SPEC: SPEC-REF-06
# ELEMENTO PASO 5: Servicio de consultas analíticas, endpoint (ITERACION_5)
# ADRs: ADR-IT5-001, ADR-IT5-002
# DRIVERS: REF-06, QA-PER-04*
"""T-REF-06-06: el endpoint del informe y sus códigos."""
from dataclasses import replace

import httpx
import pytest

from tests.ref06_util import evento, sembrar
from trotamundos.analitica.app import create_app
from trotamundos.analitica.consultas import ServicioConsultas

pytestmark = pytest.mark.db
URL = "/analitica/informe"
Q = {"desde": "2026-11-01", "hasta": "2026-11-30"}


def cliente(servicio):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(servicio)), base_url="http://analitica")


@pytest.fixture
def cfg(analitica_limpia):
    return replace(analitica_limpia, cuentas_datos=("analista",))


async def test_el_informe_por_http(cfg, analitica_limpia):
    sembrar(analitica_limpia, evento("a1"), evento("b1", "baja"))
    async with cliente(ServicioConsultas(cfg)) as c:
        r = await c.get(URL, params=Q, headers={"X-Viajero-Id": "analista"})
    assert r.status_code == 200
    assert r.json()["tendencias"] == [{"dia": "2026-11-23", "altas": 1}]
    assert r.json()["cancelaciones"][0]["bajas"] == 1


async def test_AC_REF_06_10_acceso_denegado_por_http_sin_ningun_dato(cfg, analitica_limpia):
    sembrar(analitica_limpia, evento("a1"))
    async with cliente(ServicioConsultas(cfg)) as c:
        r = await c.get(URL, params=Q, headers={"X-Viajero-Id": "luis"})
    assert (r.status_code, r.json()) == (403, {"error": "acceso_denegado"})  # ni una sola sección del informe


async def test_AC_REF_06_11_la_cota_vencida_responde_504_sin_informe_parcial(cfg):
    lento = ServicioConsultas(replace(cfg, cota_informe_segundos=0.3),
                              antes_de_consultar=lambda conn: conn.execute("SELECT pg_sleep(3)"))
    async with cliente(lento) as c:
        r = await c.get(URL, params=Q, headers={"X-Viajero-Id": "analista"})
    assert (r.status_code, r.json()) == (504, {"error": "tiempo_agotado"})
    assert "tendencias" not in r.json()


async def test_AC_REF_06_04_el_servicio_responde_aunque_las_bases_de_viajes_no_existan(cfg, analitica_limpia):
    """El Servicio solo conoce la Base analítica: no necesita ninguna base de viajes."""
    sembrar(analitica_limpia, evento("a1"))
    async with cliente(ServicioConsultas(cfg)) as c:
        assert (await c.get(URL, params=Q, headers={"X-Viajero-Id": "analista"})).status_code == 200


async def test_los_errores_de_pedido_y_la_base_caida(cfg):
    async with cliente(ServicioConsultas(cfg)) as c:
        h = {"X-Viajero-Id": "analista"}
        assert (await c.get(URL, params={"desde": "2026-12-01", "hasta": "2026-11-01"}, headers=h)).status_code == 422
        assert (await c.get(URL, params={"desde": "no-es-fecha", "hasta": "2026-11-01"}, headers=h)).status_code == 422
        assert (await c.get(URL, params=Q)).status_code == 422  # sin identidad
    caida = ServicioConsultas(replace(cfg, dsn="postgresql://x:x@localhost:1/nada"))
    async with cliente(caida) as c:
        r = await c.get(URL, params=Q, headers={"X-Viajero-Id": "analista"})
    assert (r.status_code, r.json()) == (503, {"error": "base_analitica_no_disponible"})
