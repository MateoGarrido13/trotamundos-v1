# SPEC: SPEC-COMP-04 | PLAN-COMP-04 T-COMP-04-04
import logging
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI

from tests.comp04_util import CFG, TOKEN, GoogleSimulado, oauth_con
from trotamundos.config import ConfiguracionCorreo
from trotamundos.entrada.gestor_autorizacion import CifradorTokens, GestorAutorizacion, RepositorioTokensEnMemoria
from trotamundos.entrada.gmail import AutorizacionRechazada
from trotamundos.entrada.gmail import crear_router as crear_router_oauth


class Reloj:
    def __init__(self):
        self.ahora = 100.0

    def __call__(self):
        return self.ahora


@pytest.fixture
def entorno():
    google, repo = GoogleSimulado(), RepositorioTokensEnMemoria()
    gestor = GestorAutorizacion(repo, CifradorTokens(Fernet.generate_key()), ConfiguracionCorreo())
    reloj = Reloj()
    return google, gestor, oauth_con(google, gestor, reloj), reloj, repo


def parametros(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


def test_AC_COMP_04_01_la_url_de_consentimiento_pide_solo_lectura_con_state(entorno):
    _, _, oauth, _, _ = entorno
    url = oauth.iniciar_autorizacion("ana")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    p = parametros(url)
    assert p["scope"] == "https://www.googleapis.com/auth/gmail.readonly"  # solo ese alcance
    assert p["response_type"] == "code" and p["access_type"] == "online"  # sin token de renovación
    assert p["client_id"] == CFG.client_id and p["redirect_uri"] == CFG.redireccion_oauth
    assert len(p["state"]) >= 32 and "secret" not in url
    assert parametros(oauth.iniciar_autorizacion("ana"))["state"] != p["state"]  # cada vez uno nuevo


async def test_completar_guarda_el_token_cifrado_para_el_titular_que_inicio(entorno):
    google, gestor, oauth, _, repo = entorno
    google.emitir_codigo("codigo-1", "ana")
    estado = parametros(oauth.iniciar_autorizacion("ana"))["state"]
    titular, vence = await oauth.completar_autorizacion("codigo-1", estado)
    assert titular == "ana" and gestor.token_vigente("ana") == TOKEN
    assert TOKEN.encode() not in repo.obtener("ana").token_cifrado  # cifrado en el almacén
    canje = google.llamadas("/token")[0]
    assert "redirect_uri" in canje.content.decode() and "authorization_code" in canje.content.decode()


async def test_AC_COMP_04_02_un_state_usado_se_rechaza_y_no_guarda_token(entorno):
    google, gestor, oauth, _, _ = entorno
    google.emitir_codigo("c1", "ana")
    estado = parametros(oauth.iniciar_autorizacion("ana"))["state"]
    await oauth.completar_autorizacion("c1", estado)
    gestor.revocar("ana")  # el titular vuelve a empezar y alguien repite la vuelta de Google
    google.emitir_codigo("c2", "ana")
    with pytest.raises(AutorizacionRechazada):
        await oauth.completar_autorizacion("c2", estado)
    assert gestor.token_vigente("ana") is None
    assert len(google.llamadas("/token")) == 1  # ni siquiera se canjeó el segundo código


async def test_un_state_inventado_o_vencido_se_rechaza_sin_llamar_a_google(entorno):
    google, gestor, oauth, reloj, _ = entorno
    with pytest.raises(AutorizacionRechazada):
        await oauth.completar_autorizacion("c", "state-inventado")
    estado = parametros(oauth.iniciar_autorizacion("ana"))["state"]
    reloj.ahora += CFG.vigencia_state_segundos + 1
    with pytest.raises(AutorizacionRechazada):
        await oauth.completar_autorizacion("c", estado)
    assert google.pedidos == [] and gestor.token_vigente("ana") is None


async def test_un_codigo_que_google_rechaza_no_guarda_token(entorno):
    google, gestor, oauth, _, _ = entorno
    with pytest.raises(AutorizacionRechazada):
        await oauth.completar_autorizacion("codigo-que-no-existe", parametros(oauth.iniciar_autorizacion("ana"))["state"])
    assert gestor.token_vigente("ana") is None


async def test_el_secreto_y_el_token_no_aparecen_en_los_logs(entorno, caplog):
    caplog.set_level(logging.DEBUG)
    google, gestor, oauth, _, _ = entorno
    google.emitir_codigo("c1", "ana")
    await oauth.completar_autorizacion("c1", parametros(oauth.iniciar_autorizacion("ana"))["state"])
    await oauth.revocar_en_google("ana", TOKEN)
    assert TOKEN not in caplog.text and CFG.client_secret not in caplog.text
    assert CFG.client_secret not in repr(CFG)
    assert TOKEN not in str(google.llamadas("/revoke")[0].url)  # va en el cuerpo, no en la URL


@pytest.fixture
def cliente_web(entorno):
    _, _, oauth, _, _ = entorno
    app = FastAPI()
    app.include_router(crear_router_oauth(oauth))
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


async def test_las_rutas_inician_y_completan_la_autorizacion(entorno, cliente_web):
    google, gestor, _, _, _ = entorno
    google.emitir_codigo("c1", "ana")
    r = await cliente_web.post("/correo/oauth/iniciar", headers={"X-Titular-Id": "ana"})
    estado = parametros(r.json()["url"])["state"]
    r = await cliente_web.get("/correo/oauth/callback", params={"code": "c1", "state": estado})
    assert r.status_code == 200 and r.json()["titular_id"] == "ana" and "vence" in r.json()
    assert gestor.token_vigente("ana") == TOKEN


async def test_las_rutas_rechazan_lo_incompleto_sin_detalle(entorno, cliente_web):
    _, gestor, oauth, _, _ = entorno
    assert (await cliente_web.post("/correo/oauth/iniciar")).status_code == 401
    estado = parametros(oauth.iniciar_autorizacion("ana"))["state"]
    assert (await cliente_web.get("/correo/oauth/callback", params={"state": estado, "error": "access_denied"})).status_code == 400
    r = await cliente_web.get("/correo/oauth/callback", params={"code": "c", "state": estado})  # ya no vive
    assert r.status_code == 400 and r.json() == {"detail": "autorización rechazada"}
    assert (await cliente_web.get("/correo/oauth/callback", params={"code": "c", "state": "x"})).status_code == 400
    assert gestor.token_vigente("ana") is None
