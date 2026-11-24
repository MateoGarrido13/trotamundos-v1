# SPEC: SPEC-COMP-04
# ELEMENTO PASO 5: Adaptador de correo, API de correo externa (Gmail) (ITERACION_3)
# ADRs: ADR-007, ADR-IT3-003, ADR-IT3-006, ADR-IT2-003
# DRIVERS: REF-02, QA-SEG-03*, CON-02
"""`ApiGmail`: implementación real del puerto `ApiCorreo` contra la Gmail API.

El token viaja **solo** en el encabezado `Authorization` y nunca se escribe en un log. Cada llamada
tiene una cota; al vencer es `ErrorApiCorreo` y no se reintenta (regla 9). Un 401 es `TokenInvalido`."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import httpx

from trotamundos.config import ConfiguracionGmail
from trotamundos.entrada.api_correo import CorreoCrudo, ErrorApiCorreo, TokenInvalido
from trotamundos.entrada.gmail.mensajes import MensajeInvalido, a_correo_crudo

log = logging.getLogger(__name__)

ClienteHttp = httpx.AsyncClient  # alias para que la composición no importe httpx

PARALELISMO = 10  # detalles de mensajes pedidos a la vez
TAMANO_PAGINA = 100


def crear_cliente_http() -> httpx.AsyncClient:
    """El cliente HTTP de la app. Lo crea y lo cierra la composición."""
    return httpx.AsyncClient()


class ApiGmail:
    def __init__(self, cliente: httpx.AsyncClient, configuracion: ConfiguracionGmail | None = None) -> None:
        self._cliente = cliente
        self._cfg = configuracion or ConfiguracionGmail()

    async def _get(self, token: str, ruta: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            # `httpx` acota cada fase de la conexión; `wait_for` acota la llamada entera (regla 9).
            respuesta = await asyncio.wait_for(
                self._cliente.get(f"{self._cfg.url_api}{ruta}", params=params,
                                  headers={"Authorization": f"Bearer {token}"},
                                  timeout=self._cfg.cota_llamada_gmail_segundos),
                self._cfg.cota_llamada_gmail_segundos)
        except (httpx.TimeoutException, TimeoutError):
            raise ErrorApiCorreo("la API de Gmail no respondió dentro de la cota") from None
        except httpx.HTTPError:
            raise ErrorApiCorreo("falló la conexión con la API de Gmail") from None
        if respuesta.status_code == 401:
            raise TokenInvalido("Gmail rechazó el token")
        if respuesta.status_code != 200:
            raise ErrorApiCorreo(f"Gmail respondió {respuesta.status_code}")
        try:
            cuerpo = respuesta.json()
        except ValueError:
            raise ErrorApiCorreo("Gmail respondió algo que no es JSON") from None
        if not isinstance(cuerpo, dict):
            raise ErrorApiCorreo("Gmail respondió algo inesperado")
        return cuerpo

    async def _listar(self, token: str, desde: datetime) -> list[str]:
        """Los identificadores de la ventana, de a páginas, hasta el tope por sondeo (regla 4)."""
        ids: list[str] = []
        pagina: str | None = None
        while len(ids) < self._cfg.max_mensajes_por_sondeo:
            params: dict[str, Any] = {
                "q": f"after:{int(desde.timestamp())}",
                "maxResults": min(TAMANO_PAGINA, self._cfg.max_mensajes_por_sondeo - len(ids))}
            if pagina:
                params["pageToken"] = pagina
            cuerpo = await self._get(token, "/users/me/messages", params)
            ids.extend(m["id"] for m in cuerpo.get("messages", []) if isinstance(m, dict) and "id" in m)
            pagina = cuerpo.get("nextPageToken")
            if not pagina:
                break
        return ids[: self._cfg.max_mensajes_por_sondeo]

    async def leer_mensajes(self, token: str, desde: datetime) -> list[CorreoCrudo]:
        ids = await self._listar(token, desde)
        cupo = asyncio.Semaphore(PARALELISMO)

        async def detalle(identificador: str) -> dict[str, Any]:
            async with cupo:
                return await self._get(token, f"/users/me/messages/{identificador}", {"format": "full"})

        resultados = await asyncio.gather(*(detalle(i) for i in ids), return_exceptions=True)
        for resultado in resultados:  # el rechazo del token manda sobre cualquier otro fallo
            if isinstance(resultado, TokenInvalido):
                raise resultado
        for resultado in resultados:
            if isinstance(resultado, BaseException):
                raise resultado
        correos: list[CorreoCrudo] = []
        for mensaje in resultados:
            try:
                correo = a_correo_crudo(mensaje)
            except MensajeInvalido as error:
                log.warning("mensaje de Gmail descartado: %s", error)
                continue
            if correo.recibido >= desde:  # `after:` tiene resolución de día
                correos.append(correo)
        return sorted(correos, key=lambda c: c.recibido)
