# SPEC: SPEC-REF-07
# ELEMENTO PASO 5: Módulo de Asistente Virtual y Orquestador de viajes (RONDA_2/ITERACION_1)
# ADRs: ADR-IT6-001, ADR-IT6-002, ADR-IT6-003
# DRIVERS: REF-07, QA-SEG-02
"""Interfaz interna del Orquestador que usa el Asistente.

El Asistente solo conoce este `Protocol`: no lee ni escribe ninguna base, no llama a la agencia y
no importa al Orquestador. El Orquestador lo implementa en `orquestador/fachada_asistente.py`;
`composicion.py` los ensambla. En el paso 5 esta llamada es la interfaz interna del Orquestador."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ResultadoOrquestador:
    estado: str  # "ok" | "denegado" | "rechazado"
    motivo: str | None = None  # el motivo del rechazo (el contrato de SPEC-REF-04 y SPEC-REF-05)
    datos: dict[str, Any] = field(default_factory=dict)
    repetida: bool = False  # el Orquestador reconoció la clave de operación: no se aplicó dos veces


class OrquestadorInterno(Protocol):
    async def reservas(self, actor: str, itinerario_id: str) -> ResultadoOrquestador:
        """Las reservas vigentes del itinerario (`datos["reservas"]`). Sin permiso de ver: denegado."""
        ...

    async def estado(self, actor: str, itinerario_id: str) -> ResultadoOrquestador:
        """Reservas, novedades pendientes y casos del viajero (`datos`)."""
        ...

    async def agregar_reserva(self, actor: str, itinerario_id: str, clave: str,
                              solicitud: dict[str, Any]) -> ResultadoOrquestador: ...

    async def actualizar_reserva(self, actor: str, itinerario_id: str, reserva_id: str, clave: str,
                                 cambios: dict[str, Any]) -> ResultadoOrquestador: ...

    async def eliminar_reserva(self, actor: str, itinerario_id: str, reserva_id: str,
                               clave: str) -> ResultadoOrquestador: ...

    async def abrir_caso(self, actor: str, itinerario_id: str, clave: str, reserva_id: str,
                         descripcion: str, resumen_dialogo: str | None) -> ResultadoOrquestador: ...

    async def agencia_preferida(self, actor: str) -> dict[str, str | None]:
        """`{"agencia": nombre, "contacto": número}`, o ambos `None` si no eligió una."""
        ...
