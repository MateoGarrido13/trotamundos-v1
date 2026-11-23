# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Gestor de autorización del correo (ITERACION_3)
# ADRs: ADR-IT3-006
# DRIVERS: QA-SEG-03*, REF-02
"""Gestor de autorización del correo. Único paquete de `entrada` que puede importar
`persistencia` (tokens cifrados en la Base primaria de viajes)."""
from trotamundos.entrada.gestor_autorizacion.cifrado import CifradorTokens
from trotamundos.entrada.gestor_autorizacion.gestor import GestorAutorizacion
from trotamundos.entrada.gestor_autorizacion.repositorio import (
    RepositorioTokens,
    RepositorioTokensEnMemoria,
    RepositorioTokensPostgres,
    TokenGuardado,
)

__all__ = [
    "CifradorTokens",
    "GestorAutorizacion",
    "RepositorioTokens",
    "RepositorioTokensEnMemoria",
    "RepositorioTokensPostgres",
    "TokenGuardado",
]
