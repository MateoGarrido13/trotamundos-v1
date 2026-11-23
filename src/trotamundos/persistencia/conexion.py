from __future__ import annotations

import psycopg


def conectar(dsn: str, *, autocommit: bool = False) -> psycopg.Connection:
    """Abre una conexión síncrona. El llamador la cierra."""
    return psycopg.connect(dsn, autocommit=autocommit)
