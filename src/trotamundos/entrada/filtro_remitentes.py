# SPEC: SPEC-REF-02 / SPEC-REF-03
# ELEMENTO PASO 5: Filtro de remitentes (whitelist) y Mensajes en revisión (ITERACION_3)
# ADRs: ADR-IT3-008, ADR-IT3-003
# DRIVERS: REF-03, QA-SEG-03*
"""Filtro de remitentes. Frontera entre SPEC-REF-02 y SPEC-REF-03.

SPEC-REF-02 llega hasta aquí: el Parseo aislado entrega la reserva normalizada, con su
identificador, al Filtro. El filtro no valida el contenido (eso ya lo hizo el parseo), no
guarda nada y no escribe la reserva: consulta y deja la reserva en el `AlmacenRevision` del
Orquestador, o la entrega a la ingesta."""
from __future__ import annotations

import logging
from typing import Protocol

from trotamundos.dominio.puertos_correo import AlmacenRevision, Ingesta, ResultadoRetencion
from trotamundos.dominio.reserva_normalizada import ReservaNormalizada

log = logging.getLogger(__name__)


class FiltroRemitentes(Protocol):
    async def recibir(self, reserva: ReservaNormalizada) -> None: ...


class FiltroRemitentesNulo:
    """Implementación provisoria que acumula lo recibido, sin filtrar. Solo para pruebas."""

    def __init__(self) -> None:
        self.recibidas: list[ReservaNormalizada] = []

    async def recibir(self, reserva: ReservaNormalizada) -> None:
        self.recibidas.append(reserva)


class FiltroWhitelist:
    """Remitente seguro: la reserva pasa a la ingesta. Remitente desconocido: queda en
    Mensajes en revisión hasta que el titular lo aprueba. Nunca descarta una reserva válida."""

    def __init__(self, almacen: AlmacenRevision, ingesta: Ingesta) -> None:
        self._almacen = almacen
        self._ingesta = ingesta

    async def recibir(self, reserva: ReservaNormalizada) -> None:
        if await self._almacen.remitente_seguro(reserva.titular_id, reserva.remitente):
            await self._ingesta.recibir(reserva)
            return
        resultado = await self._almacen.retener(reserva)
        if resultado is ResultadoRetencion.TOPE_ALCANZADO:
            # No se retiene y no se pierde: sigue en el buzón y vuelve en un sondeo posterior
            # mientras esté en la ventana. No es un fallo: no se reintenta.
            log.warning("tope de Mensajes en revisión alcanzado para %s", reserva.titular_id)

    async def liberar(self, reservas: list[ReservaNormalizada]) -> None:
        """Aviso del Orquestador: el remitente fue aprobado. Las reservas retenidas siguen
        hacia la ingesta (implementa `LiberadorDeRevision`)."""
        for reserva in reservas:
            await self._ingesta.recibir(reserva)
