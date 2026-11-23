# SPEC: SPEC-REF-06
# ELEMENTO PASO 5: Base analítica (ITERACION_5)
# ADRs: ADR-IT5-001
# DRIVERS: REF-06, QA-DIS-01
"""Acceso a la Base analítica, con su propia conexión. No usa la persistencia de viajes."""
from __future__ import annotations

from pathlib import Path

import psycopg

ESQUEMA = Path(__file__).with_name("esquema.sql")


def conectar(dsn: str, *, autocommit: bool = False) -> psycopg.Connection:
    """Abre una conexión síncrona a la Base analítica. El llamador la cierra."""
    return psycopg.connect(dsn, autocommit=autocommit)


def aplicar_esquema(conn: psycopg.Connection) -> None:
    conn.execute(ESQUEMA.read_text())
