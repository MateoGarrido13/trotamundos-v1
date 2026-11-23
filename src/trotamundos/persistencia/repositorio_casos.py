# SPEC: SPEC-REF-05
# ELEMENTO PASO 5: Orquestador de viajes, agencia preferida y casos (ITERACION_4)
# ADRs: ADR-IT4-010, ADR-IT4-007
# DRIVERS: REF-05
"""SQL de la agencia preferida y de los casos. Cada función recibe la conexión de una
transacción ya abierta por `BaseViajes.escribir` (o de una lectura)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import psycopg
from psycopg.types.json import Jsonb


@dataclass(frozen=True)
class FilaCaso:
    id: str
    cuenta_id: str
    itinerario_id: str
    reserva_id: str
    agencia: str
    descripcion: str
    resumen_dialogo: str | None
    pedido: dict
    estado: str
    creado_en: datetime
    actualizado_en: datetime


_COLUMNAS = ("id, cuenta_id, itinerario_id, reserva_id, agencia, descripcion, resumen_dialogo,"
             " pedido, estado, creado_en, actualizado_en")


class RepositorioCasos:
    @staticmethod
    def preferencia(c: psycopg.Connection, cuenta_id: str) -> str | None:
        fila = c.execute("SELECT agencia FROM preferencia_agencia WHERE cuenta_id = %s",
                         (cuenta_id,)).fetchone()
        return fila[0] if fila else None

    @staticmethod
    def guardar_preferencia(c: psycopg.Connection, cuenta_id: str, agencia: str, ahora: datetime) -> None:
        c.execute(
            "INSERT INTO preferencia_agencia (cuenta_id, agencia, consentimiento_en) VALUES (%s, %s, %s)"
            " ON CONFLICT (cuenta_id) DO UPDATE SET agencia = EXCLUDED.agencia,"
            " consentimiento_en = EXCLUDED.consentimiento_en", (cuenta_id, agencia, ahora))

    @staticmethod
    def insertar_caso(c: psycopg.Connection, caso: FilaCaso) -> None:
        c.execute(
            f"INSERT INTO caso ({_COLUMNAS}) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (caso.id, caso.cuenta_id, caso.itinerario_id, caso.reserva_id, caso.agencia,
             caso.descripcion, caso.resumen_dialogo, Jsonb(caso.pedido), caso.estado,
             caso.creado_en, caso.actualizado_en))

    @staticmethod
    def caso(c: psycopg.Connection, caso_id: str, bloquear: bool = False) -> FilaCaso | None:
        fila = c.execute(f"SELECT {_COLUMNAS} FROM caso WHERE id = %s" + (" FOR UPDATE" if bloquear else ""),
                         (caso_id,)).fetchone()
        return FilaCaso(*fila) if fila else None

    @staticmethod
    def actualizar_estado(c: psycopg.Connection, caso_id: str, estado: str, ahora: datetime) -> None:
        c.execute("UPDATE caso SET estado = %s, actualizado_en = %s WHERE id = %s",
                  (estado, ahora, caso_id))

    @staticmethod
    def casos_de(c: psycopg.Connection, cuenta_id: str) -> list[FilaCaso]:
        return [FilaCaso(*f) for f in c.execute(
            f"SELECT {_COLUMNAS} FROM caso WHERE cuenta_id = %s ORDER BY creado_en, id",
            (cuenta_id,)).fetchall()]
