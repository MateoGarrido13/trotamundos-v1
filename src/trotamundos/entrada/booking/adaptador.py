# SPEC: SPEC-COMP-07
# ELEMENTO PASO 5: Adaptador de anuncios (Booking) (ITERACION_3)
# ADRs: ADR-IT3-009, ADR-IT3-002, ADR-IT3-003, ADR-IT3-004, ADR-004, ADR-007
# DRIVERS: QA-PER-01, QA-INT-01, CON-02
"""Adaptador de anuncios (Booking): el listener del aviso push. Autentica el origen, limita la tasa,
traduce el aviso (ACL) y lo deja en la cola de novedades con su identificador único. **Solo habla con el
Broker**: no escribe la Base de viajes ni llama al Orquestador. Con la cola llena no puede reencolar un aviso
consumido: lo rechaza (503) y la reentrega es de Booking."""
from __future__ import annotations

import asyncio
import hmac
import logging
from datetime import UTC, datetime
from typing import Any, Protocol

from trotamundos.broker import Broker, ColaLlena, Mensaje, NombreCola
from trotamundos.config import ConfiguracionBooking
from trotamundos.entrada.booking.aviso import AvisoInvalido, traducir_aviso
from trotamundos.entrada.booking.tasa import LimitadorVentana

log = logging.getLogger(__name__)
operaciones = logging.getLogger("trotamundos.operaciones")

COTA_ECO_SEGUNDOS = 5.0


class ClaveInvalida(Exception):
    """El aviso no trae la clave compartida, o no es la correcta."""


class TasaExcedida(Exception):
    """El origen superó su límite de avisos por segundo."""


class ApiBooking(Protocol):
    async def ping(self) -> bool: ...


class AdaptadorBooking:
    nombre = "booking"

    def __init__(self, broker: Broker, configuracion: ConfiguracionBooking, api: ApiBooking | None = None, *,
                 limitador: LimitadorVentana | None = None) -> None:
        self._broker = broker
        self._cfg = configuracion
        self._api = api
        self._limitador = limitador or LimitadorVentana(configuracion.tasa_avisos_por_origen)
        self.avisos: list[str] = []  # lo que se informó a operaciones

    def _avisar(self, texto: str) -> None:
        self.avisos.append(texto)
        operaciones.error(texto)

    # --- IProveedor ---------------------------------------------------------------
    async def ping(self) -> bool:
        return True if self._api is None else await self._api.ping()

    def traducir(self, mensaje: Any) -> dict[str, str]:
        return traducir_aviso(mensaje)

    async def recibir_novedad(self, mensaje: Any) -> str:
        """Traduce el aviso y lo deja en la cola de novedades. Devuelve el identificador del mensaje.
        `AvisoInvalido` si no se puede traducir; `ColaLlena` si no hay lugar."""
        anuncio = self.traducir(mensaje)
        detectado = datetime.now(UTC)  # QA-PER-01: la medida corre desde que el listener lo detecta
        try:
            self._broker.publicar(NombreCola.NOVEDADES, Mensaje(
                anuncio["id"], {"origen": "anuncio", "anuncio": anuncio, "detectado_en": detectado.isoformat()}))
        except ColaLlena:
            self._avisar(f"cola de novedades llena: se rechazó el aviso {anuncio['id']}; Booking debe reentregar")
            raise
        return anuncio["id"]

    # --- listener -------------------------------------------------------------------
    def autenticar(self, clave: str | None) -> None:
        esperada = self._cfg.clave_proveedor
        if not esperada or not clave or not hmac.compare_digest(clave.encode(), esperada.encode()):
            raise ClaveInvalida("clave inválida")

    async def recibir_aviso(self, cuerpo: Any, clave: str | None, origen: str) -> str:
        """El camino del aviso: clave (401) -> tasa (429) -> traducción (422) -> cola (202 o 503)."""
        self.autenticar(clave)
        if not self._limitador.permitir(origen):
            raise TasaExcedida(origen)
        return await self.recibir_novedad(cuerpo)

    async def cuerpo_valido(self, leer_json) -> Any:
        """Lee el JSON solo después de autenticar; uno ilegible es un aviso inválido."""
        try:
            return await leer_json()
        except ValueError:
            raise AvisoInvalido("el cuerpo no es JSON") from None

    # --- Ping/Echo ---------------------------------------------------------------------
    async def verificar_eco(self) -> bool:
        """Ping/Echo a Booking. Sin eco (o con la API caída) se informa a operaciones."""
        try:
            eco = await asyncio.wait_for(self.ping(), COTA_ECO_SEGUNDOS)
        except Exception:  # noqa: BLE001 - cualquier falla de Booking es «sin eco»
            eco = False
        if not eco:
            self._avisar("Booking no responde al ping (sin eco)")
        return eco

    async def ejecutar_eco(self) -> None:
        """Tarea periódica del eco; se cancela al cerrar la app."""
        while True:
            await self.verificar_eco()
            await asyncio.sleep(self._cfg.intervalo_eco_segundos)
