"""Acceso a las bases PostgreSQL (Tier 3).

Solo conexión y configuración. El esquema, el commit en dos fases y la conmutación a la
pasiva son de SPEC-REF-01 (ADR-IT2-004, ADR-IT2-005).
"""
from trotamundos.persistencia.conexion import conectar

__all__ = ["conectar"]
