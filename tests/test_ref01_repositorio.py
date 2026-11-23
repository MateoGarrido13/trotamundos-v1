# SPEC: SPEC-REF-01
# ELEMENTO PASO 5: Acceso a viajes y reservas (ITERACION_1)
# ADRs: ADR-IT3-005, ADR-IT2-004
# DRIVERS: REF-01
from datetime import datetime

import pytest

from trotamundos.config import Configuracion
from trotamundos.dominio.tipos_reserva import ReservaVuelo
from trotamundos.app import create_app
from trotamundos.persistencia.conexion import conectar

pytestmark = pytest.mark.db


def test_repositorio_ida_y_vuelta_hidrata_clase_concreta(bases_limpias):
    app = create_app(Configuracion(bases=bases_limpias))
    repo = app.state.repositorio
    repo.insertar_viaje("v1", "ana")
    repo.insertar_reserva(ReservaVuelo(identificador="r1", viaje_id="v1", lugar="Lima",
                                       inicio=datetime(2026, 12, 1, 8), fin=datetime(2026, 12, 1, 12)))
    [viaje] = repo.listar_viajes("ana", "activo")
    [reserva] = repo.reservas_de([viaje.id])
    assert type(reserva) is ReservaVuelo and reserva.lugar == "Lima"
    assert reserva.inicio == datetime(2026, 12, 1, 8)
    # la escritura quedó en las dos bases
    for dsn in (bases_limpias.viajes_primaria, bases_limpias.viajes_pasiva):
        with conectar(dsn) as c:
            assert c.execute("SELECT count(*) FROM reserva").fetchone()[0] == 1
