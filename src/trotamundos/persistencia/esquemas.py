# SPEC: SPEC-REF-01
# ELEMENTO PASO 5: Base primaria y Base pasiva (ITERACION_1, ITERACION_2)
# ADRs: ADR-IT2-004
# DRIVERS: REF-01, QA-DIS-01
"""Cargador de esquemas: aplica en orden los `.sql` de `persistencia/esquemas/` (uno por spec)."""
from __future__ import annotations

from pathlib import Path

import psycopg

CARPETA = Path(__file__).parent / "esquemas"


def aplicar_esquemas(conn: psycopg.Connection) -> None:
    for archivo in sorted(CARPETA.glob("*.sql")):
        conn.execute(archivo.read_text())
