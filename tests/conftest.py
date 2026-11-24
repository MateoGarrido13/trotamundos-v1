import os

# SPEC-COMP-01, regla 9: los tests usan sus propias bases. Debe fijarse antes de importar la configuración.
os.environ.setdefault("TROTA_DSN_VIAJES_PRIMARIA", "postgresql://trotamundos:trotamundos@localhost:5433/trotamundos_test")
os.environ.setdefault("TROTA_DSN_VIAJES_PASIVA", "postgresql://trotamundos:trotamundos@localhost:5434/trotamundos_test")
os.environ.setdefault("TROTA_DSN_ANALITICA", "postgresql://trotamundos:trotamundos@localhost:5435/trotamundos_test")
# SPEC-COMP-05: las seis bases de cuentas, también en sus bases de test.
for _i, (_region, _puertos) in enumerate({"AMER": (5436, 5437), "EMEA": (5438, 5439), "APAC": (5440, 5441)}.items()):
    for _rol, _puerto in zip(("PRIMARIA", "PASIVA"), _puertos):
        os.environ.setdefault(f"TROTA_DSN_CUENTAS_{_region}_{_rol}",
                              f"postgresql://trotamundos:trotamundos@localhost:{_puerto}/trotamundos_test")

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


# --- Base analítica (SPEC-REF-06) ---------------------------------------------------
from trotamundos.analitica.base import aplicar_esquema as aplicar_esquema_analitico  # noqa: E402
from trotamundos.analitica.base import conectar as conectar_analitica  # noqa: E402
from trotamundos.config import ConfiguracionAnalitica  # noqa: E402


@pytest.fixture
def analitica_limpia():
    """La Base analítica con las tablas recreadas; devuelve su configuración."""
    cfg = ConfiguracionAnalitica()
    with conectar_analitica(cfg.dsn, autocommit=True) as conn:
        assert conn.execute("SELECT current_database()").fetchone()[0].endswith("_test")
        conn.execute("DROP TABLE IF EXISTS evento, contador CASCADE")
        aplicar_esquema_analitico(conn)
    return cfg


# --- Bases de viajes (SPEC-REF-01) -------------------------------------------------
from trotamundos.config import ConfiguracionBases  # noqa: E402
from trotamundos.persistencia.conexion import conectar  # noqa: E402
from trotamundos.persistencia.esquemas import aplicar_esquemas  # noqa: E402


def limpiar_base(dsn: str) -> None:
    """Revierte transacciones preparadas colgadas y recrea las tablas (REF-01 y REF-02)."""
    with conectar(dsn, autocommit=True) as conn:
        base = conn.execute("SELECT current_database()").fetchone()[0]
        if not base.endswith("_test"):  # SPEC-COMP-01, regla 9: nunca vaciar una base de desarrollo
            raise RuntimeError(f"los tests se niegan a borrar la base {base!r}")
        gids = conn.execute(
            "SELECT gid FROM pg_prepared_xacts WHERE database = current_database()").fetchall()
        for (gid,) in gids:
            conn.execute(f"ROLLBACK PREPARED '{gid}'")
        conn.execute("DROP TABLE IF EXISTS reserva, viaje, token_correo, remitente_seguro, mensaje_revision,"
            " membresia, auditoria, clave_operacion, novedad, preferencia_agencia, caso CASCADE")
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


# --- Bases de cuentas (SPEC-COMP-05) -------------------------------------------------
from trotamundos.config import ConfiguracionIdentidad  # noqa: E402
from trotamundos.identidad.region.base import TABLAS as TABLAS_CUENTAS  # noqa: E402
from trotamundos.identidad.region.base import aplicar_esquema as aplicar_esquema_cuentas  # noqa: E402


def limpiar_cuentas(dsn: str) -> None:
    with conectar(dsn, autocommit=True) as conn:
        base = conn.execute("SELECT current_database()").fetchone()[0]
        if not base.endswith("_test"):
            raise RuntimeError(f"los tests se niegan a borrar la base {base!r}")
        for (gid,) in conn.execute(
                "SELECT gid FROM pg_prepared_xacts WHERE database = current_database()").fetchall():
            conn.execute(f"ROLLBACK PREPARED '{gid}'")
        conn.execute("DROP TABLE IF EXISTS " + ", ".join(TABLAS_CUENTAS) + " CASCADE")
        aplicar_esquema_cuentas(conn)


@pytest.fixture
def cuentas_limpias():
    """Las seis bases de cuentas con las tablas recreadas; devuelve la configuración de identidad
    con claves de firma fijas y un costo de hash bajo para los tests."""
    cfg = ConfiguracionIdentidad(
        claves_firma={"amer": "01" * 32, "emea": "02" * 32, "apac": "03" * 32},
        clave_gateway="secreto-del-gateway", costo_hash=4)
    for primaria, pasiva in cfg.dsn.values():
        limpiar_cuentas(primaria)
        limpiar_cuentas(pasiva)
    return cfg
