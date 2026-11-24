# SPEC: SPEC-COMP-04 | PLAN-COMP-04 T-COMP-04-05
from datetime import UTC, datetime

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI

from tests.comp04_util import CFG, TOKEN, GoogleSimulado, api_con, mensaje, oauth_con
from tests.test_ref02_adaptador import _vaciar
from trotamundos.broker import Broker
from trotamundos.config import ConfiguracionBroker, ConfiguracionCorreo
from trotamundos.entrada import app as app_entrada
from trotamundos.entrada.adaptador_correo import AdaptadorCorreo
from trotamundos.entrada.api_correo import ErrorApiCorreo, TokenInvalido
from trotamundos.entrada.gestor_autorizacion import CifradorTokens, GestorAutorizacion, RepositorioTokensEnMemoria
from trotamundos.entrada.programador_sondeo import ProgramadorSondeo


class Entorno:
    """El sondeo real sobre Gmail simulado, con los nodos de entrada montados como en la app."""

    def __init__(self):
        self.google = GoogleSimulado()
        self.cfg = ConfiguracionCorreo()
        self.gestor = GestorAutorizacion(RepositorioTokensEnMemoria(), CifradorTokens(Fernet.generate_key()), self.cfg)
        self.broker = Broker(ConfiguracionBroker(tamano_maximo_cola=100))
        self.api = api_con(self.google)
        self.sondeo = ProgramadorSondeo(AdaptadorCorreo(self.api, self.gestor, self.broker, self.cfg), self.gestor, self.cfg)
        self.oauth = oauth_con(self.google, self.gestor)
        app = FastAPI()
        app.include_router(app_entrada.crear_router(self.gestor, al_revocar=self.oauth.revocar_en_google))
        self.web = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")

    def titular(self, titular: str, *mensajes: dict, token: str | None = None) -> str:
        token = token or f"tok-{titular}"
        self.google.dar_token(titular, token)
        self.google.agregar(titular, *mensajes)
        self.gestor.autorizar(titular, token)
        return token


@pytest.fixture
def e():
    return Entorno()


async def test_AC_COMP_04_04_un_401_deja_al_titular_sin_lectura_hasta_autorizar_de_nuevo(e):
    e.titular("ana", mensaje("m1"))
    e.google.tokens.clear()  # Google ya no reconoce el token
    resultado = await e.sondeo.tick()
    assert isinstance(resultado["ana"], TokenInvalido)
    assert e.gestor.token_vigente("ana") is None and e.gestor.titulares_autorizados() == []
    lecturas = len(e.google.pedidos)
    assert await e.sondeo.tick() == {}  # sin token no se vuelve a llamar a Gmail
    assert len(e.google.pedidos) == lecturas
    # El titular autoriza de nuevo y vuelve a leerse.
    e.titular("ana", token="tok-nuevo")
    assert (await e.sondeo.tick())["ana"].leyo


async def test_AC_COMP_04_05_gmail_caido_falla_solo_ese_titular(e):
    e.titular("ana", mensaje("m1"))
    e.titular("luis", mensaje("m2", message_id="<2@x>"))
    original = e.google._gmail

    def cae_para_ana(pedido, ruta):
        if pedido.headers["authorization"] == "Bearer tok-ana":
            return httpx.Response(500)
        return original(pedido, ruta)

    e.google._gmail = cae_para_ana
    resultado = await e.sondeo.tick()
    assert isinstance(resultado["ana"], ErrorApiCorreo) and not isinstance(resultado["ana"], TokenInvalido)
    assert resultado["luis"].leyo and resultado["luis"].publicados == 1
    assert e.gestor.token_vigente("ana") == "tok-ana"  # un fallo de Gmail no revoca: se reintenta en el sondeo siguiente
    assert [m.id for m in await _vaciar(e.broker)] == ["<2@x>"]


async def test_AC_COMP_04_06_revocar_no_llama_a_gmail_y_borra_el_token(e):
    token = e.titular("ana", mensaje("m1"))
    assert (await e.sondeo.tick())["ana"].publicados == 1
    antes = len(e.google.pedidos)
    r = await e.web.delete("/correo/autorizacion", headers={"X-Titular-Id": "ana"})
    assert r.status_code == 204
    assert e.gestor.token_vigente("ana") is None and e.gestor.titulares_autorizados() == []
    assert e.google.revocados == [token]  # y Google también lo revocó
    llamadas = len(e.google.pedidos)
    assert llamadas == antes + 1  # solo la revocación
    assert await e.sondeo.tick() == {}
    assert len(e.google.pedidos) == llamadas  # el sondeo no tocó a Gmail


async def test_si_google_no_responde_al_revocar_el_token_local_igual_se_borra(e):
    e.titular("ana", mensaje("m1"))
    e.google.estado_revocacion = 500
    assert (await e.web.delete("/correo/autorizacion", headers={"X-Titular-Id": "ana"})).status_code == 204
    assert e.gestor.token_vigente("ana") is None
    e.titular("luis")
    e.google.demora_segundos = 5  # Google no contesta dentro de la cota
    from dataclasses import replace

    e.oauth = type(e.oauth)(e.gestor, e.google.cliente(), replace(CFG, cota_llamada_gmail_segundos=0.1))
    await e.oauth.revocar_en_google("luis", "tok-luis")  # no lanza


async def test_revocar_sin_gmail_funciona_como_antes():
    gestor = GestorAutorizacion(RepositorioTokensEnMemoria(), CifradorTokens(Fernet.generate_key()))
    gestor.autorizar("ana", "tok")
    app = FastAPI()
    app.include_router(app_entrada.crear_router(gestor))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.delete("/correo/autorizacion", headers={"X-Titular-Id": "ana"})).status_code == 204
        assert (await c.delete("/correo/autorizacion")).status_code == 401
    assert gestor.token_vigente("ana") is None


async def test_sin_token_vigente_el_sondeo_no_llama_a_gmail(e):
    e.titular("ana", mensaje("m1"))
    e.gestor.revocar("ana")
    assert await e.sondeo.tick() == {}
    assert e.google.pedidos == []
