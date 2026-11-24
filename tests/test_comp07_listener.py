# SPEC: SPEC-COMP-07 | PLAN-COMP-07 T-COMP-07-03
import pytest

from tests.comp07_util import CFG, Entorno
from trotamundos.broker import Mensaje, NombreCola
from trotamundos.config import ConfiguracionBooking
from trotamundos.entrada.booking.simulado import BookingSimulado
from trotamundos.entrada.booking.tasa import LimitadorVentana

AVISO = BookingSimulado.aviso(1)


@pytest.fixture
def e():
    return Entorno()


async def test_AC_COMP_07_01_un_aviso_valido_queda_en_la_cola_con_su_identificador(e):
    r = await e.avisar(AVISO)
    assert r.status_code == 202 and r.json() == {"id": "booking:b-1"}
    assert e.en_cola() == 1
    mensajes: list[Mensaje] = []

    async def tomar(m):
        mensajes.append(m)

    await e.broker.procesar_uno(NombreCola.NOVEDADES, tomar)
    [m] = mensajes
    assert m.id == "booking:b-1" and m.cuerpo["origen"] == "anuncio"
    assert m.cuerpo["anuncio"]["titulo"] == "Escapada número 1" and m.cuerpo["detectado_en"]


@pytest.mark.parametrize("clave", [None, "", "otra-clave", "clave-de-booking "])
async def test_AC_COMP_07_02_clave_invalida_es_401_y_no_publica(e, clave):
    r = await e.avisar(AVISO, clave=clave)
    assert r.status_code == 401 and e.en_cola() == 0


async def test_sin_clave_configurada_ningun_aviso_es_valido():
    e = Entorno(cfg=ConfiguracionBooking(clave_proveedor=""))
    assert (await e.avisar(AVISO, clave="")).status_code == 401
    assert (await e.avisar(AVISO, clave="cualquiera")).status_code == 401 and e.en_cola() == 0


async def test_la_clave_se_mira_antes_que_el_cuerpo(e):
    r = await e.http.post("/proveedores/booking/avisos", content=b"no es json", headers={"X-Clave-Proveedor": "mala"})
    assert r.status_code == 401


async def test_AC_COMP_07_03_cola_llena_es_503_y_avisa_a_operaciones():
    e = Entorno(tamano_cola=1)
    assert (await e.avisar(BookingSimulado.aviso(1))).status_code == 202
    r = await e.avisar(BookingSimulado.aviso(2))
    assert r.status_code == 503 and r.headers["retry-after"] == "1"
    assert e.en_cola() == 1  # el rechazado no se encoló
    assert [a.tipo for a in e.avisos_broker] == ["cola_llena"]  # aviso del Broker
    assert len(e.adaptador.avisos) == 1 and "booking:b-2" in e.adaptador.avisos[0]  # y el del listener
    # Booking reentrega cuando hay lugar.
    async def tomar(m):
        pass

    await e.broker.procesar_uno(NombreCola.NOVEDADES, tomar)
    assert (await e.avisar(BookingSimulado.aviso(2))).status_code == 202


async def test_AC_COMP_07_10_un_aviso_que_no_se_traduce_es_422_y_no_entra_a_la_cola(e):
    for cuerpo in ({**AVISO, "fin": "2020-01-01"}, {"aviso_id": "x"}, [1, 2], {**AVISO, "extra": 1}):
        assert (await e.avisar(cuerpo)).status_code == 422
    r = await e.http.post("/proveedores/booking/avisos", content=b"{roto", headers={"X-Clave-Proveedor": "clave-de-booking"})
    assert r.status_code == 422 and e.en_cola() == 0


async def test_la_tasa_por_origen_se_limita_con_429_y_cada_origen_tiene_la_suya():
    e = Entorno(cfg=ConfiguracionBooking(clave_proveedor="clave-de-booking", tasa_avisos_por_origen=3))
    codigos = [(await e.avisar(BookingSimulado.aviso(i))).status_code for i in range(5)]
    assert codigos == [202, 202, 202, 429, 429] and e.en_cola() == 3
    assert (await e.avisar(BookingSimulado.aviso(9))).headers.get("retry-after") == "1"


def test_el_limitador_libera_cuando_pasa_la_ventana_y_separa_los_origenes():
    t = [0.0]
    lim = LimitadorVentana(2, reloj=lambda: t[0])
    assert [lim.permitir("a"), lim.permitir("a"), lim.permitir("a"), lim.permitir("b")] == [True, True, False, True]
    t[0] = 1.01
    assert lim.permitir("a") is True


async def test_un_aviso_repetido_se_encola_las_dos_veces_y_lo_descarta_la_ingesta(e):
    """El listener no deduplica: el identificador es el mismo y la ingesta lo descarta (AC-04)."""
    await e.avisar(AVISO)
    await e.avisar(AVISO)
    assert e.en_cola() == 2


async def test_booking_es_un_iproveedor_y_los_adaptadores_de_cotizacion_no_reciben_novedades(e):
    from tests.comp06_util import sistema

    assert e.adaptador.nombre == "booking" and await e.adaptador.ping() is True
    assert await e.adaptador.recibir_novedad(AVISO) == "booking:b-1"
    for adaptador in sistema().nodos[0]._servicio._cotizadores:  # D13: la cotización no recibe avisos
        with pytest.raises(NotImplementedError):
            await adaptador.recibir_novedad({})
