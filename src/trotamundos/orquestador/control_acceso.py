# SPEC: SPEC-REF-04
# ELEMENTO PASO 5: Módulo de control de acceso y auditoría (ITERACION_4)
# ADRs: ADR-IT4-007
# DRIVERS: QA-SEG-02
"""Control de acceso por itinerario: `verificarPermiso(cuenta, itinerario, permisoRequerido)`.

Vive dentro del Orquestador y no se consulta desde fuera. Denegación por defecto: sin membresía
y rol explícitos no hay ningún permiso. La auditoría de la decisión la escribe quien opera, en
la misma transacción que la reserva (ver `gestion_reservas.py`)."""
from __future__ import annotations

from enum import StrEnum

import psycopg

from trotamundos.persistencia.repositorio_gestion import RepositorioGestion


class Rol(StrEnum):
    ORGANIZADOR = "organizador"
    PARTICIPANTE = "participante"


class Permiso(StrEnum):
    VER = "ver"
    REGISTRAR = "registrar"
    MODIFICAR = "modificar"  # actualizar y eliminar
    ADMINISTRAR_MIEMBROS = "administrar_miembros"


class Decision(StrEnum):
    CONCEDIDO = "concedido"
    DENEGADO = "denegado"
    SOLO_PROPIAS = "solo_propias"  # concedido solo sobre las reservas que la cuenta creó


# Matriz de roles y permisos de SPEC-REF-04, «Roles y permisos».
MATRIZ: dict[Rol, dict[Permiso, Decision]] = {
    Rol.ORGANIZADOR: {
        Permiso.VER: Decision.CONCEDIDO,
        Permiso.REGISTRAR: Decision.CONCEDIDO,
        Permiso.MODIFICAR: Decision.CONCEDIDO,  # cualquier reserva del itinerario
        Permiso.ADMINISTRAR_MIEMBROS: Decision.CONCEDIDO,
    },
    Rol.PARTICIPANTE: {
        Permiso.VER: Decision.CONCEDIDO,
        Permiso.REGISTRAR: Decision.CONCEDIDO,
        Permiso.MODIFICAR: Decision.SOLO_PROPIAS,
        Permiso.ADMINISTRAR_MIEMBROS: Decision.DENEGADO,
    },
}


def decidir(rol: Rol | None, permiso: Permiso) -> Decision:
    """Sin rol (sin membresía) o con un permiso fuera de la matriz: denegado."""
    if rol is None:
        return Decision.DENEGADO
    return MATRIZ.get(rol, {}).get(permiso, Decision.DENEGADO)


def alcanza(decision: Decision, creado_por: str | None, cuenta: str) -> bool:
    """¿La decisión alcanza sobre una reserva concreta? Una reserva que vino de un proveedor o
    del correo no tiene `creado_por`: con «solo propias» no alcanza, solo el organizador."""
    if decision is Decision.CONCEDIDO:
        return True
    return decision is Decision.SOLO_PROPIAS and creado_por is not None and creado_por == cuenta


class ModuloControlAcceso:
    def verificar_permiso(self, c: psycopg.Connection, cuenta: str, itinerario: str,
                          permiso: Permiso) -> Decision:
        """Consulta la membresía dentro de la transacción de quien opera, así no hay una
        ventana entre verificar y escribir."""
        rol = RepositorioGestion.rol(c, itinerario, cuenta)
        return decidir(Rol(rol) if rol else None, permiso)
