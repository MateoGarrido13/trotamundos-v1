# SPEC: SPEC-REF-06
# ELEMENTO PASO 5: Servicio de consultas analíticas, Proyector, Base analítica (ITERACION_5)
# ADRs: ADR-IT5-002
# DRIVERS: REF-06, QA-PER-04*
"""T-REF-06-07: prueba de carga de `AC-REF-06-03`.

El millón de eventos se siembra directamente en la Base analítica, sin pasar por el Orquestador,
como autoriza la spec: la cota mide la generación del informe sobre preagregados."""
import asyncio
import time
from dataclasses import replace

import pytest

from tests.ref06_util import evento
from trotamundos.analitica.base import conectar
from trotamundos.analitica.consultas import ServicioConsultas
from trotamundos.analitica.proyector import Proyector
from trotamundos.broker import Broker, Mensaje, NombreCola, ResultadoEntrega
from trotamundos.config import ConfiguracionBroker

pytestmark = [pytest.mark.db, pytest.mark.carga]
EVENTOS = 1_000_000
INFORMES = 10
COTA = 10.0

SEMBRAR = """
INSERT INTO evento (id, tipo, tipo_reserva, destino, origen, estado, ocurrido_en, dia)
SELECT 'seed-' || g,
       (ARRAY['alta','alta','alta','modificacion','baja'])[1 + abs(hashtext('t' || g)) %% 5],
       (ARRAY['hotel','auto','vuelo','tren','autobus','actividad'])[1 + abs(hashtext('r' || g)) %% 6],
       'destino-' || (abs(hashtext('d' || g)) %% 50),
       'manual', 'confirmada',
       timestamptz '2026-01-01' + (abs(hashtext('f' || g)) %% 365) * interval '1 day',
       (date '2026-01-01' + (abs(hashtext('f' || g)) %% 365))
FROM generate_series(1, %s) AS g
"""
AGREGAR = """
INSERT INTO contador (dia, destino, tipo_reserva, tipo_evento, cantidad)
SELECT dia, destino, tipo_reserva, tipo, count(*) FROM evento GROUP BY dia, destino, tipo_reserva, tipo
"""


async def test_AC_REF_06_03_diez_informes_concurrentes_sobre_un_millon_de_eventos_tardan_menos_de_10_s(analitica_limpia):
    cfg = replace(analitica_limpia, cuentas_datos=("analista",), cota_informe_segundos=COTA)
    with conectar(cfg.dsn, autocommit=True) as c:
        c.execute(SEMBRAR, (EVENTOS,))
        c.execute(AGREGAR)
        c.execute("ANALYZE")
        assert c.execute("SELECT count(*) FROM evento").fetchone()[0] == EVENTOS
        esperado = c.execute("SELECT sum(cantidad) FROM contador WHERE tipo_evento = 'alta'").fetchone()[0]

    # el Proyector sigue consumiendo eventos nuevos mientras se piden los informes
    broker = Broker(ConfiguracionBroker(tamano_maximo_cola=1000), tamanos={NombreCola.EVENTOS_ANALITICOS: 1000})
    for i in range(500):
        e = evento(f"vivo-{i}", destino=f"destino-{i % 50}", dia=(2026, 6, 1 + i % 28))
        broker.publicar(NombreCola.EVENTOS_ANALITICOS, Mensaje(e.id, e.model_dump(mode="json")))
    proyector = Proyector(broker, cfg.dsn)
    servicio = ServicioConsultas(cfg)

    async def consumir() -> int:
        n = 0
        while await proyector.procesar_uno() is not ResultadoEntrega.VACIA:
            n += 1
            await asyncio.sleep(0)
        return n

    async def pedir(i: int) -> tuple[float, dict]:
        inicio = time.perf_counter()
        informe = await servicio.informe("analista", __import__("datetime").date(2026, 1, 1),
                                         __import__("datetime").date(2026, 12, 31))
        return time.perf_counter() - inicio, informe

    try:
        consumo = asyncio.create_task(consumir())
        resultados = await asyncio.gather(*(pedir(i) for i in range(INFORMES)))
        procesados = await consumo
    finally:
        proyector.cerrar()

    tiempos = [t for t, _ in resultados]
    promedio = sum(tiempos) / len(tiempos)
    print(f"\ncarga: {INFORMES} informes concurrentes sobre {EVENTOS:,} eventos: "
          f"promedio {promedio:.2f} s, máximo {max(tiempos):.2f} s; el Proyector consumió {procesados} eventos")
    assert promedio < COTA, f"promedio {promedio:.2f} s"
    assert max(tiempos) < COTA
    assert procesados == 500  # el Proyector no se detuvo
    informe = resultados[0][1]
    assert informe["tendencias"] and informe["destinos"] and informe["cancelaciones"]
    # el informe es consistente con lo sembrado (más lo que el Proyector sumó, que puede o no haber entrado)
    total = sum(d["altas"] for d in informe["tendencias"])
    assert esperado <= total <= esperado + 500
