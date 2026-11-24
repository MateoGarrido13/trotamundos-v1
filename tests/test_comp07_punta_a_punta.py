# SPEC: SPEC-COMP-07 | PLAN-COMP-07 T-COMP-07-06
# ELEMENTO PASO 5: Booking -> Adaptador de anuncios -> cola de novedades -> Servicio de ingesta -> Orquestador
# DRIVERS: QA-PER-01, QA-INT-01, CON-02
"""La app armada: un aviso por HTTP termina en «Novedades»."""
import asyncio
import time

import httpx
import pytest

from tests.comp07_util import CFG, CLAVE
from trotamundos.app import create_app
from trotamundos.broker import ResultadoEntrega
from trotamundos.config import Configuracion
from trotamundos.entrada.booking.simulado import RUTA_AVISOS, BookingSimulado

pytestmark = pytest.mark.db


@pytest.fixture
def app(bases_limpias, analitica_limpia):
    return create_app(Configuracion(bases=bases_limpias, analitica=analitica_limpia, booking=CFG))


def cliente(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("10.0.0.9", 4000)), base_url="http://t")


async def drenar(app):
    while await app.state.nodos_correo.ingesta.procesar_uno() is not ResultadoEntrega.VACIA:
        pass


async def test_AC_COMP_07_05_el_anuncio_llega_a_novedades_con_retraso_menor_a_5_minutos(app):
    async with cliente(app) as c:
        booking = BookingSimulado(CLAVE)

        async def post(ruta, cuerpo, cabeceras):
            return (await c.post(ruta, json=cuerpo, headers=cabeceras)).status_code

        resultados = await booking.rafaga(post, 5)
        assert all(r.entregado for r in resultados)
        await drenar(app)
        r = await c.get("/novedades/anuncios", headers={"X-Viajero-Id": "ana"})
        assert {a["id"] for a in r.json()} == {f"booking:b-{i}" for i in range(5)}
    retraso = app.state.base_viajes.leer(lambda con: con.execute(
        "SELECT avg(extract(epoch FROM recibido_en - detectado_en)), count(*) FROM anuncio").fetchone())
    assert retraso[1] == 5 and 0 <= float(retraso[0]) < 300  # QA-PER-01: menos de 5 minutos de media


async def test_con_el_ciclo_de_vida_el_consumidor_entrega_solo(app):
    """El consumidor de la cola de novedades corre en el ciclo de vida de la app: nadie lo invoca a mano."""
    async with app.router.lifespan_context(app), cliente(app) as c:
        r = await c.post(RUTA_AVISOS, json=BookingSimulado.aviso(1), headers={"X-Clave-Proveedor": CLAVE})
        assert r.status_code == 202
        limite = time.monotonic() + 10
        while time.monotonic() < limite:
            visibles = (await c.get("/novedades/anuncios", headers={"X-Viajero-Id": "ana"})).json()
            if visibles:
                break
            await asyncio.sleep(0.1)
        assert [a["id"] for a in visibles] == ["booking:b-1"]


async def test_sin_la_clave_configurada_ningun_aviso_entra(bases_limpias, analitica_limpia):
    app = create_app(Configuracion(bases=bases_limpias, analitica=analitica_limpia))  # clave vacía
    async with cliente(app) as c:
        r = await c.post(RUTA_AVISOS, json=BookingSimulado.aviso(1), headers={"X-Clave-Proveedor": ""})
        assert r.status_code == 401


async def test_el_ping_de_la_app_informa_a_operaciones_si_booking_no_da_eco(app):
    assert await app.state.booking.adaptador.verificar_eco() is True
    app.state.booking.simulado.sin_eco = True
    assert await app.state.booking.adaptador.verificar_eco() is False
    assert app.state.booking.adaptador.avisos == ["Booking no responde al ping (sin eco)"]


async def test_AC_COMP_07_09_el_listener_solo_importa_el_broker():
    """Las dependencias reales del listener (no solo las reglas de la tabla)."""
    from tests.test_arquitectura import _archivos, _imports

    prohibidos = ("trotamundos.persistencia", "trotamundos.orquestador", "psycopg")
    archivos = _archivos("entrada/booking")
    assert {a.name for a in archivos} >= {"adaptador.py", "listener.py", "aviso.py", "tasa.py", "simulado.py"}
    internos = set()
    for archivo in archivos:
        malos = [m for m in _imports(archivo) if any(m == p or m.startswith(p + ".") for p in prohibidos)]
        assert not malos, f"{archivo.name} importa {malos}"
        internos |= {m for m in _imports(archivo) if m.startswith("trotamundos.") and ".entrada.booking" not in m}
    assert "trotamundos.broker" in internos  # habla con el Broker
    assert {m.split(".")[1] for m in internos} <= {"broker", "config", "entrada"}
