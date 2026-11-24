# SPEC: SPEC-REF-04
# ELEMENTO PASO 5: Operaciones manuales de reserva, Módulo de control de acceso y auditoría (ITERACION_4)
# ADRs: ADR-IT4-007, ADR-IT4-008, ADR-IT4-009
# DRIVERS: REF-04, QA-SEG-02
"""SQL de la gestión manual. Cada función recibe la conexión de una transacción ya abierta
por `BaseViajes.escribir`: así la decisión de acceso, la reserva, la auditoría y la clave de
operación se escriben juntas (commit en dos fases) o no se escribe nada."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from trotamundos.dominio.reserva import Reserva, lugar_a_texto
from trotamundos.persistencia.repositorio_viajes import CAMPOS_COMUNES


@dataclass(frozen=True)
class FilaReserva:
    identificador: str
    viaje_id: str
    itinerario_id: str
    tipo: str
    inicio: datetime
    fin: datetime
    estado: str
    lugar: str | None
    datos: dict
    origen: str
    creado_por: str | None
    editada_manualmente: bool
    baja_en: datetime | None


@dataclass(frozen=True)
class FilaNovedad:
    id: str
    reserva_id: str
    proveedor: str
    cambios: dict
    estado: str
    recibida_en: datetime


class RepositorioGestion:
    # --- membresías -----------------------------------------------------------
    @staticmethod
    def rol(c: psycopg.Connection, itinerario_id: str, cuenta_id: str) -> str | None:
        fila = c.execute("SELECT rol FROM membresia WHERE itinerario_id = %s AND cuenta_id = %s",
                         (itinerario_id, cuenta_id)).fetchone()
        return fila[0] if fila else None

    @staticmethod
    def agregar_membresia(c: psycopg.Connection, itinerario_id: str, cuenta_id: str, rol: str) -> None:
        """Precarga de membresías (datos de prueba, como fija la spec)."""
        c.execute("INSERT INTO membresia (itinerario_id, cuenta_id, rol) VALUES (%s, %s, %s)"
                  " ON CONFLICT (itinerario_id, cuenta_id) DO UPDATE SET rol = EXCLUDED.rol",
                  (itinerario_id, cuenta_id, rol))

    # --- viajes y reservas ------------------------------------------------------
    @staticmethod
    def itinerario_del_viaje(c: psycopg.Connection, viaje_id: str) -> str | None:
        fila = c.execute("SELECT itinerario_id FROM viaje WHERE id = %s", (viaje_id,)).fetchone()
        return fila[0] if fila else None

    @staticmethod
    def crear_viaje(c: psycopg.Connection, viaje_id: str, viajero_id: str, itinerario_id: str,
                    nombre: str = "") -> None:
        c.execute("INSERT INTO viaje (id, viajero_id, itinerario_id, nombre) VALUES (%s, %s, %s, %s)",
                  (viaje_id, viajero_id, itinerario_id, nombre))

    # --- membresías (SPEC-COMP-01) -------------------------------------------------
    @staticmethod
    def quitar_membresia(c: psycopg.Connection, itinerario_id: str, cuenta_id: str) -> None:
        c.execute("DELETE FROM membresia WHERE itinerario_id = %s AND cuenta_id = %s",
                  (itinerario_id, cuenta_id))

    @staticmethod
    def contar_organizadores(c: psycopg.Connection, itinerario_id: str) -> int:
        return c.execute("SELECT count(*) FROM membresia WHERE itinerario_id = %s AND rol = 'organizador'",
                         (itinerario_id,)).fetchone()[0]

    @staticmethod
    def miembros(c: psycopg.Connection, itinerario_id: str) -> list[tuple[str, str]]:
        return [(f[0], f[1]) for f in c.execute(
            "SELECT cuenta_id, rol FROM membresia WHERE itinerario_id = %s ORDER BY cuenta_id",
            (itinerario_id,)).fetchall()]

    @staticmethod
    def itinerarios_de(c: psycopg.Connection, cuenta_id: str) -> list[tuple[str, str]]:
        return [(f[0], f[1]) for f in c.execute(
            "SELECT itinerario_id, rol FROM membresia WHERE cuenta_id = %s ORDER BY itinerario_id",
            (cuenta_id,)).fetchall()]

    @staticmethod
    def reserva(c: psycopg.Connection, reserva_id: str, bloquear: bool = True) -> FilaReserva | None:
        fila = c.execute(
            "SELECT r.identificador, r.viaje_id, v.itinerario_id, r.tipo, r.inicio, r.fin, r.estado,"
            " r.lugar, r.datos, r.origen, r.creado_por, r.editada_manualmente, r.baja_en"
            " FROM reserva r JOIN viaje v ON v.id = r.viaje_id WHERE r.identificador = %s"
            + (" FOR UPDATE OF r" if bloquear else ""), (reserva_id,)).fetchone()
        return FilaReserva(*fila) if fila else None

    @staticmethod
    def insertar_reserva(c: psycopg.Connection, reserva: Reserva, tipo: str) -> None:
        c.execute(
            "INSERT INTO reserva (identificador, viaje_id, tipo, inicio, fin, estado, lugar, datos,"
            " origen, creado_por) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (reserva.identificador, reserva.viaje_id, tipo, reserva.inicio, reserva.fin,
             reserva.estado.value, lugar_a_texto(reserva.lugar),
             Jsonb(reserva.model_dump(mode="json", exclude=CAMPOS_COMUNES)),
             reserva.origen.value, reserva.creado_por))

    @staticmethod
    def actualizar_reserva(c: psycopg.Connection, reserva: Reserva, marcar_editada: bool = True) -> None:
        c.execute(
            "UPDATE reserva SET inicio = %s, fin = %s, estado = %s, lugar = %s, datos = %s,"
            " editada_manualmente = editada_manualmente OR %s WHERE identificador = %s",
            (reserva.inicio, reserva.fin, reserva.estado.value, lugar_a_texto(reserva.lugar),
             Jsonb(reserva.model_dump(mode="json", exclude=CAMPOS_COMUNES)), marcar_editada,
             reserva.identificador))

    @staticmethod
    def dar_de_baja(c: psycopg.Connection, reserva_id: str, ahora: datetime) -> None:
        c.execute("UPDATE reserva SET baja_en = %s WHERE identificador = %s", (ahora, reserva_id))

    # --- claves de operación (idempotencia) ----------------------------------------
    @staticmethod
    def clave(c: psycopg.Connection, cuenta_id: str, clave: str) -> dict | None:
        fila = c.execute("SELECT resultado FROM clave_operacion WHERE cuenta_id = %s AND clave = %s",
                         (cuenta_id, clave)).fetchone()
        return fila[0] if fila else None

    @staticmethod
    def guardar_clave(c: psycopg.Connection, cuenta_id: str, clave: str, resultado: dict,
                      ahora: datetime) -> None:
        c.execute("INSERT INTO clave_operacion (cuenta_id, clave, resultado, creada_en)"
                  " VALUES (%s, %s, %s, %s)", (cuenta_id, clave, Jsonb(resultado), ahora))

    @staticmethod
    def purgar_claves(c: psycopg.Connection, limite: datetime) -> int:
        return c.execute("DELETE FROM clave_operacion WHERE creada_en < %s", (limite,)).rowcount

    # --- auditoría --------------------------------------------------------------------
    @staticmethod
    def auditar(c: psycopg.Connection, *, cuenta_id: str, itinerario_id: str, operacion: str,
                permiso: str, resultado: str, ahora: datetime, reserva_id: str | None = None,
                clave: str | None = None, motivo: str | None = None) -> None:
        c.execute(
            "INSERT INTO auditoria (cuenta_id, itinerario_id, operacion, permiso, resultado,"
            " reserva_id, clave, motivo, momento) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (cuenta_id, itinerario_id, operacion, permiso, resultado, reserva_id, clave, motivo, ahora))

    @staticmethod
    def asientos(c: psycopg.Connection, itinerario_id: str) -> list[dict[str, Any]]:
        filas = c.execute(
            "SELECT cuenta_id, operacion, permiso, resultado, reserva_id, clave, motivo FROM auditoria"
            " WHERE itinerario_id = %s ORDER BY id", (itinerario_id,)).fetchall()
        return [dict(zip(("cuenta", "operacion", "permiso", "resultado", "reserva", "clave", "motivo"), f))
                for f in filas]

    # --- vista -------------------------------------------------------------------------
    @staticmethod
    def viajes_del_itinerario(c: psycopg.Connection, itinerario_id: str, estado: str) -> list[tuple[str, str]]:
        return [(f[0], f[1]) for f in c.execute(
            "SELECT id, estado FROM viaje WHERE itinerario_id = %s AND estado = %s ORDER BY id",
            (itinerario_id, estado)).fetchall()]

    # --- novedades -----------------------------------------------------------------------
    @staticmethod
    def novedad_existe(c: psycopg.Connection, novedad_id: str) -> bool:
        return c.execute("SELECT 1 FROM novedad WHERE id = %s", (novedad_id,)).fetchone() is not None

    @staticmethod
    def insertar_novedad(c: psycopg.Connection, *, novedad_id: str, itinerario_id: str, reserva_id: str,
                         proveedor: str, cambios: dict, estado: str, ahora: datetime) -> None:
        c.execute("INSERT INTO novedad (id, itinerario_id, reserva_id, proveedor, cambios, estado,"
                  " recibida_en) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                  (novedad_id, itinerario_id, reserva_id, proveedor, Jsonb(cambios), estado, ahora))

    @staticmethod
    def novedades_pendientes(c: psycopg.Connection, itinerario_id: str) -> list[FilaNovedad]:
        return [FilaNovedad(*f) for f in c.execute(
            "SELECT id, reserva_id, proveedor, cambios, estado, recibida_en FROM novedad"
            " WHERE itinerario_id = %s AND estado = 'pendiente' ORDER BY recibida_en, id",
            (itinerario_id,)).fetchall()]
