# SPEC: SPEC-REF-01
# ELEMENTO PASO 5: Commit en dos fases del Orquestador (ITERACION_2)
# ADRs: ADR-IT2-004
# DRIVERS: QA-DIS-01
import psycopg
import pytest

from trotamundos.persistencia.base_viajes import BaseViajes, ErrorBaseNoDisponible
from trotamundos.persistencia.conexion import conectar

pytestmark = pytest.mark.db


class Espia:
    """Envuelve una conexión y registra PREPARE / COMMIT PREPARED; puede fallar a demanda."""

    def __init__(self, conn, lado, eventos, falla_en=None):
        self._conn, self._lado, self._eventos, self._falla_en = conn, lado, eventos, falla_en

    def execute(self, sql, *args, **kw):
        palabra = sql.split("'")[0].strip()
        if palabra in ("PREPARE TRANSACTION", "COMMIT PREPARED"):
            if self._falla_en == palabra:
                raise psycopg.OperationalError("fallo inyectado")
            self._eventos.append((palabra, self._lado))
        return self._conn.execute(sql, *args, **kw)

    def close(self):
        self._conn.close()


def _base(cfg, eventos, falla_pasiva=None):
    return BaseViajes(
        lambda: Espia(conectar(cfg.viajes_primaria, autocommit=True), "primaria", eventos),
        lambda: Espia(conectar(cfg.viajes_pasiva, autocommit=True), "pasiva", eventos, falla_pasiva),
    )


def _cuenta(dsn):
    with conectar(dsn) as c:
        return c.execute("SELECT count(*) FROM viaje").fetchone()[0]


def _alta(c):
    c.execute("INSERT INTO viaje (id, viajero_id) VALUES ('v1', 'ana')")


def test_AC_REF_01_04_pasiva_acuerda_antes_de_que_la_primaria_confirme(bases_limpias):
    eventos = []
    _base(bases_limpias, eventos).escribir(_alta)
    assert eventos.index(("PREPARE TRANSACTION", "pasiva")) < eventos.index(("COMMIT PREPARED", "primaria"))
    assert eventos.index(("PREPARE TRANSACTION", "pasiva")) < eventos.index(("PREPARE TRANSACTION", "primaria"))
    assert _cuenta(bases_limpias.viajes_primaria) == _cuenta(bases_limpias.viajes_pasiva) == 1


def test_fallo_de_la_pasiva_deja_la_primaria_sin_cambios(bases_limpias):
    base = _base(bases_limpias, [], falla_pasiva="PREPARE TRANSACTION")
    with pytest.raises(ErrorBaseNoDisponible):
        base.escribir(_alta)
    assert _cuenta(bases_limpias.viajes_primaria) == _cuenta(bases_limpias.viajes_pasiva) == 0
    with conectar(bases_limpias.viajes_primaria) as c:
        assert c.execute("SELECT count(*) FROM pg_prepared_xacts").fetchone()[0] == 0
    assert not base.conmutada  # un fallo de la pasiva no es caída de la primaria


def test_fallo_al_preparar_la_primaria_revierte_la_pasiva_ya_preparada(bases_limpias):
    eventos = []
    base = BaseViajes(
        lambda: Espia(conectar(bases_limpias.viajes_primaria, autocommit=True), "primaria",
                      eventos, "PREPARE TRANSACTION"),
        lambda: Espia(conectar(bases_limpias.viajes_pasiva, autocommit=True), "pasiva", eventos),
    )
    with pytest.raises(ErrorBaseNoDisponible):
        base.escribir(_alta)
    assert ("PREPARE TRANSACTION", "pasiva") in eventos
    for dsn in (bases_limpias.viajes_primaria, bases_limpias.viajes_pasiva):
        assert _cuenta(dsn) == 0
        with conectar(dsn) as c:
            assert c.execute("SELECT count(*) FROM pg_prepared_xacts").fetchone()[0] == 0
