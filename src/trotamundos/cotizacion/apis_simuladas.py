# SPEC: SPEC-COMP-06
# ELEMENTO PASO 5: API Proveedor 2 (SOAP), API de hoteles, API de arrendadoras (ITERACION_2)
# ADRs: ADR-007
# DRIVERS: CON-02
"""APIs externas simuladas. Cada una habla su propio formato, distinto del modelo interno: el
adaptador es quien lo traduce. Se les puede inyectar demora, caída o falta de eco, y cuentan sus
llamadas para que los tests verifiquen el Ping/Echo y la ausencia de Retry (`CON-02`)."""
from __future__ import annotations

import asyncio
from datetime import date


class ErrorApiProveedor(Exception):
    """La API del proveedor no responde o falló."""


class ApiSimulada:
    def __init__(self, nombre: str) -> None:
        self.nombre = nombre
        self.demora_segundos = 0.0
        self.caida = False
        self.sin_eco = False
        self.llamadas_ping = 0
        self.llamadas_precio = 0

    async def _esperar(self) -> None:
        if self.demora_segundos:
            await asyncio.sleep(self.demora_segundos)
        if self.caida:
            raise ErrorApiProveedor(f"la API de {self.nombre} no responde")

    async def ping(self) -> bool:
        self.llamadas_ping += 1
        await self._esperar()
        return not self.sin_eco

    async def precio(self, fecha: date, hospedaje: str, compania: str):
        self.llamadas_precio += 1
        await self._esperar()
        return self._respuesta(fecha, hospedaje, compania)

    def _respuesta(self, fecha: date, hospedaje: str, compania: str):  # pragma: no cover
        raise NotImplementedError


class ApiAerolineasSoap(ApiSimulada):
    """Responde un sobre SOAP/XML (texto)."""

    def __init__(self) -> None:
        super().__init__("aerolineas")

    def _respuesta(self, fecha: date, hospedaje: str, compania: str) -> str:
        return (
            '<Envelope><Body><Tarifas>'
            f'<Tarifa vuelo="{compania}-100" fecha="{fecha.isoformat()}" importe="480.50" moneda="USD"/>'
            f'<Tarifa vuelo="{compania}-200" fecha="{fecha.isoformat()}" importe="615.00" moneda="USD"/>'
            '</Tarifas></Body></Envelope>')


class ApiHoteles(ApiSimulada):
    def __init__(self) -> None:
        super().__init__("hoteles")

    def _respuesta(self, fecha: date, hospedaje: str, compania: str) -> dict:
        return {"habitaciones": [
            {"nombre": f"{hospedaje} estándar", "tarifa": {"valor": "120.00", "divisa": "USD"}},
            {"nombre": f"{hospedaje} superior", "tarifa": {"valor": "185.00", "divisa": "USD"}}]}


class ApiArrendadoras(ApiSimulada):
    def __init__(self) -> None:
        super().__init__("arrendadoras")

    def _respuesta(self, fecha: date, hospedaje: str, compania: str) -> dict:
        return {"vehiculos": [
            {"modelo": "compacto", "precio_dia": 45.0, "currency": "USD"},
            {"modelo": "utilitario", "precio_dia": 70.0, "currency": "USD"}]}
