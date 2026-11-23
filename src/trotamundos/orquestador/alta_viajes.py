# SPEC: SPEC-COMP-01
# ELEMENTO PASO 5: Orquestador de viajes, control de acceso y auditoría (ITERACION_4)
# ADRs: ADR-IT4-007, ADR-IT4-008
# DRIVERS: REF-04, QA-SEG-02
"""Alta de viajes y administración de miembros. Cada operación es una sola escritura de
`BaseViajes` (2PC), con permiso, clave de operación y auditoría en la misma transacción.

Los identificadores los asigna el sistema **antes** de la operación, porque corre en las dos
bases y no puede producir valores distintos en cada una (reglas de `gestion_reservas`)."""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

import psycopg

from trotamundos.orquestador.control_acceso import Decision, ModuloControlAcceso, Permiso, Rol
from trotamundos.persistencia.base_viajes import BaseViajes
from trotamundos.persistencia.repositorio_gestion import RepositorioGestion as R

LARGO_MAXIMO_NOMBRE = 100


@dataclass(frozen=True)
class RespuestaAlta:
    estado: str  # "ok" | "denegado" | "rechazado"
    operacion: str
    motivo: str | None = None  # "nombre_invalido" | "rol_invalido" | "no_existe" | "ultimo_organizador"
    datos: dict[str, Any] = field(default_factory=dict)
    repetida: bool = False

    def a_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if k != "repetida"}

    @classmethod
    def repetida_de(cls, guardado: dict) -> RespuestaAlta:
        return cls(**guardado, repetida=True)


def _ahora() -> datetime:
    return datetime.now(UTC)


class ServicioViajes:
    def __init__(self, base: BaseViajes, acceso: ModuloControlAcceso | None = None,
                 reloj: Callable[[], datetime] = _ahora) -> None:
        self._base = base
        self._acceso = acceso or ModuloControlAcceso()
        self._reloj = reloj

    # --- operaciones ---------------------------------------------------------------
    async def crear_viaje(self, actor: str, clave: str, nombre: Any, itinerario_id: str | None = None) -> RespuestaAlta:
        viaje_id, itin_nuevo, ahora = f"viaje-{uuid.uuid4().hex[:12]}", f"itin-{uuid.uuid4().hex[:12]}", self._reloj()
        return await self._escribir(lambda c: self._crear(c, actor, f"viaje:{clave}", nombre, itinerario_id,
                                                           viaje_id, itin_nuevo, ahora))

    async def agregar_miembro(self, actor: str, itinerario_id: str, clave: str, cuenta: Any, rol: Any) -> RespuestaAlta:
        ahora = self._reloj()
        return await self._escribir(lambda c: self._agregar_miembro(c, actor, itinerario_id, f"miembro:{clave}",
                                                                    cuenta, rol, ahora))

    async def quitar_miembro(self, actor: str, itinerario_id: str, clave: str, cuenta: str) -> RespuestaAlta:
        ahora = self._reloj()
        return await self._escribir(lambda c: self._quitar_miembro(c, actor, itinerario_id, f"miembro:{clave}",
                                                                   cuenta, ahora))

    async def listar_miembros(self, actor: str, itinerario_id: str) -> list[dict] | None:
        """`None` si no tiene permiso `ver` (deja su asiento)."""
        ahora = self._reloj()

        def leer(c: psycopg.Connection):
            if self._acceso.verificar_permiso(c, actor, itinerario_id, Permiso.VER) is Decision.DENEGADO:
                return None
            return [{"cuenta": cu, "rol": ro} for cu, ro in R.miembros(c, itinerario_id)]
        miembros = await asyncio.to_thread(self._base.leer, leer)
        if miembros is None:
            await asyncio.to_thread(self._base.escribir, lambda c: self._auditar(
                c, "listar_miembros", Permiso.VER, actor, itinerario_id, "denegado", ahora, None))
        return miembros

    async def itinerarios_de(self, actor: str) -> list[dict]:
        filas = await asyncio.to_thread(self._base.leer, lambda c: R.itinerarios_de(c, actor))
        return [{"id": i, "rol": r} for i, r in filas]

    # --- dentro de la transacción ---------------------------------------------------
    def _crear(self, c, actor, clave, nombre, itin_pedido, viaje_id, itin_nuevo, ahora) -> RespuestaAlta:
        if itin_pedido is not None:
            # Inexistente y ajeno son indistinguibles: sin membresía no hay permiso (ADR-IT4-007).
            if self._acceso.verificar_permiso(c, actor, itin_pedido, Permiso.REGISTRAR) is Decision.DENEGADO:
                return self._denegar(c, "crear_viaje", Permiso.REGISTRAR, actor, itin_pedido, clave, ahora)
        guardado = R.clave(c, actor, clave)
        if guardado is not None:
            return RespuestaAlta.repetida_de(guardado)
        itin = itin_pedido or itin_nuevo
        if not isinstance(nombre, str) or not nombre.strip() or len(nombre.strip()) > LARGO_MAXIMO_NOMBRE:
            return self._rechazar(c, "crear_viaje", Permiso.REGISTRAR, actor, itin, clave, ahora, "nombre_invalido")
        if itin_pedido is None:
            R.agregar_membresia(c, itin, actor, Rol.ORGANIZADOR.value)
        R.crear_viaje(c, viaje_id, actor, itin, nombre.strip())
        return self._confirmar(c, "crear_viaje", Permiso.REGISTRAR, actor, itin, clave, ahora,
                               {"viaje_id": viaje_id, "itinerario_id": itin, "nombre": nombre.strip()})

    def _agregar_miembro(self, c, actor, itin, clave, cuenta, rol, ahora) -> RespuestaAlta:
        if self._acceso.verificar_permiso(c, actor, itin, Permiso.ADMINISTRAR_MIEMBROS) is Decision.DENEGADO:
            return self._denegar(c, "agregar_miembro", Permiso.ADMINISTRAR_MIEMBROS, actor, itin, clave, ahora)
        guardado = R.clave(c, actor, clave)
        if guardado is not None:
            return RespuestaAlta.repetida_de(guardado)
        roles = {r.value for r in Rol}
        if not isinstance(cuenta, str) or not cuenta.strip() or rol not in roles:
            motivo = "rol_invalido" if rol not in roles else "cuenta_invalida"
            return self._rechazar(c, "agregar_miembro", Permiso.ADMINISTRAR_MIEMBROS, actor, itin, clave, ahora, motivo)
        actual = R.rol(c, itin, cuenta)
        if actual == Rol.ORGANIZADOR.value and rol != actual and R.contar_organizadores(c, itin) <= 1:
            return self._rechazar(c, "agregar_miembro", Permiso.ADMINISTRAR_MIEMBROS, actor, itin, clave, ahora,
                                  "ultimo_organizador")
        R.agregar_membresia(c, itin, cuenta, rol)
        return self._confirmar(c, "agregar_miembro", Permiso.ADMINISTRAR_MIEMBROS, actor, itin, clave, ahora,
                               {"itinerario_id": itin, "cuenta": cuenta, "rol": rol})

    def _quitar_miembro(self, c, actor, itin, clave, cuenta, ahora) -> RespuestaAlta:
        if self._acceso.verificar_permiso(c, actor, itin, Permiso.ADMINISTRAR_MIEMBROS) is Decision.DENEGADO:
            return self._denegar(c, "quitar_miembro", Permiso.ADMINISTRAR_MIEMBROS, actor, itin, clave, ahora)
        guardado = R.clave(c, actor, clave)
        if guardado is not None:
            return RespuestaAlta.repetida_de(guardado)
        actual = R.rol(c, itin, cuenta)
        if actual is None:
            return self._rechazar(c, "quitar_miembro", Permiso.ADMINISTRAR_MIEMBROS, actor, itin, clave, ahora, "no_existe")
        if actual == Rol.ORGANIZADOR.value and R.contar_organizadores(c, itin) <= 1:
            return self._rechazar(c, "quitar_miembro", Permiso.ADMINISTRAR_MIEMBROS, actor, itin, clave, ahora,
                                  "ultimo_organizador")
        R.quitar_membresia(c, itin, cuenta)
        return self._confirmar(c, "quitar_miembro", Permiso.ADMINISTRAR_MIEMBROS, actor, itin, clave, ahora,
                               {"itinerario_id": itin, "cuenta": cuenta})

    # --- auditoría y clave --------------------------------------------------------
    def _denegar(self, c, op, permiso, actor, itin, clave, ahora) -> RespuestaAlta:
        self._auditar(c, op, permiso, actor, itin, "denegado", ahora, clave)
        return RespuestaAlta("denegado", op)

    def _rechazar(self, c, op, permiso, actor, itin, clave, ahora, motivo) -> RespuestaAlta:
        self._auditar(c, op, permiso, actor, itin, "rechazado", ahora, clave, motivo)
        return RespuestaAlta("rechazado", op, motivo)

    def _confirmar(self, c, op, permiso, actor, itin, clave, ahora, datos) -> RespuestaAlta:
        self._auditar(c, op, permiso, actor, itin, "permitido", ahora, clave)
        respuesta = RespuestaAlta("ok", op, datos=datos)
        R.guardar_clave(c, actor, clave, respuesta.a_dict(), ahora)
        return respuesta

    @staticmethod
    def _auditar(c, op, permiso, actor, itin, resultado, ahora, clave, motivo=None) -> None:
        R.auditar(c, cuenta_id=actor, itinerario_id=itin, operacion=op, permiso=permiso,
                  resultado=resultado, ahora=ahora, clave=clave, motivo=motivo)

    async def _escribir(self, operacion):
        def ejecutar():
            try:
                return self._base.escribir(operacion)
            except psycopg.errors.UniqueViolation:  # misma clave en paralelo: el segundo la encuentra
                return self._base.escribir(operacion)
        return await asyncio.to_thread(ejecutar)
