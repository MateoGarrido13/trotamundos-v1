# SPEC: SPEC-REF-07
# ELEMENTO PASO 5: Filtrado de inyección de prompt (RONDA_2/ITERACION_2)
# ADRs: ADR-IT7-001
# DRIVERS: REF-07, QA-SEG-04
"""Filtro de inyección de prompt: corre **antes** de `IMotorConversacional`.

Rechaza el mensaje que supera el largo máximo, trae caracteres de control o coincide con un patrón
de inyección: pedidos de ignorar instrucciones, mostrar o cambiar las instrucciones internas,
adoptar otro rol, o marcas que imitan mensajes del sistema (en español y en inglés). Usa reglas
fijas: un mensaje legítimo que coincida recibe el rechazo y el menú, costo que la spec acepta."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from trotamundos.config import ConfiguracionAsistente


def _plano(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")


# Los patrones se aplican sobre el texto en minúsculas y sin tildes.
PATRONES = [re.compile(p) for p in (
    # ignorar o olvidar instrucciones
    r"\b(ignor\w*|ignore|disregard|olvid\w*|forget|descart\w*|omit\w*)\b.{0,40}\b(instruccion\w*|regla\w*|indicacion\w*|"
    r"instructions?|rules?|prompt|guidelines?|restriccion\w*|restrictions?|todo lo anterior|above|previous)\b",
    r"\b(ignora|ignore|olvida|forget|disregard)\b.{0,20}\b(todo|everything|all)\b",
    # mostrar, repetir o cambiar las instrucciones internas
    r"\b(system|sistema)\s*(prompt|message|mensaje)\b",
    r"\bprompt\s+del\s+sistema\b",
    r"\b(muestr\w*|revel\w*|reveal|show|print|repet\w*|repeat|dime|dame|tell me|what (is|are))\b.{0,40}\b(tu|tus|your|el|las|the)?\s*"
    r"(prompt|instrucciones?|instructions?|configuracion|reglas internas|hidden|ocult\w*|internas?|secret\w*|clave)\b",
    r"\b(cambi\w*|modific\w*|change|update|override|reemplaz\w*|replace|new)\b.{0,30}\b(tus|tu|your|las|the)?\s*"
    r"(instrucciones?|instructions?|reglas|rules|system message|mensaje del sistema|prompt)\b",
    r"\bnew instructions?\b",
    r"\bnuevas? instrucciones?\b",
    r"repeat the (words|text) above",
    # adoptar otro rol o salirse de las reglas
    r"\b(ahora\s+)?(eres|sos|seras)\s+(un|una)\b",
    r"\b(actua|actue|haz de|compor\w*|comporta\w*|haz de cuenta)\b.{0,25}\b(como|que eres|de|si)\b",
    r"\b(you are now|from now on|act as|pretend|roleplay|role-play|simulate being|you must now)\b",
    r"\b(jailbreak|dan mode|developer mode|modo desarrollador|modo dios|god mode|sudo|root access|admin access)\b",
    r"\bsin (restricciones|limites|reglas|filtros)\b",
    r"\b(without|no) (restrictions|limits|rules|filters|guardrails)\b",
    r"\b(bypass|saltea\w*|evad\w*|desactiv\w*|disable|turn off|apaga\w*)\b.{0,30}\b(filtro\w*|seguridad|safety|guardrails?|restricciones|protecciones?|rules)\b",
    r"\bguardrails?\b",
    # marcas que imitan mensajes del sistema
    r"\[\s*(system|sistema|admin|assistant|asistente|developer|instruction)\s*\]",
    r"</?\s*(system|sistema|instructions?|prompt|admin)\s*>",
    r"<\|?\s*(system|im_start|im_end)\s*\|?>",
    r"^\s*#{2,}\s*(system|sistema|instruction|instrucc)",
    r"^\s*(system|sistema|admin|assistant)\s*:",
    r"\bbegin\s+(system|prompt)\b",
    r"\b(end|fin)\s+(system|prompt)\b",
)]
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")  # los saltos de línea y tabulaciones sí valen


@dataclass(frozen=True)
class ResultadoFiltro:
    aceptado: bool
    motivo: str | None = None  # "largo" | "control" | "inyeccion"


class FiltroInyeccion:
    def __init__(self, configuracion: ConfiguracionAsistente | None = None) -> None:
        self._cfg = configuracion or ConfiguracionAsistente()

    def revisar(self, mensaje: str) -> ResultadoFiltro:
        if not isinstance(mensaje, str) or not mensaje.strip():
            return ResultadoFiltro(False, "vacio")
        if len(mensaje) > self._cfg.largo_maximo_mensaje:
            return ResultadoFiltro(False, "largo")
        if CONTROL.search(mensaje):
            return ResultadoFiltro(False, "control")
        plano = _plano(mensaje)
        for patron in PATRONES:
            if patron.search(plano):
                return ResultadoFiltro(False, "inyeccion")
        return ResultadoFiltro(True)
