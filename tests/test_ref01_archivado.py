# SPEC: SPEC-REF-01
# ELEMENTO PASO 5: Orquestador de viajes, archivado automático por fecha (ITERACION_1)
# ADRs: ADR-IT2-004
# DRIVERS: REF-01, QA-DIS-01
import asyncio
from datetime import datetime

import pytest

from trotamundos.app import create_app
from trotamundos.config import Configuracion
from trotamundos.dominio.tipos_reserva import ReservaHotel
from trotamundos.orquestador.agrupacion import Agrupacion
from trotamundos.orquestador.archivado import archivar_completados, tarea_periodica
from trotamundos.persistencia.conexion import conectar

pytestmark = pytest.mark.db


def _hotel(ident, viaje, fin):
    return ReservaHotel(identificador=ident, viaje_id=viaje, inicio=datetime(2026, 12, 1), fin=fin)


def _repo(cfg):
    return create_app(Configuracion(bases=cfg)).state.repositorio


def test_AC_REF_01_02_archivado_saca_viaje_completo_de_vista_principal(bases_limpias):
    repo = _repo(bases_limpias)
    for v in ("completo", "en_curso", "vacio"):
        repo.insertar_viaje(v, "ana")
    repo.insertar_reserva(_hotel("r1", "completo", datetime(2026, 12, 5)))
    repo.insertar_reserva(_hotel("r2", "completo", datetime(2026, 12, 8)))
    repo.insertar_reserva(_hotel("r3", "en_curso", datetime(2026, 12, 8)))
    repo.insertar_reserva(_hotel("r4", "en_curso", datetime(2027, 1, 20)))
    ahora = datetime(2026, 12, 10)

    assert archivar_completados(repo, ahora) == ["completo"]

    ag = Agrupacion(repo)
    assert [v.id for v in ag.vista_principal("ana")] == ["en_curso", "vacio"]
    [archivado] = ag.archivados("ana")
    assert archivado.id == "completo" and len(archivado.reservas) == 2  # no se elimina
    # la escritura pasó por 2PC: las dos bases quedaron iguales
    for dsn in (bases_limpias.viajes_primaria, bases_limpias.viajes_pasiva):
        with conectar(dsn) as c:
            assert c.execute("SELECT estado FROM viaje WHERE id = 'completo'").fetchone()[0] == "archivado"
    assert archivar_completados(repo, ahora) == []  # idempotente


async def test_tarea_periodica_archiva_con_reloj_inyectado(bases_limpias):
    repo = _repo(bases_limpias)
    repo.insertar_viaje("v1", "ana")
    repo.insertar_reserva(_hotel("r1", "v1", datetime(2026, 12, 5)))
    tarea = asyncio.create_task(tarea_periodica(repo, 0.01, reloj=lambda: datetime(2026, 12, 10)))
    for _ in range(100):
        await asyncio.sleep(0.05)
        if Agrupacion(repo).archivados("ana"):
            break
    tarea.cancel()
    assert [v.id for v in Agrupacion(repo).archivados("ana")] == ["v1"]
