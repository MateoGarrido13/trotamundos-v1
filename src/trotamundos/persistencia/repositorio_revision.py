# SPEC: SPEC-REF-03
# ELEMENTO PASO 5: Orquestador de viajes, whitelist y Mensajes en revisión (ITERACION_3)
# ADRs: ADR-IT3-008, ADR-IT2-004
# DRIVERS: REF-03, QA-SEG-03*
"""Acceso a la whitelist y a Mensajes en revisión. Toda escritura pasa por `BaseViajes`
(commit en dos fases)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from psycopg.types.json import Jsonb

from trotamundos.dominio.puertos_correo import ResultadoRetencion
from trotamundos.dominio.reserva_normalizada import ReservaNormalizada
from trotamundos.persistencia.base_viajes import BaseViajes


def normalizar_remitente(remitente: str) -> str:
    """Se compara en minúsculas y sin espacios en los extremos."""
    return remitente.strip().lower()


@dataclass(frozen=True)
class MensajePendiente:
    id_mensaje: str
    remitente: str
    reserva: ReservaNormalizada

    @property
    def resumen(self) -> str:
        r = self.reserva
        return f"{r.tipo} en {r.lugar} ({r.inicio:%Y-%m-%d} a {r.fin:%Y-%m-%d})"


class RepositorioRevision:
    def __init__(self, base: BaseViajes, tope_pendientes: int) -> None:
        self._base = base
        self._tope = tope_pendientes

    # --- whitelist ----------------------------------------------------------
    def es_seguro(self, titular_id: str, remitente: str) -> bool:
        rem = normalizar_remitente(remitente)
        return self._base.leer(lambda c: c.execute(
            "SELECT 1 FROM remitente_seguro WHERE titular_id = %s AND remitente = %s",
            (titular_id, rem)).fetchone()) is not None

    def agregar_remitente(self, titular_id: str, remitente: str) -> None:
        rem = normalizar_remitente(remitente)
        self._base.escribir(lambda c: c.execute(
            "INSERT INTO remitente_seguro (titular_id, remitente) VALUES (%s, %s)"
            " ON CONFLICT DO NOTHING", (titular_id, rem)))

    def quitar_remitente(self, titular_id: str, remitente: str) -> None:
        rem = normalizar_remitente(remitente)
        self._base.escribir(lambda c: c.execute(
            "DELETE FROM remitente_seguro WHERE titular_id = %s AND remitente = %s",
            (titular_id, rem)))

    # --- Mensajes en revisión -------------------------------------------------
    def retener(self, reserva: ReservaNormalizada, ahora: datetime) -> ResultadoRetencion:
        """Retiene la reserva, salvo que ya esté pendiente, descartada o incorporada al
        itinerario (se ignora) o que el titular tenga el tope de pendientes (no se retiene,
        sigue en el buzón)."""
        titular, ident = reserva.titular_id, reserva.id_mensaje
        ya_incorporada = reserva.identificador_reserva
        rem = normalizar_remitente(reserva.remitente)
        cuerpo = Jsonb(reserva.model_dump(mode="json"))
        tope = self._tope

        def op(c):
            if c.execute("SELECT 1 FROM mensaje_revision WHERE titular_id = %s AND id_mensaje = %s",
                         (titular, ident)).fetchone():
                return ResultadoRetencion.DUPLICADA
            # Un mensaje que ya está en el itinerario no vuelve a revisión, aunque se haya quitado
            # al remitente de la whitelist y el correo siga dentro de la ventana de sondeo.
            if c.execute("SELECT 1 FROM reserva WHERE identificador = %s",
                         (ya_incorporada,)).fetchone():
                return ResultadoRetencion.DUPLICADA
            pendientes = c.execute(
                "SELECT count(*) FROM mensaje_revision WHERE titular_id = %s AND estado = 'pendiente'",
                (titular,)).fetchone()[0]
            if pendientes >= tope:
                return ResultadoRetencion.TOPE_ALCANZADO
            c.execute(
                "INSERT INTO mensaje_revision (titular_id, id_mensaje, remitente, reserva, creado_en)"
                " VALUES (%s, %s, %s, %s, %s)", (titular, ident, rem, cuerpo, ahora))
            return ResultadoRetencion.RETENIDA
        return self._base.escribir(op)

    def pendientes(self, titular_id: str) -> list[MensajePendiente]:
        return self._leer_pendientes(
            "SELECT id_mensaje, remitente, reserva FROM mensaje_revision"
            " WHERE titular_id = %s AND estado = 'pendiente' ORDER BY creado_en, id_mensaje",
            (titular_id,))

    def pendientes_de(self, titular_id: str, remitente: str) -> list[MensajePendiente]:
        return self._leer_pendientes(
            "SELECT id_mensaje, remitente, reserva FROM mensaje_revision"
            " WHERE titular_id = %s AND remitente = %s AND estado = 'pendiente'"
            " ORDER BY creado_en, id_mensaje", (titular_id, normalizar_remitente(remitente)))

    def borrar(self, titular_id: str, ids_mensaje: list[str]) -> None:
        if not ids_mensaje:
            return
        self._base.escribir(lambda c: c.execute(
            "DELETE FROM mensaje_revision WHERE titular_id = %s AND id_mensaje = ANY(%s)",
            (titular_id, ids_mensaje)))

    def descartar(self, titular_id: str, id_mensaje: str) -> bool:
        """Pasa un pendiente del titular a descartado. False si no existe, es de otro titular
        o ya está resuelto: en ese caso no cambia ningún dato."""
        return self._base.escribir(lambda c: c.execute(
            "UPDATE mensaje_revision SET estado = 'descartado', reserva = '{}'::jsonb"
            " WHERE titular_id = %s AND id_mensaje = %s AND estado = 'pendiente'",
            (titular_id, id_mensaje)).rowcount > 0)

    def purgar(self, limite: datetime) -> int:
        """Elimina los mensajes (pendientes o descartados) creados antes de `limite`."""
        return self._base.escribir(lambda c: c.execute(
            "DELETE FROM mensaje_revision WHERE creado_en < %s", (limite,)).rowcount)

    # --- internos -----------------------------------------------------------
    def _leer_pendientes(self, sql: str, params: tuple) -> list[MensajePendiente]:
        filas = self._base.leer(lambda c: c.execute(sql, params).fetchall())
        return [MensajePendiente(i, r, ReservaNormalizada.model_validate(datos))
                for i, r, datos in filas]
