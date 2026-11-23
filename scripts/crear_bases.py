"""Crea `trotamundos_dev` y `trotamundos_test` en los tres contenedores (idempotente).

Uso: .venv/bin/python scripts/crear_bases.py"""
import psycopg

PUERTOS = (5433, 5434, 5435)  # primaria, pasiva, analítica
for puerto in PUERTOS:
    with psycopg.connect(f"postgresql://trotamundos:trotamundos@localhost:{puerto}/postgres",
                         autocommit=True) as conn:
        for nombre in ("trotamundos_dev", "trotamundos_test"):
            if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (nombre,)).fetchone():
                conn.execute(f'CREATE DATABASE "{nombre}"')
                print(f"puerto {puerto}: creada {nombre}")
            else:
                print(f"puerto {puerto}: {nombre} ya existe")
