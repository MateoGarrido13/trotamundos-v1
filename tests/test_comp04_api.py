# SPEC: SPEC-COMP-04 | PLAN-COMP-04 T-COMP-04-03
import logging
from datetime import UTC, datetime, timedelta

import pytest

from tests.comp04_util import TOKEN, GoogleSimulado, api_con, mensaje
from trotamundos.entrada.api_correo import ErrorApiCorreo, TokenInvalido

AHORA = datetime.now(UTC)
VENTANA = AHORA - timedelta(days=7)


@pytest.fixture
def google():
    g = GoogleSimulado()
    g.dar_token("ana")
    return g


async def test_lee_los_mensajes_de_la_ventana_como_correo_crudo(google):
    google.agregar("ana", mensaje("m1", cuerpo="uno", message_id="<1@x>", recibido=AHORA - timedelta(days=2)),
                   mensaje("m2", cuerpo="dos", message_id="<2@x>", recibido=AHORA - timedelta(days=1)))
    correos = await api_con(google).leer_mensajes(TOKEN, VENTANA)
    assert [(c.cuerpo, c.message_id) for c in correos] == [("uno", "<1@x>"), ("dos", "<2@x>")]
    assert all(c.remitente == "agencia@x.com" for c in correos)


async def test_descarta_lo_anterior_a_la_ventana_aunque_gmail_lo_devuelva_por_el_dia(google):
    google.agregar("ana", mensaje("viejo", recibido=VENTANA - timedelta(hours=2)),
                   mensaje("nuevo", cuerpo="nuevo", recibido=VENTANA + timedelta(hours=2)))
    assert [c.cuerpo for c in await api_con(google).leer_mensajes(TOKEN, VENTANA)] == ["nuevo"]


async def test_pagina_hasta_el_tope_de_mensajes_por_sondeo(google):
    google.tamano_pagina = 2
    google.agregar("ana", *(mensaje(f"m{i}", cuerpo=str(i), message_id=f"<{i}@x>",
                                    recibido=AHORA - timedelta(hours=10 - i)) for i in range(7)))
    assert len(await api_con(google, max_mensajes_por_sondeo=5).leer_mensajes(TOKEN, VENTANA)) == 5
    assert len(google.llamadas("/messages") ) >= 3 + 5  # 3 páginas de la lista y 5 detalles
    google.pedidos.clear()
    assert len(await api_con(google).leer_mensajes(TOKEN, VENTANA)) == 7  # sin tope se leen todos


async def test_un_buzon_vacio_no_pide_detalles(google):
    assert await api_con(google).leer_mensajes(TOKEN, VENTANA) == []
    assert len(google.pedidos) == 1


async def test_un_mensaje_ilegible_se_descarta_y_los_demas_llegan(google):
    roto = mensaje("roto")
    del roto["payload"]
    google.agregar("ana", roto, mensaje("bueno", cuerpo="ok"))
    assert [c.cuerpo for c in await api_con(google).leer_mensajes(TOKEN, VENTANA)] == ["ok"]


async def test_gmail_rechaza_el_token_con_401_es_token_invalido(google):
    with pytest.raises(TokenInvalido):
        await api_con(google).leer_mensajes("token-que-google-no-conoce", VENTANA)
    google.estado_lista = 401
    with pytest.raises(TokenInvalido):
        await api_con(google).leer_mensajes(TOKEN, VENTANA)


@pytest.mark.parametrize("estado", [403, 429, 500, 503])
async def test_cualquier_otro_fallo_de_gmail_es_error_de_la_api_y_no_se_reintenta(google, estado):
    google.estado_lista = estado
    with pytest.raises(ErrorApiCorreo) as error:
        await api_con(google).leer_mensajes(TOKEN, VENTANA)
    assert not isinstance(error.value, TokenInvalido)
    assert len(google.llamadas("/messages")) == 1  # regla 9: sin reintento


async def test_la_demora_mayor_que_la_cota_es_error_de_la_api_y_no_se_reintenta(google):
    google.demora_segundos = 0.5
    with pytest.raises(ErrorApiCorreo):
        await api_con(google, cota_llamada_gmail_segundos=0.1).leer_mensajes(TOKEN, VENTANA)
    assert len(google.pedidos) == 1


async def test_el_detalle_que_falla_hace_fallar_el_sondeo_de_ese_titular(google):
    google.agregar("ana", mensaje("m1"), mensaje("m2"))
    google.buzones["ana"][1]["id"] = "m2"
    original = google._gmail

    def falla_el_detalle(pedido, ruta):
        from httpx import Response

        return Response(500) if ruta.endswith("/messages/m2") else original(pedido, ruta)

    google._gmail = falla_el_detalle
    with pytest.raises(ErrorApiCorreo):
        await api_con(google).leer_mensajes(TOKEN, VENTANA)


async def test_AC_COMP_04_07_el_token_viaja_solo_en_el_encabezado_y_no_figura_en_ningun_log(google, caplog):
    caplog.set_level(logging.DEBUG)
    google.agregar("ana", mensaje("m1"))
    await api_con(google).leer_mensajes(TOKEN, VENTANA)
    google.estado_lista = 500
    with pytest.raises(ErrorApiCorreo):
        await api_con(google).leer_mensajes(TOKEN, VENTANA)
    for pedido in google.pedidos:
        assert pedido.headers["authorization"] == f"Bearer {TOKEN}"
        assert TOKEN not in str(pedido.url) and TOKEN not in pedido.content.decode()
    assert TOKEN not in caplog.text
