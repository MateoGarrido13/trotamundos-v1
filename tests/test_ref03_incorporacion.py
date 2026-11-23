# SPEC: SPEC-REF-03
# ELEMENTO PASO 5: Orquestador de viajes (ITERACION_3)
# ADRs: ADR-IT3-003, ADR-IT2-004
# DRIVERS: REF-03, QA-SEG-03*
from datetime import datetime

import pytest

from tests.ref03_util import reserva_norm
from trotamundos.dominio.registro_tipos import ErrorRegistroTipos, RegistroTipos
from trotamundos.dominio.tipos_reserva import ReservaHotel
from trotamundos.orquestador.arranque import registrar_tipos
from trotamundos.orquestador.incorporacion import IncorporadorReservas
from trotamundos.persistencia.base_viajes import BaseViajes
from trotamundos.persistencia.conexion import conectar
from trotamundos.persistencia.repositorio_viajes import RepositorioViajes

pytestmark = pytest.mark.db


@pytest.fixture
def repo(bases_limpias):
    registro = RegistroTipos()
    registrar_tipos(registro)
    return RepositorioViajes(BaseViajes.desde_config(bases_limpias), registro)


@pytest.fixture
def incorporador(repo):
    return IncorporadorReservas(repo, repo._registro)


async def test_la_reserva_del_correo_entra_al_itinerario_del_titular(incorporador, repo):
    await incorporador.incorporar(reserva_norm())
    [viaje] = repo.listar_viajes("t1", "activo")
    [reserva] = repo.reservas_de([viaje.id])
    assert type(reserva) is ReservaHotel  # la clase sale del Registro, no de un if
    assert (reserva.identificador, reserva.lugar, reserva.codigo) == ("t1:<m1@x>", "Roma", "H-1")
    assert reserva.inicio == datetime(2026, 12, 1, 10)
    assert repo.listar_viajes("otro", "activo") == []  # solo en el itinerario del titular


async def test_AC_REF_03_13_entregar_dos_veces_la_misma_reserva_deja_una(incorporador, repo, bases_limpias):
    await incorporador.incorporar(reserva_norm())
    await incorporador.incorporar(reserva_norm())  # reintento tras un timeout
    for dsn in (bases_limpias.viajes_primaria, bases_limpias.viajes_pasiva):
        with conectar(dsn) as c:
            assert c.execute("SELECT count(*) FROM reserva").fetchone()[0] == 1
            assert c.execute("SELECT count(*) FROM viaje").fetchone()[0] == 1


async def test_el_mismo_correo_de_dos_titulares_son_dos_reservas(incorporador, repo):
    await incorporador.incorporar(reserva_norm(titular="t1"))
    await incorporador.incorporar(reserva_norm(titular="t2"))
    assert len(repo.listar_viajes("t1", "activo")) == 1
    assert len(repo.listar_viajes("t2", "activo")) == 1


async def test_un_tipo_desconocido_hace_fallar_la_entrega(incorporador, repo):
    with pytest.raises(ErrorRegistroTipos):
        await incorporador.incorporar(reserva_norm(tipo="cohete"))
    assert repo.listar_viajes("t1", "activo") == []  # no se guardó nada


async def test_la_agrupacion_de_reservas_del_correo_no_conoce_los_tipos(incorporador, repo):
    from trotamundos.orquestador.agrupacion import Agrupacion
    await incorporador.incorporar(reserva_norm("<a@x>", tipo="vuelo", lugar="Lima"))
    await incorporador.incorporar(reserva_norm("<b@x>", tipo="tren", lugar="Cusco"))
    viajes = Agrupacion(repo).vista_principal("t1")
    assert sorted(len(v.reservas) for v in viajes) == [1, 1]
