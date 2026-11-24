# SPEC: SPEC-COMP-04 | PLAN-COMP-04 T-COMP-04-06
# ELEMENTO PASO 5: Gestor de autorización -> Adaptador de correo -> Parseo -> Filtro -> Ingesta -> Orquestador
# DRIVERS: REF-02, QA-SEG-03*, CON-02
"""El correo real hasta el itinerario en PostgreSQL, con Google simulado y el Parseo como proceso del SO."""
import json
import logging
from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

import pytest

from tests.comp04_util import CFG, TOKEN, GoogleSimulado, adjunto, mensaje, parte
from trotamundos.app import create_app
from trotamundos.broker import ResultadoEntrega
from trotamundos.composicion import ensamblar_gmail
from trotamundos.config import Configuracion
from trotamundos.entrada.adaptador_correo import AdaptadorCorreo
from trotamundos.entrada.consumidor_correo import ConsumidorCorreo
from trotamundos.entrada.parseo_aislado.cliente import ClienteParseo

pytestmark = pytest.mark.db

AGENCIA = "agencia@x.com"


def reserva_json(lugar="Roma", codigo="H-1") -> str:
    return json.dumps({"tipo": "hotel", "inicio": "2026-12-01T10:00:00", "fin": "2026-12-05T10:00:00",
                       "lugar": lugar, "codigo": codigo})


class Sistema:
    def __init__(self, app, parseo):
        self.app = app
        self.google = GoogleSimulado()
        self.gestor = app.state.gestor_correo  # el Gestor real sobre PostgreSQL
        self.gmail = ensamblar_gmail(CFG, self.gestor, self.google.cliente())
        self.adaptador = AdaptadorCorreo(self.gmail.api, self.gestor, app.state.broker, app.state.configuracion.correo)
        self.consumidor = ConsumidorCorreo(app.state.broker, parseo, app.state.nodos_correo.filtro)

    async def autorizar(self, titular="t1", buzon="ana@gmail.com"):
        """El consentimiento completo: iniciar, que Google vuelva con el código, y canjearlo."""
        self.google.emitir_codigo(f"codigo-{titular}", buzon)
        estado = parse_qs(urlsplit(self.gmail.oauth.iniciar_autorizacion(titular)).query)["state"][0]
        await self.gmail.oauth.completar_autorizacion(f"codigo-{titular}", estado)

    async def sondear_y_procesar(self, titular="t1"):
        await self.adaptador.sondear(titular)
        while await self.consumidor.procesar_uno() is not ResultadoEntrega.VACIA:
            pass
        while await self.app.state.nodos_correo.ingesta.procesar_uno() is not ResultadoEntrega.VACIA:
            pass

    def reservas(self, titular="t1"):
        repo = self.app.state.repositorio
        return repo.reservas_de([v.id for v in repo.listar_viajes(titular, "activo")])


@pytest.fixture
async def sistema(bases_limpias):
    app = create_app(Configuracion(bases=bases_limpias))
    parseo = ClienteParseo()
    sis = Sistema(app, parseo)
    try:
        await app.state.servicio_revision.aprobar("t1", AGENCIA)  # remitente seguro
        yield sis
    finally:
        await parseo.cerrar()
        await sis.gmail.cerrar()


async def test_AC_COMP_04_03_los_mensajes_del_buzon_llegan_como_reservas_del_itinerario(sistema):
    await sistema.autorizar()
    sistema.google.agregar("ana@gmail.com", mensaje("m1", cuerpo=reserva_json("Roma", "H-1"), message_id="<1@x>"))
    await sistema.sondear_y_procesar()
    [reserva] = sistema.reservas()
    assert (reserva.identificador, reserva.lugar, reserva.codigo) == ("t1:<1@x>", "Roma", "H-1")


async def test_el_correo_html_con_adjuntos_tambien_termina_en_el_itinerario(sistema):
    await sistema.autorizar()
    multipart = {"mimeType": "multipart/mixed", "filename": "", "body": {"size": 0}, "parts": [
        parte("text/html", f"<html><body><p>{reserva_json('Lima', 'H-9')}</p></body></html>"), adjunto()]}
    sistema.google.agregar("ana@gmail.com", mensaje("m1", payload=multipart, message_id="<h@x>"))
    await sistema.sondear_y_procesar()
    assert [(r.lugar, r.codigo) for r in sistema.reservas()] == [("Lima", "H-9")]


async def test_AC_COMP_04_08_dos_sondeos_de_un_mensaje_sin_message_id_no_duplican_la_reserva(sistema):
    await sistema.autorizar()
    sistema.google.agregar("ana@gmail.com", mensaje("m1", cuerpo=reserva_json("Roma", "H-1"), message_id=None))
    for _ in range(2):
        await sistema.sondear_y_procesar()
    [reserva] = sistema.reservas()
    assert reserva.identificador.startswith("t1:") and len(reserva.identificador) == len("t1:") + 64  # SHA-256


async def test_AC_COMP_04_07_el_token_no_figura_en_claro_en_logs_ni_en_la_base(sistema, caplog):
    caplog.set_level(logging.DEBUG)
    await sistema.autorizar()
    sistema.google.agregar("ana@gmail.com", mensaje("m1", cuerpo=reserva_json()))
    await sistema.sondear_y_procesar()
    base = sistema.app.state.base_viajes
    fila = base.leer(lambda c: c.execute("SELECT token_cifrado FROM token_correo WHERE titular_id = 't1'").fetchone())
    assert TOKEN.encode() not in bytes(fila[0])
    assert sistema.gestor.token_vigente("t1") == TOKEN  # pero el Gestor sí lo recupera
    assert TOKEN not in caplog.text and CFG.client_secret not in caplog.text


async def test_revocar_conserva_la_reserva_ya_incorporada(sistema):
    await sistema.autorizar()
    sistema.google.agregar("ana@gmail.com", mensaje("m1", cuerpo=reserva_json()))
    await sistema.sondear_y_procesar()
    sistema.gestor.revocar("t1")
    await sistema.sondear_y_procesar()  # sin token no lee
    assert len(sistema.reservas()) == 1
    assert sistema.google.llamadas("/messages") != [] and len(sistema.google.llamadas("/messages")) == 2  # lista + detalle, una vez


def test_la_app_usa_el_correo_simulado_sin_credenciales_y_gmail_con_ellas(bases_limpias):
    sin = create_app(Configuracion(bases=bases_limpias))
    assert sin.state.gmail is None and "/correo/oauth/iniciar" not in sin.openapi()["paths"]
    con = create_app(Configuracion(bases=bases_limpias, gmail=replace(CFG)))
    assert con.state.gmail is not None
    assert {"/correo/oauth/iniciar", "/correo/oauth/callback", "/correo/autorizacion"} <= set(con.openapi()["paths"])
    assert con.state.api_correo is con.state.gmail.api
    solo_id = create_app(Configuracion(bases=bases_limpias, gmail=replace(CFG, client_secret="")))
    assert solo_id.state.gmail is None  # con una sola credencial tampoco se activa
