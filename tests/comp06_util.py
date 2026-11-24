"""Fábricas de la cotización para los tests de SPEC-COMP-06 (sin base ni Broker)."""
from __future__ import annotations

import time
from datetime import date

from trotamundos.composicion import SistemaCotizacion, ensamblar_cotizacion
from trotamundos.config import ConfiguracionCotizacion
from trotamundos.dominio.cotizacion import Criterios, EstadoOrigen, ResultadoOrigen

CRITERIOS = Criterios(date(2027, 1, 10), "hotel", "familia")


def criterios(dia: int = 10, hospedaje: str = "hotel") -> Criterios:
    return Criterios(date(2027, 1, 1 + (dia - 1) % 28), hospedaje, f"c{dia}")


def sistema(**cambios) -> SistemaCotizacion:
    return ensamblar_cotizacion(ConfiguracionCotizacion(**cambios))


def estados(grilla) -> dict[str, str]:
    return {o.proveedor: o.estado.value for o in grilla.origenes}


class Cronometro:
    def __enter__(self):
        self.inicio = time.perf_counter()
        return self

    def __exit__(self, *_):
        self.segundos = time.perf_counter() - self.inicio


class Reloj:
    """Reloj controlable para envejecer una copia sin esperar 300 s."""

    def __init__(self) -> None:
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora

    def avanzar(self, segundos: float) -> None:
        self.ahora += segundos


class HotelNuevo:
    """Un proveedor hotelero más: un solo módulo que implementa ICotizadorHotel (AC-COMP-06-09)."""

    nombre = "hotel_nuevo"

    async def ping(self) -> bool:
        return True

    def traducir(self, mensaje):
        return ()

    async def cotizar(self, criterios) -> ResultadoOrigen:
        return ResultadoOrigen(self.nombre, EstadoOrigen.OK)


def borde_con(sis: SistemaCotizacion, reloj=None, **cambios):
    """Una Caché de borde sobre el Balanceador del sistema, con reloj controlable y config propia."""
    from trotamundos.cotizacion.borde import CacheBorde

    return CacheBorde(sis.balanceador, ConfiguracionCotizacion(**cambios), **({"reloj": reloj} if reloj else {}))
