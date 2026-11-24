# SPEC: SPEC-COMP-04
# ELEMENTO PASO 5: Gestor de autorización del correo, consentimiento con Google (ITERACION_3)
# ADRs: ADR-IT3-006
# DRIVERS: QA-SEG-03*
"""Flujo OAuth con Google sobre el Gestor de autorización: el titular consiente, el código se canjea
por un token de acceso de **solo lectura** y el Gestor lo guarda cifrado. No se pide ni se guarda un
token de renovación: el token vence como fija `REF-02`."""
from __future__ import annotations

import asyncio
import logging
import secrets
import time
from collections.abc import Callable
from datetime import datetime
from urllib.parse import urlencode

import httpx

from trotamundos.config import ConfiguracionGmail
from trotamundos.entrada.gestor_autorizacion import GestorAutorizacion

log = logging.getLogger(__name__)

ALCANCE = "https://www.googleapis.com/auth/gmail.readonly"


class AutorizacionRechazada(Exception):
    """El `state` es inválido, ya se usó o venció, o Google rechazó el código. No se guardó nada."""


class EstadosOAuth:
    """`state` de un solo uso, ligado al titular que inició la autorización y con vencimiento."""

    def __init__(self, vigencia_segundos: float, reloj: Callable[[], float] = time.monotonic) -> None:
        self._vigencia = vigencia_segundos
        self._reloj = reloj
        self._vigentes: dict[str, tuple[str, float]] = {}

    def emitir(self, titular_id: str) -> str:
        ahora = self._reloj()
        self._vigentes = {s: v for s, v in self._vigentes.items() if v[1] > ahora}  # purga los vencidos
        estado = secrets.token_urlsafe(32)
        self._vigentes[estado] = (titular_id, ahora + self._vigencia)
        return estado

    def consumir(self, estado: str) -> str | None:
        """El titular del `state`, o `None` si no existe, ya se usó o venció. Siempre lo gasta."""
        guardado = self._vigentes.pop(estado, None)
        if guardado is None or guardado[1] <= self._reloj():
            return None
        return guardado[0]


class ServicioOAuth:
    def __init__(self, gestor: GestorAutorizacion, cliente: httpx.AsyncClient,
                 configuracion: ConfiguracionGmail, reloj: Callable[[], float] = time.monotonic) -> None:
        self._gestor = gestor
        self._cliente = cliente
        self._cfg = configuracion
        self._estados = EstadosOAuth(configuracion.vigencia_state_segundos, reloj)

    def iniciar_autorizacion(self, titular_id: str) -> str:
        """La URL de consentimiento de Google, con alcance de solo lectura y un `state` de un solo uso."""
        parametros = {
            "client_id": self._cfg.client_id, "redirect_uri": self._cfg.redireccion_oauth,
            "response_type": "code", "scope": ALCANCE, "access_type": "online",
            "state": self._estados.emitir(titular_id)}
        return f"{self._cfg.url_autorizacion}?{urlencode(parametros)}"

    def descartar_estado(self, state: str) -> None:
        """El titular negó el permiso o la vuelta vino incompleta: el `state` no queda vivo."""
        self._estados.consumir(state)

    async def completar_autorizacion(self, code: str, state: str) -> tuple[str, datetime]:
        """Canjea el código y guarda el token cifrado. Devuelve (titular, vencimiento)."""
        titular = self._estados.consumir(state)
        if titular is None:
            raise AutorizacionRechazada("state inválido, usado o vencido")
        try:
            respuesta = await asyncio.wait_for(self._cliente.post(
                self._cfg.url_token, timeout=self._cfg.cota_llamada_gmail_segundos,
                data={"code": code, "client_id": self._cfg.client_id, "client_secret": self._cfg.client_secret,
                      "redirect_uri": self._cfg.redireccion_oauth, "grant_type": "authorization_code"}),
                self._cfg.cota_llamada_gmail_segundos)
            token = respuesta.json().get("access_token") if respuesta.status_code == 200 else None
        except (httpx.HTTPError, TimeoutError, ValueError, AttributeError):
            token = None
        if not token:
            raise AutorizacionRechazada("Google no entregó un token")
        vence = await asyncio.to_thread(self._gestor.autorizar, titular, token)
        return titular, vence

    async def revocar_en_google(self, titular_id: str, token: str) -> None:
        """Mejor esfuerzo: el borrado local ya se hizo antes (regla de `revocar`). El token va en el
        cuerpo del formulario, nunca en la URL."""
        try:
            await asyncio.wait_for(
                self._cliente.post(self._cfg.url_revocacion, data={"token": token},
                                   timeout=self._cfg.cota_llamada_gmail_segundos),
                self._cfg.cota_llamada_gmail_segundos)
        except (httpx.HTTPError, TimeoutError):
            log.warning("Google no confirmó la revocación del acceso de %s; el token local ya se borró", titular_id)
