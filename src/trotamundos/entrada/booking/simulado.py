# SPEC: SPEC-COMP-07
# ELEMENTO PASO 5: API de Booking simulada (ITERACION_3)
# ADRs: ADR-IT3-009
# DRIVERS: CON-02
"""Booking simulado (`CON-02`, regla 8): responde al ping con demora, caída o sin eco inyectables, genera
avisos y dispara ráfagas que reentregan ante un 503 o un 429, como haría el Booking real. No usa HTTP:
quien lo prueba le da la función con la que se hace el POST."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

# post(ruta, json, cabeceras) -> código HTTP de la respuesta
Post = Callable[[str, dict, dict], Awaitable[int]]
RUTA_AVISOS = "/proveedores/booking/avisos"


class ErrorBooking(Exception):
    """La API de Booking no responde."""


@dataclass
class ResultadoEnvio:
    codigos: list[int]  # un código por intento

    @property
    def entregado(self) -> bool:
        return bool(self.codigos) and self.codigos[-1] == 202

    @property
    def intentos(self) -> int:
        return len(self.codigos)


class BookingSimulado:
    def __init__(self, clave: str = "clave-de-booking") -> None:
        self.clave = clave
        self.sin_eco = False
        self.caida = False
        self.demora_segundos = 0.0
        self.pings = 0

    async def ping(self) -> bool:
        self.pings += 1
        if self.demora_segundos:
            await asyncio.sleep(self.demora_segundos)
        if self.caida:
            raise ErrorBooking("la API de Booking no responde")
        return not self.sin_eco

    @staticmethod
    def aviso(numero: int, **cambios) -> dict:
        base = {"aviso_id": f"b-{numero}", "titulo": f"Escapada número {numero}", "destino": "Lisboa",
                "inicio": "2027-03-10", "fin": "2027-03-17", "proveedor": "Booking"}
        return {**base, **cambios}

    async def enviar(self, post: Post, aviso: dict, *, reintentos: int = 5, espera: float = 0.01,
                     clave: str | None = None) -> ResultadoEnvio:
        """Entrega un aviso y, ante 429 o 503, reentrega con espera creciente (la reentrega es de Booking)."""
        codigos: list[int] = []
        for intento in range(reintentos + 1):
            codigo = await post(RUTA_AVISOS, aviso, {"X-Clave-Proveedor": clave if clave is not None else self.clave})
            codigos.append(codigo)
            if codigo not in (429, 503) or intento == reintentos:
                break
            await asyncio.sleep(espera * (2**intento))
        return ResultadoEnvio(codigos)

    async def rafaga(self, post: Post, cantidad: int, *, desde: int = 0, **kw) -> list[ResultadoEnvio]:
        """Los avisos de las 8 am: todos a la vez."""
        return list(await asyncio.gather(*(
            self.enviar(post, self.aviso(desde + i), **kw) for i in range(cantidad))))
