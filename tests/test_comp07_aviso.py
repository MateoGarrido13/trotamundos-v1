# SPEC: SPEC-COMP-07 | PLAN-COMP-07 T-COMP-07-02
import pytest

from trotamundos.entrada.booking.aviso import AvisoInvalido, traducir_aviso
from trotamundos.entrada.booking.simulado import BookingSimulado, ErrorBooking

AVISO = BookingSimulado.aviso(7)


def test_un_aviso_valido_se_traduce_a_la_novedad_interna_con_identificador_estable():
    novedad = traducir_aviso(AVISO)
    assert novedad == {"id": "booking:b-7", "titulo": "Escapada número 7", "destino": "Lisboa",
                       "inicio": "2027-03-10", "fin": "2027-03-17", "proveedor": "Booking"}
    assert traducir_aviso(dict(AVISO))["id"] == novedad["id"]  # el mismo aviso, el mismo identificador


@pytest.mark.parametrize("cambios", [
    {"aviso_id": ""}, {"titulo": ""}, {"destino": "x" * 201}, {"inicio": "no-es-fecha"},
    {"inicio": "2027-03-20", "fin": "2027-03-10"}, {"aviso_id": 7}, {"intruso": "x"}, {"proveedor": None},
])
def test_AC_COMP_07_10_un_aviso_que_no_se_traduce_se_rechaza(cambios):
    with pytest.raises(AvisoInvalido):
        traducir_aviso({**AVISO, **cambios})


@pytest.mark.parametrize("cuerpo", [None, [], "texto", 7, {}])
def test_lo_que_no_es_un_objeto_con_los_campos_no_es_un_aviso(cuerpo):
    with pytest.raises(AvisoInvalido):
        traducir_aviso(cuerpo)


def test_la_falta_de_un_campo_se_informa_sin_devolver_el_contenido():
    with pytest.raises(AvisoInvalido) as e:
        traducir_aviso({k: v for k, v in AVISO.items() if k != "destino"})
    assert "destino" in str(e.value) and "Lisboa" not in str(e.value)


async def test_booking_simulado_inyecta_demora_caida_y_falta_de_eco():
    b = BookingSimulado()
    assert await b.ping() is True
    b.sin_eco = True
    assert await b.ping() is False
    b.sin_eco, b.caida = False, True
    with pytest.raises(ErrorBooking):
        await b.ping()
    assert b.pings == 3


async def test_booking_simulado_reentrega_ante_503_y_429_y_se_rinde_al_agotar():
    respuestas = iter([503, 429, 202])

    async def post(ruta, cuerpo, cabeceras):
        return next(respuestas)

    r = await BookingSimulado().enviar(post, AVISO, espera=0)
    assert r.codigos == [503, 429, 202] and r.entregado and r.intentos == 3

    async def siempre_503(ruta, cuerpo, cabeceras):
        return 503

    r = await BookingSimulado().enviar(siempre_503, AVISO, reintentos=2, espera=0)
    assert r.intentos == 3 and not r.entregado
    async def rechazada(ruta, cuerpo, cabeceras):
        return 401

    assert (await BookingSimulado().enviar(rechazada, AVISO, espera=0)).codigos == [401]  # 401 no se reentrega
