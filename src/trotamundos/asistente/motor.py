# SPEC: SPEC-REF-07
# ELEMENTO PASO 5: IMotorConversacional (RONDA_2/ITERACION_1)
# ADRs: ADR-IT6-004, ADR-IT7-004
# DRIVERS: REF-07, QA-PER-05, QA-DIS-02
"""`IMotorConversacional`: abstrae el proveedor de modelo de IA.

`MotorSimulado` interpreta con reglas de palabras clave, sin ningún proveedor real, y permite
inyectar demora, time-out y caída (`CON-02`). Una agencia o un proveedor nuevo es un adaptador más
detrás del mismo `Protocol`."""
from __future__ import annotations

import asyncio
import re
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from trotamundos.asistente.intenciones import FUERA_DE_ALCANCE, Intencion, TipoIntencion


class ErrorMotor(Exception):
    """El proveedor de modelo no respondió o falló."""


@dataclass(frozen=True)
class ContextoMotor:
    mensajes: tuple[str, ...] = ()  # los últimos mensajes aceptados por el filtro
    reservas: tuple[dict, ...] = ()  # identificador, tipo y lugar de las reservas del itinerario


class IMotorConversacional(Protocol):
    async def interpretar(self, mensaje: str, contexto: ContextoMotor) -> Any:
        """Devuelve una intención de un conjunto cerrado (cualquier otra cosa es `fueraDeAlcance`)."""
        ...


def _plano(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")


FECHA = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?")
TIPOS = ("hotel", "auto", "vuelo", "tren", "autobus", "actividad")
CASO_COMPLEJO = ("reembols", "disputa", "penalidad", "cobraron de mas", "cobro de mas", "escalar",
                 "hablar con la agencia", "proveedor no responde", "proveedor caido", "se cayo el proveedor",
                 "me cancelaron")
REPROGRAMAR = ("reprogram", "cambiar la fecha", "cambiar fecha", "mover", "postergar", "adelantar")
ELIMINAR = ("eliminar", "borrar", "dar de baja", "anular")
ESTADO = ("estado", "novedad", "como esta", "que paso", "mis reservas")
AGREGAR = ("agregar", "anotar", "sumar", "registrar", "cargar")


class MotorSimulado:
    def __init__(self, *, dormir: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self._dormir = dormir
        self.demora_segundos = 0.0
        self.caida = False
        self.respuestas: list[Any] = []  # si hay, se devuelven en orden en lugar de las reglas
        self.llamadas = 0

    async def interpretar(self, mensaje: str, contexto: ContextoMotor) -> Any:
        self.llamadas += 1
        if self.demora_segundos:
            await self._dormir(self.demora_segundos)
        if self.caida:
            raise ErrorMotor("el proveedor de modelo no responde")
        if self.respuestas:
            return self.respuestas.pop(0)
        return self._reglas(mensaje, contexto)

    def _reglas(self, mensaje: str, contexto: ContextoMotor) -> Intencion:
        t = _plano(mensaje)
        ref = self._referencia(t, contexto)
        if any(p in t for p in CASO_COMPLEJO):
            return Intencion(tipo=TipoIntencion.CASO_COMPLEJO, referencia=ref, motivo=mensaje)
        if any(p in t for p in REPROGRAMAR):
            fechas = FECHA.findall(mensaje)
            cambios = {}
            if fechas:
                cambios["inicio"] = fechas[0]
            if len(fechas) > 1:
                cambios["fin"] = fechas[1]
            return Intencion(tipo=TipoIntencion.REPROGRAMAR, referencia=ref, cambios=cambios)
        if any(p in t for p in ELIMINAR):
            return Intencion(tipo=TipoIntencion.ELIMINAR_RESERVA, referencia=ref)
        if any(p in t for p in ESTADO):
            return Intencion(tipo=TipoIntencion.CONSULTAR_ESTADO, referencia=ref)
        if any(p in t for p in AGREGAR):
            fechas = FECHA.findall(mensaje)
            lugar = re.search(r"\ben ([A-Za-zÁÉÍÓÚáéíóúñÑ ]+?)(?= el | del | desde | hasta |\d|$)", mensaje)
            datos: dict[str, Any] = {"tipo": next((x for x in TIPOS if x in t), "actividad")}
            if lugar:
                datos["lugar"] = lugar.group(1).strip()
            if fechas:
                datos["inicio"] = fechas[0]
                datos["fin"] = fechas[1] if len(fechas) > 1 else fechas[0]
            return Intencion(tipo=TipoIntencion.AGREGAR_RESERVA, datos=datos)
        return FUERA_DE_ALCANCE

    @staticmethod
    def _referencia(texto_plano: str, contexto: ContextoMotor) -> str | None:
        for r in contexto.reservas:
            if _plano(str(r.get("identificador", ""))) in texto_plano and r.get("identificador"):
                return r["identificador"]
        for r in contexto.reservas:
            lugar = _plano(str(r.get("lugar") or ""))
            if lugar and lugar in texto_plano:
                return r["lugar"]
        for tipo in TIPOS:
            if tipo in texto_plano and any(r.get("tipo") == tipo for r in contexto.reservas):
                return tipo
        return None
