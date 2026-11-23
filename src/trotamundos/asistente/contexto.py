# SPEC: SPEC-REF-07
# ELEMENTO PASO 5: Contexto firmado (RONDA_2/ITERACION_1)
# ADRs: ADR-IT6-001, ADR-IT6-002
# DRIVERS: REF-07
"""Contexto de la conversación. El módulo no guarda nada entre turnos: lo que hay que recordar
viaja en un contexto firmado que el módulo entrega al cliente y el cliente devuelve en cada turno.

Lleva la acción pendiente de confirmación (con su clave de operación), los últimos mensajes
aceptados por el filtro y un vencimiento. Se firma con HMAC-SHA256 con una clave tomada de una
variable de entorno. Si la firma no coincide, si venció o si es de otra cuenta u otro itinerario,
se descarta: no se ejecuta ninguna acción pendiente y la conversación empieza de nuevo."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AccionPendiente:
    tipo: str  # el valor de la intención: reprogramar, eliminarReserva, agregarReserva, casoComplejo
    clave: str  # clave de operación generada cuando el asistente propone la acción
    datos: dict[str, Any]  # reserva_id, cambios, solicitud, motivo (solo valores JSON)
    descripcion: str  # lo que se le mostró al viajero para que confirme


@dataclass
class Contexto:
    actor: str
    itinerario_id: str
    mensajes: list[str] = field(default_factory=list)  # solo los que aceptó el filtro
    pendiente: AccionPendiente | None = None
    vence: float = 0.0


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).decode().rstrip("=")


def _desb64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


class FirmaContexto:
    def __init__(self, clave: str, vigencia_segundos: float = 30 * 60,
                 reloj: Callable[[], float] = time.time) -> None:
        if not clave:
            raise ValueError("Falta la clave que firma el contexto (TROTA_CLAVE_ASISTENTE)")
        self._clave = clave.encode()
        self._vigencia = vigencia_segundos
        self._reloj = reloj

    def nuevo(self, actor: str, itinerario_id: str) -> Contexto:
        return Contexto(actor=actor, itinerario_id=itinerario_id, vence=self._reloj() + self._vigencia)

    def firmar(self, contexto: Contexto) -> str:
        contexto.vence = self._reloj() + self._vigencia  # cada turno renueva la vigencia
        cuerpo = _b64(json.dumps(asdict(contexto), separators=(",", ":"), sort_keys=True).encode())
        return f"{cuerpo}.{_b64(self._mac(cuerpo))}"

    def verificar(self, token: str | None, actor: str, itinerario_id: str) -> Contexto | None:
        """El contexto, o `None` si no hay, la firma no coincide, venció o es de otro actor u otro
        itinerario (un contexto firmado para una cuenta no sirve para otra)."""
        if not token or not isinstance(token, str) or token.count(".") != 1:
            return None
        cuerpo, firma = token.split(".")
        try:
            if not hmac.compare_digest(_desb64(firma), self._mac(cuerpo)):
                return None
            crudo = json.loads(_desb64(cuerpo))
            pendiente = crudo.get("pendiente")
            contexto = Contexto(
                actor=crudo["actor"], itinerario_id=crudo["itinerario_id"],
                mensajes=list(crudo["mensajes"]), vence=float(crudo["vence"]),
                pendiente=AccionPendiente(**pendiente) if pendiente else None)
        except (ValueError, KeyError, TypeError):
            return None
        if contexto.vence < self._reloj():
            return None
        if contexto.actor != actor or contexto.itinerario_id != itinerario_id:
            return None
        return contexto

    def _mac(self, cuerpo: str) -> bytes:
        return hmac.new(self._clave, cuerpo.encode(), hashlib.sha256).digest()
