"""Google simulado para los tests de SPEC-COMP-04: OAuth y Gmail sobre `httpx.MockTransport`.

Las respuestas siguen la forma documentada de `users.messages.list/get` (formato `full`)."""
from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs

import httpx

from trotamundos.config import ConfiguracionGmail
from trotamundos.entrada.gmail import ApiGmail, ServicioOAuth

CFG = ConfiguracionGmail(client_id="cid-prueba", client_secret="secreto-de-prueba",
                         redireccion_oauth="http://localhost:8000/correo/oauth/callback",
                         cota_llamada_gmail_segundos=1.0)
TOKEN = "ya29.token-de-prueba-0123456789"


def _b64(texto: str, codec: str = "utf-8") -> str:
    return base64.urlsafe_b64encode(texto.encode(codec)).decode().rstrip("=")


def _cabeceras(**kv) -> list[dict]:
    return [{"name": k.replace("_", "-"), "value": v} for k, v in kv.items() if v is not None]


def parte(tipo: str, texto: str, charset: str = "utf-8") -> dict:
    return {"mimeType": tipo, "filename": "", "headers": [{"name": "Content-Type", "value": f'{tipo}; charset="{charset}"'}],
            "body": {"size": len(texto), "data": _b64(texto, charset)}}


def adjunto(nombre: str = "voucher.pdf") -> dict:
    return {"mimeType": "application/pdf", "filename": nombre,
            "headers": [{"name": "Content-Type", "value": "application/pdf"}],
            "body": {"attachmentId": "ANGjdJ8-adjunto-largo", "size": 48213}}


def mensaje(identificador: str, *, cuerpo: str = "hola", remitente: str = "Agencia <agencia@x.com>",
            message_id: str | None = "<m1@x.com>", recibido: datetime | None = None, payload: dict | None = None) -> dict:
    recibido = recibido or datetime.now(UTC) - timedelta(hours=1)
    cabeceras = _cabeceras(From=remitente, Subject="Su reserva", Message_ID=message_id)
    base = payload or parte("text/plain", cuerpo)
    return {"id": identificador, "threadId": identificador, "internalDate": str(int(recibido.timestamp() * 1000)),
            "payload": {**base, "headers": cabeceras + base.get("headers", [])}}


class GoogleSimulado:
    """Los endpoints de Google. Registra cada pedido para que los tests inspeccionen qué viajó y dónde."""

    def __init__(self) -> None:
        self.tokens: dict[str, str] = {}  # token vigente -> buzón
        self.buzones: dict[str, list[dict]] = {}
        self.codigos: dict[str, str] = {}  # código de autorización -> token (un solo uso)
        self.pedidos: list[httpx.Request] = []
        self.estado_lista: int | None = None  # fuerza el HTTP de la lista (401, 500...)
        self.estado_revocacion: int | None = None
        self.demora_segundos = 0.0
        self.tamano_pagina: int | None = None
        self.revocados: list[str] = []

    # --- armado ---------------------------------------------------------------------
    def dar_token(self, buzon: str, token: str = TOKEN) -> str:
        self.tokens[token] = buzon
        return token

    def agregar(self, buzon: str, *mensajes: dict) -> None:
        self.buzones.setdefault(buzon, []).extend(mensajes)

    def emitir_codigo(self, codigo: str, buzon: str, token: str = TOKEN) -> None:
        self.dar_token(buzon, token)
        self.codigos[codigo] = token

    def llamadas(self, fragmento: str) -> list[httpx.Request]:
        return [p for p in self.pedidos if fragmento in p.url.path]

    # --- transporte -------------------------------------------------------------------
    def cliente(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self._manejar))

    async def _manejar(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        if self.demora_segundos:
            await asyncio.sleep(self.demora_segundos)
        ruta = pedido.url.path
        if ruta.endswith("/token"):
            return self._canjear(pedido)
        if ruta.endswith("/revoke"):
            return self._revocar(pedido)
        return self._gmail(pedido, ruta)

    def _canjear(self, pedido: httpx.Request) -> httpx.Response:
        datos = {k: v[0] for k, v in parse_qs(pedido.content.decode()).items()}
        if datos.get("client_secret") != CFG.client_secret or datos.get("grant_type") != "authorization_code":
            return httpx.Response(401, json={"error": "invalid_client"})
        token = self.codigos.pop(datos.get("code", ""), None)  # un código se usa una vez
        if token is None:
            return httpx.Response(400, json={"error": "invalid_grant"})
        return httpx.Response(200, json={"access_token": token, "expires_in": 3599, "token_type": "Bearer",
                                         "scope": "https://www.googleapis.com/auth/gmail.readonly"})

    def _revocar(self, pedido: httpx.Request) -> httpx.Response:
        if self.estado_revocacion:
            return httpx.Response(self.estado_revocacion)
        token = parse_qs(pedido.content.decode()).get("token", [""])[0]
        self.tokens.pop(token, None)
        self.revocados.append(token)
        return httpx.Response(200)

    def _gmail(self, pedido: httpx.Request, ruta: str) -> httpx.Response:
        autorizacion = pedido.headers.get("authorization", "")
        buzon = self.tokens.get(autorizacion.removeprefix("Bearer "))
        if self.estado_lista and ruta.endswith("/messages"):
            return httpx.Response(self.estado_lista, json={"error": {"code": self.estado_lista}})
        if buzon is None:
            return httpx.Response(401, json={"error": {"code": 401, "status": "UNAUTHENTICATED"}})
        mensajes = self.buzones.get(buzon, [])
        if ruta.endswith("/messages"):
            parametros = {k: v[0] for k, v in parse_qs(pedido.url.query.decode()).items()}
            despues = int(parametros.get("q", "after:0").removeprefix("after:")) * 1000
            vigentes = [m for m in mensajes if int(m["internalDate"]) >= despues - 86_400_000]  # `after:` es por día
            tamano = min(int(parametros.get("maxResults", 100)), self.tamano_pagina or 10_000)
            inicio = int(parametros.get("pageToken", 0))
            pagina = vigentes[inicio: inicio + tamano]
            cuerpo: dict = {"resultSizeEstimate": len(vigentes)}
            if pagina:
                cuerpo["messages"] = [{"id": m["id"], "threadId": m["threadId"]} for m in pagina]
            if inicio + tamano < len(vigentes):
                cuerpo["nextPageToken"] = str(inicio + tamano)
            return httpx.Response(200, json=cuerpo)
        for m in mensajes:
            if ruta.endswith("/messages/" + m["id"]):
                return httpx.Response(200, json=m)
        return httpx.Response(404, json={"error": {"code": 404}})


def api_con(google: GoogleSimulado, **cambios) -> ApiGmail:
    from dataclasses import replace

    return ApiGmail(google.cliente(), replace(CFG, **cambios))


def oauth_con(google: GoogleSimulado, gestor, reloj=None) -> ServicioOAuth:
    return ServicioOAuth(gestor, google.cliente(), CFG, **({"reloj": reloj} if reloj else {}))
