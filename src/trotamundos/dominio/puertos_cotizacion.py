# SPEC: SPEC-COMP-06
# ELEMENTO PASO 5: IProveedor, ICotizadorHotel, IProveedorInventario, IProveedorArrendadora (ITERACION_2 y 3)
# ADRs: ADR-IT3-004, ADR-IT2-003, ADR-007
# DRIVERS: QA-INT-01, QA-PER-02
"""Contratos de la cotización. Los puertos solo dependen del dominio."""
from __future__ import annotations

from typing import Any, Protocol

from trotamundos.dominio.cotizacion import Criterios, Grilla, Precio, ProgresoGrilla, ResultadoOrigen


class NodoCaido(Exception):
    """El nodo dejó de responder con un pedido en vuelo (el Balanceador lo reenvía)."""


class SinNodosDisponibles(Exception):
    """Ningún nodo sano puede atender el pedido."""


class IProveedor(Protocol):
    """El contrato común de todo proveedor (`ADR-IT3-004`). `recibir_novedad` es de SPEC-COMP-07 (PLAN-COMP-07,
    D13): el aviso de un proveedor que anuncia algo. Los adaptadores de cotización no reciben avisos."""

    nombre: str

    async def ping(self) -> bool: ...

    def traducir(self, mensaje: Any) -> Any: ...

    async def recibir_novedad(self, mensaje: Any) -> Any: ...


class ICotizador(Protocol):
    """Lo único que el Orquestador conoce de un adaptador de cotización."""

    nombre: str

    async def cotizar(self, criterios: Criterios) -> ResultadoOrigen: ...


class ICotizadorHotel(IProveedor, ICotizador, Protocol):
    pass


class IProveedorInventario(IProveedor, ICotizador, Protocol):
    """Aerolíneas."""


class IProveedorArrendadora(IProveedor, ICotizador, Protocol):
    pass


class INodo(Protocol):
    nombre: str

    async def eco(self) -> bool: ...

    async def atender(self, criterios: Criterios, progreso: ProgresoGrilla) -> Grilla: ...


class IDespachador(Protocol):
    """Lo que la Caché de borde conoce del API Gateway y del Balanceador."""

    async def despachar(self, criterios: Criterios, progreso: ProgresoGrilla) -> Grilla: ...
