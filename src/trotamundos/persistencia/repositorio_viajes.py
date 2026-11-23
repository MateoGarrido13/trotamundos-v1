# SPEC: SPEC-REF-01
# ELEMENTO PASO 5: Acceso a viajes y reservas en la Base primaria (ITERACION_1)
# ADRs: ADR-IT3-005, ADR-IT2-004
# DRIVERS: REF-01, QA-EVO-01, QA-DIS-01
"""Repositorio de viajes y reservas. Hidrata cada reserva a su clase concreta mediante el
`RegistroTipos`; no conoce ningún tipo concreto. Las altas son solo base de escritura: las
operaciones públicas de reservas son de SPEC-REF-04."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from psycopg.types.json import Jsonb

from trotamundos.dominio.registro_tipos import RegistroTipos
from trotamundos.dominio.reserva import Reserva
from trotamundos.persistencia.base_viajes import BaseViajes

CAMPOS_COMUNES = {"identificador", "viaje_id", "inicio", "fin", "estado", "lugar"}


@dataclass(frozen=True)
class Viaje:
    id: str
    viajero_id: str
    estado: str  # 'activo' | 'archivado'


class RepositorioViajes:
    def __init__(self, base: BaseViajes, registro: RegistroTipos) -> None:
        self._base = base
        self._registro = registro

    # --- escritura (2PC) ----------------------------------------------------
    def insertar_viaje(self, viaje_id: str, viajero_id: str) -> None:
        self._base.escribir(lambda c: c.execute(
            "INSERT INTO viaje (id, viajero_id) VALUES (%s, %s)", (viaje_id, viajero_id)))

    def insertar_reserva(self, reserva: Reserva) -> None:
        tipo = self._nombre_de_tipo(type(reserva))
        datos = reserva.model_dump(mode="json", exclude=CAMPOS_COMUNES)
        self._base.escribir(lambda c: c.execute(
            "INSERT INTO reserva (identificador, viaje_id, tipo, inicio, fin, estado, lugar, datos)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (reserva.identificador, reserva.viaje_id, tipo, reserva.inicio, reserva.fin,
             reserva.estado.value, reserva.lugar, Jsonb(datos))))

    def archivar(self, viaje_ids: list[str], ahora: datetime) -> None:
        if not viaje_ids:
            return
        self._base.escribir(lambda c: c.execute(
            "UPDATE viaje SET estado = 'archivado', archivado_en = %s WHERE id = ANY(%s)",
            (ahora, viaje_ids)))

    # --- lectura ------------------------------------------------------------
    def listar_viajes(self, viajero_id: str, estado: str) -> list[Viaje]:
        def consulta(c):
            return c.execute(
                "SELECT id, viajero_id, estado FROM viaje"
                " WHERE viajero_id = %s AND estado = %s ORDER BY id", (viajero_id, estado)
            ).fetchall()
        return [Viaje(*f) for f in self._base.leer(consulta)]

    def reservas_de(self, viaje_ids: list[str]) -> list[Reserva]:
        if not viaje_ids:
            return []

        def consulta(c):
            return c.execute(
                "SELECT identificador, viaje_id, tipo, inicio, fin, estado, lugar, datos"
                " FROM reserva WHERE viaje_id = ANY(%s) ORDER BY inicio, identificador",
                (viaje_ids,)).fetchall()
        return [self._hidratar(*f) for f in self._base.leer(consulta)]

    def viajes_completos(self, ahora: datetime) -> list[str]:
        """Viajes activos con al menos una reserva y todas con `fin <= ahora`."""
        def consulta(c):
            return c.execute(
                "SELECT v.id FROM viaje v WHERE v.estado = 'activo'"
                " AND EXISTS (SELECT 1 FROM reserva r WHERE r.viaje_id = v.id)"
                " AND NOT EXISTS (SELECT 1 FROM reserva r WHERE r.viaje_id = v.id AND r.fin > %s)"
                " ORDER BY v.id", (ahora,)).fetchall()
        return [f[0] for f in self._base.leer(consulta)]

    # --- internos -----------------------------------------------------------
    def _nombre_de_tipo(self, clase: type) -> str:
        for nombre, registrada in self._registro.tipos().items():
            if registrada is clase:
                return nombre
        raise ValueError(f"La clase {clase.__name__} no está registrada en el Registro de tipos")

    def _hidratar(self, identificador, viaje_id, tipo, inicio, fin, estado, lugar, datos) -> Reserva:
        clase = self._registro.clase_de(tipo)
        return clase(identificador=identificador, viaje_id=viaje_id, inicio=inicio, fin=fin,
                     estado=estado, lugar=lugar, **datos)
