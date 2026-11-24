# SPEC: SPEC-COMP-04
# ELEMENTO PASO 5: Adaptador de correo, capa anti-corrupción de Gmail (ITERACION_3)
# ADRs: ADR-007, ADR-IT3-003, ADR-IT3-007
# DRIVERS: REF-02, CON-02
"""Traduce un mensaje de la Gmail API (`users.messages.get`, formato `full`) al `CorreoCrudo` que ya
espera el Adaptador de correo. Entrega solo texto: prefiere `text/plain`, reduce el HTML a texto y
ignora los adjuntos (regla 6). No hace red."""
from __future__ import annotations

import base64
import re
from datetime import UTC, datetime
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any

from trotamundos.entrada.api_correo import CorreoCrudo


class MensajeInvalido(ValueError):
    """Un mensaje de Gmail al que le falta lo mínimo para traducirlo."""


_BLOQUES = {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol", "blockquote"}
_IGNORADOS = {"script", "style", "head", "title"}


class _HtmlATexto(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._trozos: list[str] = []
        self._ignorando = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _IGNORADOS:
            self._ignorando += 1
        elif tag in _BLOQUES:
            self._trozos.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _IGNORADOS:
            self._ignorando = max(0, self._ignorando - 1)
        elif tag in _BLOQUES:
            self._trozos.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignorando:
            self._trozos.append(data)

    def texto(self) -> str:
        lineas = (re.sub(r"[ \t\r\f\v\xa0]+", " ", linea).strip() for linea in "".join(self._trozos).splitlines())
        return "\n".join(linea for linea in lineas if linea)


def html_a_texto(html: str) -> str:
    conversor = _HtmlATexto()
    conversor.feed(html)
    conversor.close()
    return conversor.texto()


def _cabeceras(parte: dict[str, Any]) -> dict[str, str]:
    return {h.get("name", "").lower(): h.get("value", "") for h in parte.get("headers", [])}


def _decodificar(parte: dict[str, Any]) -> str:
    datos = (parte.get("body") or {}).get("data") or ""
    crudo = base64.urlsafe_b64decode(datos + "=" * (-len(datos) % 4))
    coincidencia = re.search(r"charset=\"?([\w.\-]+)", _cabeceras(parte).get("content-type", ""), re.IGNORECASE)
    try:
        return crudo.decode(coincidencia.group(1) if coincidencia else "utf-8", errors="replace")
    except LookupError:
        return crudo.decode("utf-8", errors="replace")


def _es_adjunto(parte: dict[str, Any]) -> bool:
    return bool(parte.get("filename")) or bool((parte.get("body") or {}).get("attachmentId"))


def _recoger(parte: dict[str, Any], planos: list[str], htmls: list[str]) -> None:
    if _es_adjunto(parte):
        return
    tipo = (parte.get("mimeType") or "").lower()
    if tipo == "text/plain":
        planos.append(_decodificar(parte))
    elif tipo == "text/html":
        htmls.append(_decodificar(parte))
    for hija in parte.get("parts") or []:
        _recoger(hija, planos, htmls)


def texto_del_mensaje(payload: dict[str, Any]) -> str:
    planos: list[str] = []
    htmls: list[str] = []
    _recoger(payload, planos, htmls)
    if planos:
        return "\n".join(p.strip() for p in planos if p.strip())
    return "\n".join(html_a_texto(h) for h in htmls if h.strip())


def _fecha(mensaje: dict[str, Any], cabeceras: dict[str, str]) -> datetime:
    interna = mensaje.get("internalDate")
    if interna is not None:
        try:
            return datetime.fromtimestamp(int(interna) / 1000, UTC)
        except (ValueError, OverflowError, OSError) as error:
            raise MensajeInvalido("internalDate inválido") from error
    try:
        fecha = parsedate_to_datetime(cabeceras["date"])
    except (KeyError, TypeError, ValueError) as error:
        raise MensajeInvalido("el mensaje no trae fecha") from error
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=UTC)


def a_correo_crudo(mensaje: dict[str, Any]) -> CorreoCrudo:
    payload = mensaje.get("payload")
    if not isinstance(payload, dict):
        raise MensajeInvalido("el mensaje no trae `payload`")
    cabeceras = _cabeceras(payload)
    return CorreoCrudo(
        cuerpo=texto_del_mensaje(payload),
        remitente=parseaddr(cabeceras.get("from", ""))[1].lower(),
        recibido=_fecha(mensaje, cabeceras),
        message_id=cabeceras.get("message-id", "").strip() or None,
    )
