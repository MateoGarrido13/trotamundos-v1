from datetime import datetime

import pytest

from trotamundos.config import ConfiguracionBroker
from trotamundos.dominio.reserva import Reserva


class ReservaDePrueba(Reserva):
    """Tipo concreto mínimo para los tests del esqueleto."""

    def resumen(self) -> str:
        return f"Prueba {self.identificador}"


@pytest.fixture
def reserva_de_prueba():
    return ReservaDePrueba(
        identificador="r1", viaje_id="v1",
        inicio=datetime(2026, 12, 1), fin=datetime(2026, 12, 5),
    )


@pytest.fixture
def cfg_broker():
    """Colas de 5 y backoff 1 s, como las specs para los tests."""
    return ConfiguracionBroker(tamano_maximo_cola=5, reintentos=3, backoff_base_segundos=1.0)


# --- Bases de viajes (SPEC-REF-01) -------------------------------------------------
from trotamundos.config import ConfiguracionBases  # noqa: E402
from trotamundos.persistencia.conexion import conectar  # noqa: E402
from trotamundos.persistencia.esquemas import aplicar_esquemas  # noqa: E402


def limpiar_base(dsn: str) -> None:
    """Revierte transacciones preparadas colgadas y recrea las tablas (REF-01 y REF-02)."""
    with conectar(dsn, autocommit=True) as conn:
        gids = conn.execute(
            "SELECT gid FROM pg_prepared_xacts WHERE database = current_database()").fetchall()
        for (gid,) in gids:
            conn.execute(f"ROLLBACK PREPARED '{gid}'")
        conn.execute("DROP TABLE IF EXISTS reserva, viaje, token_correo, remitente_seguro, mensaje_revision,"
            " membresia, auditoria, clave_operacion, novedad CASCADE")
        aplicar_esquemas(conn)


@pytest.fixture
def bases_limpias():
    cfg = ConfiguracionBases()
    limpiar_base(cfg.viajes_primaria)
    limpiar_base(cfg.viajes_pasiva)
    yield cfg
    for dsn in (cfg.viajes_primaria, cfg.viajes_pasiva):
        with conectar(dsn, autocommit=True) as conn:
            for (gid,) in conn.execute(
                    "SELECT gid FROM pg_prepared_xacts WHERE database = current_database()"
            ).fetchall():
                conn.execute(f"ROLLBACK PREPARED '{gid}'")
