# SPEC: SPEC-COMP-07 | PLAN-COMP-07 T-COMP-07-05
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI

from tests.comp07_util import CFG, Entorno
from tests.ref03_util import reserva_norm
from trotamundos.broker import NombreCola, ResultadoEntrega
from trotamundos.config import ConfiguracionBooking
from trotamundos.dominio.puertos_anuncios import Anuncio
from trotamundos.entrada.booking.simulado import BookingSimulado
from trotamundos.entrada.ingesta import ServicioIngesta
from trotamundos.orquestador import api_anuncios
from trotamundos.orquestador.anuncios import ServicioAnuncios
from trotamundos.persistencia.base_viajes import BaseViajes

pytestmark = pytest.mark.db
T0 = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


class Reloj:
    def __init__(self, ahora=T0):
        self.ahora = ahora

    def __call__(self):
        return self.ahora


class EntregaReservas:
    def __init__(self):
        self.reservas = []

    async def incorporar(self, reserva):
        self.reservas.append(reserva)


def anuncio(n, detectado=T0) -> Anuncio:
    return Anuncio(id=f"booking:b-{n}", titulo=f"Escapada {n}", destino="Lisboa",
                   inicio=datetime(2027, 3, 10).date(), fin=datetime(2027, 3, 17).date(), proveedor="Booking",
                   detectado_en=detectado)


@pytest.fixture
def servicio(bases_limpias):
    reloj = Reloj()
    return ServicioAnuncios(BaseViajes.desde_config(bases_limpias), CFG, reloj=reloj), reloj


@pytest.fixture
def web(servicio):
    app = FastAPI()
    app.include_router(api_anuncios.router)
    app.state.anuncios = servicio[0]
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


async def test_guardar_un_anuncio_es_idempotente(servicio):
    svc, _ = servicio
    assert await svc.guardar_anuncio(anuncio(1)) is True
    assert await svc.guardar_anuncio(anuncio(1)) is False  # una entrega repetida no duplica
    assert [f.id for f in await svc.recientes()] == ["booking:b-1"]


async def test_AC_COMP_07_04_el_mismo_aviso_dos_veces_se_muestra_una_sola_vez(servicio, web):
    svc, _ = servicio
    e = Entorno()  # el listener sobre su propio Broker
    ingesta = ServicioIngesta(e.broker, EntregaReservas(), entrega_anuncios=svc)
    aviso = BookingSimulado.aviso(1)
    assert (await e.avisar(aviso)).status_code == 202
    assert (await e.avisar(aviso)).status_code == 202  # Booking reentregó el mismo aviso
    assert e.en_cola() == 2
    while await ingesta.procesar_uno() is not ResultadoEntrega.VACIA:
        pass
    r = await web.get("/novedades/anuncios", headers={"X-Viajero-Id": "ana"})
    assert [a["id"] for a in r.json()] == ["booking:b-1"]


async def test_la_lista_va_del_mas_reciente_al_mas_viejo_y_respeta_el_tope_y_la_retencion(servicio, web):
    svc, reloj = servicio
    for n, dias in ((1, 40), (2, 10), (3, 1), (4, 5)):  # el 1 se guardó hace 40 días: fuera de los 30
        reloj.ahora = T0 - timedelta(days=dias)
        await svc.guardar_anuncio(anuncio(n))
    reloj.ahora = T0
    r = await web.get("/novedades/anuncios", headers={"X-Viajero-Id": "ana"})
    assert [a["id"] for a in r.json()] == ["booking:b-3", "booking:b-4", "booking:b-2"]
    assert set(r.json()[0]) == {"id", "titulo", "destino", "inicio", "fin", "proveedor", "recibido_en"}
    chico = ServicioAnuncios(svc._base, ConfiguracionBooking(clave_proveedor="x", tope_listado_anuncios=2), reloj=reloj)
    assert [f.id for f in await chico.recientes()] == ["booking:b-3", "booking:b-4"]


async def test_sin_anuncios_la_lista_es_vacia_y_sin_identidad_es_401(web):
    assert (await web.get("/novedades/anuncios", headers={"X-Viajero-Id": "ana"})).json() == []
    assert (await web.get("/novedades/anuncios")).status_code == 401


async def test_los_anuncios_los_ven_todos_los_viajeros(servicio, web):
    await servicio[0].guardar_anuncio(anuncio(1))
    for viajero in ("ana", "luis"):
        r = await web.get("/novedades/anuncios", headers={"X-Viajero-Id": viajero})
        assert [a["id"] for a in r.json()] == ["booking:b-1"]


async def test_un_anuncio_no_modifica_reservas_y_convive_con_las_reservas_del_correo_en_la_misma_cola(servicio):
    svc, _ = servicio
    e = Entorno()
    entrega = EntregaReservas()
    ingesta = ServicioIngesta(e.broker, entrega, entrega_anuncios=svc)
    await e.avisar(BookingSimulado.aviso(1))
    await ingesta.recibir(reserva_norm("<m1@x>"))  # una reserva del correo, por la misma cola
    await e.avisar(BookingSimulado.aviso(2))
    while await ingesta.procesar_uno() is not ResultadoEntrega.VACIA:
        pass
    assert [r.id_mensaje for r in entrega.reservas] == ["<m1@x>"]  # el correo siguió su camino
    assert sorted(f.id for f in await svc.recientes()) == ["booking:b-1", "booking:b-2"]
    assert e.broker.mensajes_muertos(NombreCola.NOVEDADES) == []


async def test_una_ingesta_sin_entrega_de_anuncios_los_manda_a_muertos_tras_los_reintentos():
    e = Entorno()
    e.broker._cfg = type(e.broker._cfg)(tamano_maximo_cola=10, reintentos=1, backoff_base_segundos=0)
    ingesta = ServicioIngesta(e.broker, EntregaReservas())
    await e.avisar(BookingSimulado.aviso(1))
    assert await ingesta.procesar_uno() is ResultadoEntrega.MUERTO
    assert [m.id for m in e.broker.mensajes_muertos(NombreCola.NOVEDADES)] == ["booking:b-1"]
