# SPEC: SPEC-REF-04
# ELEMENTO PASO 5: Orquestador de viajes, precedencia de la edición manual (ITERACION_4)
# ADRs: ADR-IT4-008
# DRIVERS: REF-04
"""Lado del Orquestador de las novedades del proveedor.

Una reserva editada a mano no la sobrescribe una novedad: la novedad queda pendiente y visible
en «Novedades» para que el viajero decida. Si la reserva no fue editada, la novedad se aplica.

La ingesta de Booking (`QA-PER-01`) no tiene spec en esta tanda: esto es solo la forma mínima
de la novedad que hace verificable la precedencia. La interfaz para resolver una novedad
pendiente queda fuera de alcance."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import psycopg
from pydantic import ValidationError

from trotamundos.dominio.registro_tipos import ErrorRegistroTipos, RegistroTipos
from trotamundos.orquestador.control_acceso import Decision, ModuloControlAcceso, Permiso
from trotamundos.orquestador.eventos_analiticos import EmisorEventos
from trotamundos.orquestador.gestion_reservas import (
    EDITABLES_COMUNES,
    AccesoDenegado,
    reconstruir,
)
from trotamundos.persistencia.base_viajes import BaseViajes
from trotamundos.persistencia.repositorio_gestion import FilaNovedad, RepositorioGestion


@dataclass(frozen=True)
class NovedadProveedor:
    id: str  # identificador único: una novedad repetida se descarta
    reserva_id: str
    cambios: dict[str, Any] = field(default_factory=dict)  # inicio, fin, lugar o estado
    proveedor: str = ""


def _ahora_utc() -> datetime:
    return datetime.now(UTC)


class ServicioNovedades:
    def __init__(self, base: BaseViajes, registro: RegistroTipos,
                 acceso: ModuloControlAcceso | None = None, *,
                 reloj: Callable[[], datetime] = _ahora_utc,
                 emisor: EmisorEventos | None = None) -> None:
        self._base, self._registro = base, registro
        self._emisor = emisor  # SPEC-REF-06: una novedad aplicada es una modificación
        self._acceso = acceso or ModuloControlAcceso()
        self._reloj = reloj

    async def aplicar(self, novedad: NovedadProveedor) -> str:
        """`aplicada`, `retenida` (queda en «Novedades»), `duplicada` o `no_existe`."""
        ahora = self._reloj()
        resultado, evento = await asyncio.to_thread(
            self._base.escribir, lambda c: self._aplicar(c, novedad, ahora))
        if evento and self._emisor:
            self._emisor.emitir(evento, ahora)
        return resultado

    async def pendientes(self, actor: str, itinerario_id: str) -> list[FilaNovedad]:
        """Las novedades que esperan la decisión del viajero. Requiere permiso de ver."""
        def leer(c: psycopg.Connection):
            if self._acceso.verificar_permiso(c, actor, itinerario_id, Permiso.VER) is Decision.DENEGADO:
                return None
            return RepositorioGestion.novedades_pendientes(c, itinerario_id)
        pendientes = await asyncio.to_thread(self._base.leer, leer)
        if pendientes is None:
            raise AccesoDenegado(f"{actor} no puede ver el itinerario {itinerario_id}")
        return pendientes

    def _aplicar(self, c: psycopg.Connection, n: NovedadProveedor, ahora: datetime) -> tuple[str, dict | None]:
        fila = RepositorioGestion.reserva(c, n.reserva_id)
        if fila is None:
            return "no_existe", None
        if RepositorioGestion.novedad_existe(c, n.id):
            return "duplicada", None
        registrar = lambda estado: RepositorioGestion.insertar_novedad(  # noqa: E731
            c, novedad_id=n.id, itinerario_id=fila.itinerario_id, reserva_id=n.reserva_id,
            proveedor=n.proveedor, cambios=_serializable(n.cambios), estado=estado, ahora=ahora)
        if fila.editada_manualmente or fila.baja_en is not None:
            registrar("pendiente")  # la edición manual tiene precedencia
            return "retenida", None
        try:
            if set(n.cambios) - EDITABLES_COMUNES:
                raise ValueError("la novedad trae campos que no se pueden aplicar")
            nueva = reconstruir(self._registro, fila, n.cambios)
        except (ValidationError, ValueError, TypeError, ErrorRegistroTipos):
            registrar("pendiente")  # no se puede aplicar sola: la decide el viajero
            return "retenida", None
        RepositorioGestion.actualizar_reserva(c, nueva, marcar_editada=False)
        registrar("aplicada")
        return "aplicada", {"tipo": "modificacion", "tipo_reserva": fila.tipo, "destino": nueva.lugar,
                            "inicio": nueva.inicio, "fin": nueva.fin, "origen": fila.origen,
                            "estado": nueva.estado.value}


def _serializable(cambios: dict[str, Any]) -> dict[str, Any]:
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in cambios.items()}
