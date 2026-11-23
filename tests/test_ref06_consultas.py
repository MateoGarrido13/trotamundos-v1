# SPEC: SPEC-REF-06
# ELEMENTO PASO 5: Servicio de consultas analíticas (ITERACION_5)
# ADRs: ADR-IT5-001, ADR-IT5-002
# DRIVERS: REF-06, QA-PER-04*, QA-PER-02, QA-DIS-01
"""T-REF-06-05: el informe, su acceso, su cota y su aislamiento."""
import time
from dataclasses import replace
from datetime import date

import pytest

from tests.ref06_util import evento, sembrar
from trotamundos.analitica.consultas import AccesoDenegado, ErrorTiempoAgotado, ServicioConsultas

pytestmark = pytest.mark.db
D1, D2, D3 = (2026, 11, 22), (2026, 11, 23), (2026, 11, 24)
RANGO = (date(2026, 11, 1), date(2026, 11, 30))


@pytest.fixture
def servicio(analitica_limpia):
    return ServicioConsultas(replace(analitica_limpia, cuentas_datos=("analista",)))


async def test_el_informe_tiene_las_tres_secciones_por_dia(servicio, analitica_limpia):
    sembrar(analitica_limpia,
            evento("a1", dia=D1), evento("a2", dia=D2), evento("a3", dia=D2, destino="Lima"),
            evento("a4", dia=D2), evento("m1", "modificacion", dia=D2),  # una modificación no es un alta
            evento("b1", "baja", dia=D2), evento("b2", "baja", dia=D3, destino="Lima"))
    informe = await servicio.informe("analista", *RANGO)
    assert informe["tendencias"] == [{"dia": "2026-11-22", "altas": 1}, {"dia": "2026-11-23", "altas": 3}]
    assert informe["destinos"] == [{"destino": "Roma", "reservas": 3}, {"destino": "Lima", "reservas": 1}]
    assert informe["cancelaciones"] == [{"dia": "2026-11-23", "destino": "Roma", "bajas": 1},
                                        {"dia": "2026-11-24", "destino": "Lima", "bajas": 1}]


async def test_el_informe_respeta_el_rango_y_los_filtros(servicio, analitica_limpia):
    sembrar(analitica_limpia,
            evento("a1", dia=D1), evento("a2", dia=D2, destino="Lima"), evento("a3", dia=D2, tipo_reserva="vuelo"),
            evento("b1", "baja", dia=D2, destino="Lima"))
    dia = date(2026, 11, 23)
    assert [t["altas"] for t in (await servicio.informe("analista", dia, dia))["tendencias"]] == [2]
    assert (await servicio.informe("analista", *RANGO, destino="Lima"))["destinos"] == [
        {"destino": "Lima", "reservas": 1}]
    assert (await servicio.informe("analista", *RANGO, tipo_reserva="vuelo"))["tendencias"] == [
        {"dia": "2026-11-23", "altas": 1}]
    assert (await servicio.informe("analista", *RANGO, destino="Lima"))["cancelaciones"][0]["bajas"] == 1


async def test_AC_REF_06_12_sin_eventos_en_el_rango_las_tres_secciones_llegan_vacias(servicio, analitica_limpia):
    sembrar(analitica_limpia, evento("a1", dia=D2))
    informe = await servicio.informe("analista", date(2020, 1, 1), date(2020, 1, 31))  # sin datos: no es un error
    assert (informe["tendencias"], informe["destinos"], informe["cancelaciones"]) == ([], [], [])


async def test_un_destino_vacio_se_informa_como_sin_destino(servicio, analitica_limpia):
    sembrar(analitica_limpia, evento("a1", destino=""))
    assert (await servicio.informe("analista", *RANGO))["destinos"] == [{"destino": None, "reservas": 1}]


async def test_AC_REF_06_10_una_cuenta_que_no_es_del_equipo_de_datos_recibe_acceso_denegado(analitica_limpia):
    # La base ni siquiera es alcanzable: el rechazo ocurre antes de tocarla y no devuelve ningún dato.
    servicio = ServicioConsultas(replace(analitica_limpia, dsn="postgresql://x:x@localhost:1/nada",
                                         cuentas_datos=("analista",)))
    for cuenta in ("luis", "", "ANALISTA", "analista "):
        with pytest.raises(AccesoDenegado):
            await servicio.informe(cuenta, *RANGO)


async def test_un_rango_invertido_se_rechaza(servicio):
    with pytest.raises(ValueError):
        await servicio.informe("analista", date(2026, 12, 1), date(2026, 11, 1))


async def test_AC_REF_06_11_al_vencer_la_cota_hay_error_de_tiempo_agotado_y_ningun_informe_parcial(analitica_limpia):
    sembrar(analitica_limpia, evento("a1", dia=D2))
    lento = ServicioConsultas(replace(analitica_limpia, cota_informe_segundos=0.3, cuentas_datos=("analista",)),
                              antes_de_consultar=lambda conn: conn.execute("SELECT pg_sleep(3)"))
    inicio = time.perf_counter()
    with pytest.raises(ErrorTiempoAgotado):
        await lento.informe("analista", *RANGO)  # la consulta duerme 3 s y la cota es de 0,3 s
    assert time.perf_counter() - inicio < 1.5  # el llamador no esperó a la consulta
    rapido = ServicioConsultas(replace(analitica_limpia, cuentas_datos=("analista",)))
    assert (await rapido.informe("analista", *RANGO))["tendencias"]  # y el servicio sigue sirviendo


async def test_la_cota_cancela_la_consulta_en_la_base(analitica_limpia):
    """`statement_timeout` corta la consulta de verdad: no queda corriendo en PostgreSQL."""
    from trotamundos.analitica.base import conectar
    lento = ServicioConsultas(replace(analitica_limpia, cota_informe_segundos=0.3, cuentas_datos=("analista",)),
                              antes_de_consultar=lambda conn: conn.execute("SELECT pg_sleep(5)"))
    with pytest.raises(ErrorTiempoAgotado):
        await lento.informe("analista", *RANGO)
    time.sleep(0.5)
    with conectar(analitica_limpia.dsn) as c:
        activas = c.execute("SELECT count(*) FROM pg_stat_activity WHERE query LIKE '%pg_sleep(5)%'"
                            " AND state = 'active' AND pid <> pg_backend_pid()").fetchone()[0]
    assert activas == 0


async def test_AC_REF_06_04_el_informe_no_lee_la_base_de_viajes_ni_usa_el_orquestador(
        servicio, analitica_limpia, monkeypatch):
    sembrar(analitica_limpia, evento("a1", dia=D2))
    import trotamundos.persistencia.conexion as conexion_de_viajes

    def prohibido(*a, **k):
        raise AssertionError("el informe intentó abrir una conexión a la Base de viajes")
    monkeypatch.setattr(conexion_de_viajes, "conectar", prohibido)
    assert (await servicio.informe("analista", *RANGO))["destinos"] == [{"destino": "Roma", "reservas": 1}]
    import sys
    # y el módulo del servicio no arrastra nada del Orquestador ni de la persistencia de viajes
    from trotamundos.analitica import consultas
    assert "orquestador" not in " ".join(m for m in vars(consultas) if isinstance(m, str))
    assert not [m for m in sys.modules if m.startswith("trotamundos.analitica") and "persistencia" in m]
