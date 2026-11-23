# SPEC: SPEC-REF-04
# ELEMENTO PASO 5: Contrato `Reserva` y baja lógica (ITERACION_4)
# ADRs: ADR-IT4-008, ADR-IT4-009
# DRIVERS: REF-04
"""T-REF-04-01: modelo ampliado (origen, creado_por, baja lógica, itinerario)."""
from datetime import UTC, datetime

import pytest

from tests.ref03_util import reserva_norm
from trotamundos.app import create_app
from trotamundos.config import Configuracion
from trotamundos.dominio.reserva import Origen
from trotamundos.dominio.tipos_reserva import ReservaActividad, ReservaHotel
from trotamundos.orquestador.agrupacion import Agrupacion
from trotamundos.orquestador.archivado import archivar_completados
from trotamundos.orquestador.incorporacion import IncorporadorReservas
from trotamundos.persistencia.conexion import conectar

pytestmark = pytest.mark.db
DIAS = dict(inicio=datetime(2026, 12, 1, 8), fin=datetime(2026, 12, 3, 8))


@pytest.fixture
def app(bases_limpias):
    return create_app(Configuracion(bases=bases_limpias))


def dar_de_baja(bases, reserva_id):
    for dsn in (bases.viajes_primaria, bases.viajes_pasiva):
        with conectar(dsn, autocommit=True) as c:
            c.execute("UPDATE reserva SET baja_en = now() WHERE identificador = %s", (reserva_id,))


def test_actividad_es_un_tipo_mas_del_registro(app):
    assert app.state.registro_tipos.clase_de("actividad") is ReservaActividad
    assert ReservaActividad(identificador="a", viaje_id="v", **DIAS).resumen() == "Actividad (a)"


def test_las_altas_de_viaje_fijan_el_itinerario_individual(app, bases_limpias):
    app.state.repositorio.insertar_viaje("v1", "ana")
    with conectar(bases_limpias.viajes_primaria) as c:
        assert c.execute("SELECT itinerario_id FROM viaje WHERE id = 'v1'").fetchone()[0] == "ana"


async def test_la_reserva_del_correo_lleva_origen_correo_y_sin_creador(app):
    await IncorporadorReservas(app.state.repositorio, app.state.registro_tipos).incorporar(reserva_norm())
    repo = app.state.repositorio
    [viaje] = repo.listar_viajes("t1", "activo")
    [reserva] = repo.reservas_de([viaje.id])
    assert (reserva.origen, reserva.creado_por) == (Origen.CORREO, None)
    assert reserva.editada_manualmente is False and reserva.baja_en is None


def test_origen_y_creador_hacen_ida_y_vuelta(app):
    repo = app.state.repositorio
    repo.insertar_viaje("v1", "ana")
    repo.insertar_reserva(ReservaHotel(identificador="r1", viaje_id="v1", origen=Origen.MANUAL,
                                       creado_por="ana", **DIAS))
    [reserva] = repo.reservas_de(["v1"])
    assert (reserva.origen, reserva.creado_por) == (Origen.MANUAL, "ana")


def test_AC_REF_04_03_una_reserva_en_baja_no_aparece_en_la_vista_pero_se_conserva(app, bases_limpias):
    repo = app.state.repositorio
    repo.insertar_viaje("v1", "ana")
    for ident in ("r1", "r2"):
        repo.insertar_reserva(ReservaHotel(identificador=ident, viaje_id="v1", **DIAS))
    dar_de_baja(bases_limpias, "r1")
    [viaje] = Agrupacion(repo).vista_principal("ana")
    assert [r.identificador for r in viaje.reservas] == ["r2"]
    with conectar(bases_limpias.viajes_primaria) as c:  # sigue disponible para el historial
        assert c.execute("SELECT count(*) FROM reserva").fetchone()[0] == 2


def test_las_bajas_no_cuentan_para_cerrar_un_viaje(app, bases_limpias):
    repo = app.state.repositorio
    repo.insertar_viaje("completo", "ana")
    repo.insertar_reserva(ReservaHotel(identificador="a", viaje_id="completo", **DIAS))
    repo.insertar_reserva(ReservaHotel(identificador="b", viaje_id="completo",
                                       inicio=datetime(2027, 6, 1), fin=datetime(2027, 6, 9)))
    dar_de_baja(bases_limpias, "b")  # lo único que seguía vigente a futuro está en baja
    repo.insertar_viaje("vacio", "ana")
    repo.insertar_reserva(ReservaHotel(identificador="c", viaje_id="vacio", **DIAS))
    dar_de_baja(bases_limpias, "c")  # todo en baja: no hay reservas vigentes
    ahora = datetime(2026, 12, 31, tzinfo=UTC)
    assert archivar_completados(repo, ahora) == ["completo"]
