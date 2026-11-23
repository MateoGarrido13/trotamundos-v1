# SPEC: SPEC-REF-05
# ELEMENTO PASO 5: IAgencia, Adaptador de agencia, cola de casos de ayuda (ITERACION_4)
# ADRs: ADR-IT4-010
# DRIVERS: REF-05, CON-02
"""Contrato de las agencias de viajes y estados del caso de ayuda.

`IAgencia` extiende `IProveedor` con `abrirCaso(caso)` y `consultarCaso(idCaso)`. Una agencia
nueva es un adaptador más detrás de `IAgencia`, sin tocar al Orquestador (`CON-02`)."""
from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel


class EstadoCaso(StrEnum):
    EN_TRAMITE = "en_tramite"  # el Orquestador guardó el caso; puede estar en camino a la agencia
    ABIERTO = "abierto"  # la agencia recibió y abrió el caso
    EN_CURSO = "en_curso"  # la agencia está trabajando en el caso
    RESUELTO = "resuelto"  # final: no se reabre en el prototipo
    SIN_ENTREGAR = "sin_entregar"  # no se pudo entregar el pedido; se puede reintentar


_AVANCE = [EstadoCaso.EN_TRAMITE, EstadoCaso.ABIERTO, EstadoCaso.EN_CURSO, EstadoCaso.RESUELTO]


def puede_pasar(actual: EstadoCaso, nuevo: EstadoCaso) -> bool:
    """Los estados solo avanzan. «Sin entregar» solo se alcanza desde «en trámite» y solo se
    sale reintentando (lo hace el Orquestador, no una novedad). Una novedad que retrocede, que
    repite el estado o que llega sobre un caso «sin entregar» o «resuelto» se ignora."""
    if actual in (EstadoCaso.SIN_ENTREGAR, EstadoCaso.RESUELTO):
        return False
    if nuevo is EstadoCaso.SIN_ENTREGAR:
        return actual is EstadoCaso.EN_TRAMITE
    return _AVANCE.index(nuevo) > _AVANCE.index(actual)


class PedidoCaso(BaseModel):
    """Lo que viaja a la agencia: solo lo que el viajero consintió (la reserva afectada, la
    descripción del problema y, si lo trae el asistente, el resumen del diálogo)."""

    id_caso: str
    agencia: str
    reserva: dict
    descripcion: str
    resumen_dialogo: str | None = None


class IProveedor(Protocol):
    nombre: str


class IAgencia(IProveedor, Protocol):
    async def abrir_caso(self, pedido: PedidoCaso) -> None: ...

    async def consultar_caso(self, id_caso: str) -> EstadoCaso | None:
        """El estado que informa la agencia, o `None` si no conoce el caso."""
        ...
