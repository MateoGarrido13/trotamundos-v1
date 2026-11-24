# SPEC: SPEC-COMP-04 | PLAN-COMP-04 T-COMP-04-02
import hashlib
from datetime import UTC, datetime

from tests.comp04_util import adjunto, mensaje, parte
from trotamundos.entrada.adaptador_correo import identificador_de
from trotamundos.entrada.gmail.mensajes import a_correo_crudo, html_a_texto

HTML = ('<html><head><style>p{color:red}</style><title>x</title></head><body><script>alert("x")</script>'
        '<div>Reserva <b>confirmada</b></div><p>Hotel&nbsp;Roma &amp; spa</p><br>fin</body></html>')


def test_un_mensaje_de_texto_plano_se_traduce_a_correo_crudo():
    recibido = datetime(2026, 11, 20, 15, 30, tzinfo=UTC)
    c = a_correo_crudo(mensaje("1", cuerpo="Su reserva", remitente="Agencia Viajes <Ventas@Agencia.COM>",
                               message_id="<abc@agencia.com>", recibido=recibido))
    assert (c.cuerpo, c.remitente, c.message_id, c.recibido) == (
        "Su reserva", "ventas@agencia.com", "<abc@agencia.com>", recibido)


def test_el_html_se_reduce_a_texto():
    texto = html_a_texto(HTML)
    assert "alert" not in texto and "color" not in texto and "<" not in texto
    assert texto.splitlines() == ["Reserva confirmada", "Hotel Roma & spa", "fin"]


def test_se_prefiere_el_texto_plano_a_la_alternativa_html():
    alternativas = {"mimeType": "multipart/alternative", "filename": "", "body": {"size": 0},
                    "parts": [parte("text/plain", "texto plano"), parte("text/html", "<p>otro</p>")]}
    assert a_correo_crudo(mensaje("1", payload=alternativas)).cuerpo == "texto plano"


def test_AC_COMP_04_09_html_y_adjuntos_se_entregan_solo_como_texto():
    multipart = {"mimeType": "multipart/mixed", "filename": "", "body": {"size": 0}, "parts": [
        {"mimeType": "multipart/related", "filename": "", "body": {"size": 0},
         "parts": [parte("text/html", HTML)]},
        adjunto("voucher.pdf"), adjunto("mapa.png")]}
    c = a_correo_crudo(mensaje("1", payload=multipart))
    assert c.cuerpo.splitlines() == ["Reserva confirmada", "Hotel Roma & spa", "fin"]
    assert "ANGjdJ8" not in c.cuerpo and "voucher" not in c.cuerpo and "<" not in c.cuerpo


def test_se_decodifica_con_el_charset_de_la_parte():
    c = a_correo_crudo(mensaje("1", payload=parte("text/plain", "Reservación en Ñandú, año nuevo", "iso-8859-1")))
    assert c.cuerpo == "Reservación en Ñandú, año nuevo"


def test_AC_COMP_04_08_sin_message_id_se_identifica_por_hash_estable():
    sin_id = mensaje("1", cuerpo="Reserva sin identificador", message_id=None)
    primero, segundo = a_correo_crudo(sin_id), a_correo_crudo(sin_id)  # dos sondeos leen el mismo mensaje
    assert primero.message_id is None
    esperado = hashlib.sha256(b"Reserva sin identificador").hexdigest()
    assert identificador_de(primero) == identificador_de(segundo) == esperado
    con_id = a_correo_crudo(mensaje("2", cuerpo="Reserva sin identificador", message_id="<z@x>"))
    assert identificador_de(con_id) == "<z@x>"


def test_un_mensaje_sin_payload_o_sin_fecha_es_invalido():
    import pytest

    from trotamundos.entrada.gmail.mensajes import MensajeInvalido

    with pytest.raises(MensajeInvalido):
        a_correo_crudo({"id": "1"})
    sin_fecha = mensaje("1")
    del sin_fecha["internalDate"]
    with pytest.raises(MensajeInvalido):
        a_correo_crudo(sin_fecha)
