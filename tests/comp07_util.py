"""Ayudas compartidas de los tests de SPEC-COMP-07 (Booking)."""
from __future__ import annotations

import httpx
from fastapi import FastAPI

from trotamundos.broker import Aviso, Broker, NombreCola
from trotamundos.config import ConfiguracionBooking, ConfiguracionBroker
from trotamundos.entrada.booking.adaptador import AdaptadorBooking
from trotamundos.entrada.booking.listener import crear_router
from trotamundos.entrada.booking.simulado import RUTA_AVISOS, BookingSimulado

CLAVE = "clave-de-booking"
CFG = ConfiguracionBooking(clave_proveedor=CLAVE)


class Entorno:
    """El listener sobre un Broker propio, con Booking simulado, sin base de datos."""

    def __init__(self, *, tamano_cola: int = 100, cfg: ConfiguracionBooking = CFG) -> None:
        self.avisos_broker: list[Aviso] = []
        self.broker = Broker(ConfiguracionBroker(tamano_maximo_cola=tamano_cola), avisar=self.avisos_broker.append)
        self.booking = BookingSimulado(CLAVE)
        self.adaptador = AdaptadorBooking(self.broker, cfg, self.booking)
        app = FastAPI()
        app.include_router(crear_router(self.adaptador))
        self.app = app
        self.http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("10.0.0.9", 4000)),
                                      base_url="http://t")

    async def post(self, ruta: str, cuerpo: dict, cabeceras: dict) -> int:
        return (await self.http.post(ruta, json=cuerpo, headers=cabeceras)).status_code

    async def avisar(self, cuerpo: dict, clave: str | None = CLAVE) -> httpx.Response:
        cabeceras = {"X-Clave-Proveedor": clave} if clave is not None else {}
        return await self.http.post(RUTA_AVISOS, json=cuerpo, headers=cabeceras)

    def en_cola(self) -> int:
        return self.broker.tamano_actual(NombreCola.NOVEDADES)
