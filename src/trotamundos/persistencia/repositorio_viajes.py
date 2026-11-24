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
from trotamundos.dominio.reserva import Reserva, lugar_a_texto
from trotamundos.persistencia.base_viajes import BaseViajes

CAMPOS_COMUNES = {"identificador", "viaje_id", "inicio", "fin", "estado", "lugar", "origen",
                  "creado_por", "editada_manualmente", "baja_en"}


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
            "INSERT INTO viaje (id, viajero_id, itinerario_id) VALUES (%s, %s, %s)",
            (viaje_id, viajero_id, viajero_id)))  # itinerario individual: id = la cuenta

    def insertar_reserva(self, reserva: Reserva) -> None:
        tipo = self._nombre_de_tipo(type(reserva))
        datos = reserva.model_dump(mode="json", exclude=CAMPOS_COMUNES)
        self._base.escribir(lambda c: c.execute(
            "INSERT INTO reserva (identificador, viaje_id, tipo, inicio, fin, estado, lugar, datos,"
            " origen, creado_por) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (reserva.identificador, reserva.viaje_id, tipo, reserva.inicio, reserva.fin,
             reserva.estado.value, lugar_a_texto(reserva.lugar), Jsonb(datos), reserva.origen.value,
             reserva.creado_por)))

    def incorporar_reserva(self, viajero_id: str, reserva: Reserva) -> bool:
        """Escribe el viaje y la reserva en una sola escritura de dos fases. Es idempotente:
        si el viaje o la reserva ya existen no hace nada (una entrega repetida tras un timeout
        no falla ni duplica). Es la entrada de las reservas que llegan por la ingesta; las
        operaciones manuales con permisos son de SPEC-REF-04. Devuelve `True` si la reserva era nueva
        y `False` si ya estaba (una entrega repetida)."""
        tipo = self._nombre_de_tipo(type(reserva))
        datos = Jsonb(reserva.model_dump(mode="json", exclude=CAMPOS_COMUNES))

        def op(c):
            c.execute("INSERT INTO viaje (id, viajero_id, itinerario_id) VALUES (%s, %s, %s)"
                      " ON CONFLICT DO NOTHING", (reserva.viaje_id, viajero_id, viajero_id))
            return c.execute(
                "INSERT INTO reserva (identificador, viaje_id, tipo, inicio, fin, estado, lugar, datos,"
                " origen, creado_por) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT DO NOTHING",
                (reserva.identificador, reserva.viaje_id, tipo, reserva.inicio, reserva.fin,
                 reserva.estado.value, lugar_a_texto(reserva.lugar), datos, reserva.origen.value,
                 reserva.creado_por)).rowcount > 0
        return self._base.escribir(op)

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
                "SELECT identificador, viaje_id, tipo, inicio, fin, estado, lugar, datos,"
                " origen, creado_por, editada_manualmente, baja_en"
                " FROM reserva WHERE viaje_id = ANY(%s) AND baja_en IS NULL"  # las bajas no se ven
                " ORDER BY inicio, identificador",
                (viaje_ids,)).fetchall()
        return [self._hidratar(*f) for f in self._base.leer(consulta)]

    def viajes_completos(self, ahora: datetime) -> list[str]:
        """Viajes activos con al menos una reserva vigente y todas con `fin <= ahora`.
        Una reserva en baja lógica no cuenta (SPEC-REF-04)."""
        def consulta(c):
            return c.execute(
                "SELECT v.id FROM viaje v WHERE v.estado = 'activo'"
                " AND EXISTS (SELECT 1 FROM reserva r WHERE r.viaje_id = v.id AND r.baja_en IS NULL)"
                " AND NOT EXISTS (SELECT 1 FROM reserva r WHERE r.viaje_id = v.id"
                " AND r.baja_en IS NULL AND r.fin > %s)"
                " ORDER BY v.id", (ahora,)).fetchall()
        return [f[0] for f in self._base.leer(consulta)]

    # --- internos -----------------------------------------------------------
    def _nombre_de_tipo(self, clase: type) -> str:
        for nombre, registrada in self._registro.tipos().items():
            if registrada is clase:
                return nombre
        raise ValueError(f"La clase {clase.__name__} no está registrada en el Registro de tipos")

    def _hidratar(self, identificador, viaje_id, tipo, inicio, fin, estado, lugar, datos,
                  origen, creado_por, editada_manualmente, baja_en) -> Reserva:
        clase = self._registro.clase_de(tipo)
        return clase(identificador=identificador, viaje_id=viaje_id, inicio=inicio, fin=fin,
                     estado=estado, lugar=lugar, origen=origen, creado_por=creado_por,
                     editada_manualmente=editada_manualmente, baja_en=baja_en, **datos)
