# SPEC: SPEC-COMP-06
# ELEMENTO PASO 5: Adaptador de aerolíneas, Adaptador de hoteles, Adaptador de arrendadoras (ITERACION_2)
# ADRs: ADR-IT2-003, ADR-004, ADR-007, ADR-IT3-004
# DRIVERS: QA-PER-02, QA-INT-01
"""Los tres adaptadores de cotización. Cada uno es la Capa anti-corrupción de su API: traduce al
modelo interno, hace Ping/Echo antes de pedir el precio y corta la espera en su cota. **Sin Retry**:
cualquier falla informa «origen no respondió» y el pedido de precio no sigue."""
from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from typing import Any

from trotamundos.cotizacion.apis_simuladas import (
    ApiAerolineasSoap, ApiArrendadoras, ApiHoteles, ApiSimulada, ErrorApiProveedor)
from trotamundos.dominio.cotizacion import Criterios, EstadoOrigen, Precio, ResultadoOrigen

log = logging.getLogger(__name__)


class RespuestaInvalida(ValueError):
    """La API respondió algo que no se puede traducir."""


def _precio(descripcion: str, monto: Any, moneda: Any) -> Precio:
    try:
        return Precio(str(descripcion), Decimal(str(monto)), str(moneda))
    except (InvalidOperation, ValueError) as error:
        raise RespuestaInvalida(f"importe inválido: {monto!r}") from error


class _AdaptadorBase:
    nombre: str

    def __init__(self, api: ApiSimulada, cota_segundos: float) -> None:
        self._api = api
        self._cota = cota_segundos

    async def ping(self) -> bool:
        return await self._api.ping()

    def traducir(self, mensaje: Any) -> tuple[Precio, ...]:  # pragma: no cover
        raise NotImplementedError

    async def recibir_novedad(self, mensaje: Any) -> Any:
        """`IProveedor.recibir_novedad` (SPEC-COMP-07): la cotización no recibe avisos de proveedores."""
        raise NotImplementedError("los adaptadores de cotización no reciben novedades")

    async def _consultar(self, criterios: Criterios) -> tuple[Precio, ...] | None:
        if not await self.ping():  # Ping/Echo: sin eco no se pide el precio
            return None
        mensaje = await self._api.precio(criterios.fecha, criterios.hospedaje, criterios.compania)
        return self.traducir(mensaje)

    async def cotizar(self, criterios: Criterios) -> ResultadoOrigen:
        try:
            precios = await asyncio.wait_for(self._consultar(criterios), self._cota)
        except (TimeoutError, ErrorApiProveedor, RespuestaInvalida) as error:
            log.warning("%s: origen no respondió (%s)", self.nombre, type(error).__name__)
            precios = None
        if precios is None:
            return ResultadoOrigen(self.nombre, EstadoOrigen.NO_RESPONDIO)
        return ResultadoOrigen(self.nombre, EstadoOrigen.OK, precios)


class AdaptadorAerolineas(_AdaptadorBase):
    nombre = "aerolineas"

    def __init__(self, api: ApiAerolineasSoap, cota_segundos: float) -> None:
        super().__init__(api, cota_segundos)

    def traducir(self, mensaje: str) -> tuple[Precio, ...]:
        try:
            raiz = ET.fromstring(mensaje)
        except ET.ParseError as error:
            raise RespuestaInvalida("sobre SOAP inválido") from error
        return tuple(_precio(t.get("vuelo", ""), t.get("importe"), t.get("moneda"))
                     for t in raiz.iter("Tarifa"))


class AdaptadorHoteles(_AdaptadorBase):
    nombre = "hoteles"

    def __init__(self, api: ApiHoteles, cota_segundos: float) -> None:
        super().__init__(api, cota_segundos)

    def traducir(self, mensaje: dict) -> tuple[Precio, ...]:
        try:
            return tuple(_precio(h["nombre"], h["tarifa"]["valor"], h["tarifa"]["divisa"])
                         for h in mensaje["habitaciones"])
        except (KeyError, TypeError) as error:
            raise RespuestaInvalida("respuesta de hoteles inválida") from error


class AdaptadorArrendadoras(_AdaptadorBase):
    nombre = "arrendadoras"

    def __init__(self, api: ApiArrendadoras, cota_segundos: float) -> None:
        super().__init__(api, cota_segundos)

    def traducir(self, mensaje: dict) -> tuple[Precio, ...]:
        try:
            return tuple(_precio(v["modelo"], v["precio_dia"], v["currency"]) for v in mensaje["vehiculos"])
        except (KeyError, TypeError) as error:
            raise RespuestaInvalida("respuesta de arrendadoras inválida") from error
