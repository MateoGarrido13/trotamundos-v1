# SPEC: SPEC-REF-03
# ELEMENTO PASO 5: Orquestador de viajes, recibe lo que entrega la ingesta (ITERACION_3)
# ADRs: ADR-IT3-003, ADR-IT2-004
# DRIVERS: REF-03, QA-SEG-03*
"""Recibe de la ingesta la reserva normalizada y la guarda en el itinerario del titular.

Implementa `EntregaOrquestador`. La clase concreta sale del Registro de tipos: un tipo que no
está registrado hace fallar la entrega (reintentos y, al agotarse, mensajes muertos con aviso);
no se descarta en silencio."""
from __future__ import annotations

import asyncio

from trotamundos.dominio.registro_tipos import RegistroTipos
from trotamundos.dominio.reserva import Origen
from trotamundos.dominio.reserva_normalizada import ReservaNormalizada
from trotamundos.persistencia.repositorio_viajes import RepositorioViajes


class IncorporadorReservas:
    def __init__(self, repositorio: RepositorioViajes, registro: RegistroTipos) -> None:
        self._repo = repositorio
        self._registro = registro

    async def incorporar(self, reserva: ReservaNormalizada) -> None:
        await asyncio.to_thread(self._incorporar, reserva)

    def _incorporar(self, rn: ReservaNormalizada) -> None:
        clase = self._registro.clase_de(rn.tipo)  # ErrorRegistroTipos si el tipo no existe
        identificador = rn.identificador_reserva
        reserva = clase(
            identificador=identificador,
            # La spec no define a qué viaje va una reserva del correo: cada una crea el suyo.
            viaje_id=f"viaje-{identificador}",
            inicio=rn.inicio, fin=rn.fin, lugar=rn.lugar, codigo=rn.codigo,
            origen=Origen.CORREO,  # sin `creado_por`: solo el organizador la puede modificar
        )
        self._repo.incorporar_reserva(rn.titular_id, reserva)
