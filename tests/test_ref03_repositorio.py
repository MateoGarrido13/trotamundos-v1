# SPEC: SPEC-REF-03
# ELEMENTO PASO 5: Orquestador de viajes, whitelist y Mensajes en revisión (ITERACION_3)
# ADRs: ADR-IT3-008, ADR-IT2-004
# DRIVERS: REF-03, QA-SEG-03*
from datetime import timedelta

import pytest

from tests.ref03_util import AHORA, reserva_norm
from trotamundos.dominio.puertos_correo import ResultadoRetencion
from trotamundos.persistencia.base_viajes import BaseViajes
from trotamundos.persistencia.conexion import conectar
from trotamundos.persistencia.repositorio_revision import RepositorioRevision

pytestmark = pytest.mark.db


@pytest.fixture
def repo(bases_limpias):
    return RepositorioRevision(BaseViajes.desde_config(bases_limpias), tope_pendientes=3)


def test_whitelist_agregar_quitar_y_normalizar(repo):
    assert not repo.es_seguro("t1", "agencia@x.com")
    repo.agregar_remitente("t1", " Agencia@X.com ")
    repo.agregar_remitente("t1", "agencia@x.com")  # ya aprobado: no cambia nada, no es error
    assert repo.es_seguro("t1", "AGENCIA@x.com")
    assert not repo.es_seguro("t2", "agencia@x.com")  # la whitelist es de cada titular
    repo.quitar_remitente("t1", "agencia@x.com")
    repo.quitar_remitente("t1", "agencia@x.com")  # no está: no es error
    assert not repo.es_seguro("t1", "agencia@x.com")


def test_escrituras_de_revision_quedan_en_primaria_y_pasiva(repo, bases_limpias):
    repo.agregar_remitente("t1", "a@x.com")
    repo.retener(reserva_norm(), AHORA)
    for dsn in (bases_limpias.viajes_primaria, bases_limpias.viajes_pasiva):
        with conectar(dsn) as c:
            assert c.execute("SELECT count(*) FROM remitente_seguro").fetchone()[0] == 1
            assert c.execute("SELECT count(*) FROM mensaje_revision").fetchone()[0] == 1


def test_AC_REF_03_05_mismo_mensaje_deja_una_sola_entrada_en_revision(repo):
    assert repo.retener(reserva_norm(), AHORA) is ResultadoRetencion.RETENIDA
    assert repo.retener(reserva_norm(), AHORA + timedelta(minutes=15)) is ResultadoRetencion.DUPLICADA
    assert repo.retener(reserva_norm(), AHORA + timedelta(minutes=30)) is ResultadoRetencion.DUPLICADA
    assert [m.id_mensaje for m in repo.pendientes("t1")] == ["<m1@x>"]


def test_AC_REF_03_06_tope_alcanzado_no_retiene_ni_pierde(repo):
    for i in range(3):
        assert repo.retener(reserva_norm(f"<m{i}@x>"), AHORA) is ResultadoRetencion.RETENIDA
    assert repo.retener(reserva_norm("<m3@x>"), AHORA) is ResultadoRetencion.TOPE_ALCANZADO
    assert len(repo.pendientes("t1")) == 3  # no se retuvo
    # otro titular no se ve afectado por el tope de t1
    assert repo.retener(reserva_norm("<m3@x>", titular="t2"), AHORA) is ResultadoRetencion.RETENIDA
    # al liberar lugar, el mismo mensaje se puede retener en un sondeo posterior
    repo.borrar("t1", ["<m0@x>"])
    assert repo.retener(reserva_norm("<m3@x>"), AHORA) is ResultadoRetencion.RETENIDA


def test_AC_REF_03_07_descartado_no_reaparece_en_pendientes(repo):
    repo.retener(reserva_norm(), AHORA)
    assert repo.descartar("t1", "<m1@x>") is True
    assert repo.pendientes("t1") == []
    # el mismo mensaje llega de nuevo en un sondeo posterior: sigue sin aparecer
    assert repo.retener(reserva_norm(), AHORA + timedelta(minutes=15)) is ResultadoRetencion.DUPLICADA
    assert repo.pendientes("t1") == []


def test_descartado_no_cuenta_para_el_tope_y_no_guarda_la_reserva(repo, bases_limpias):
    for i in range(3):
        repo.retener(reserva_norm(f"<m{i}@x>"), AHORA)
    repo.descartar("t1", "<m0@x>")
    assert repo.retener(reserva_norm("<m9@x>"), AHORA) is ResultadoRetencion.RETENIDA
    with conectar(bases_limpias.viajes_primaria) as c:
        [(datos,)] = c.execute(
            "SELECT reserva FROM mensaje_revision WHERE id_mensaje = '<m0@x>'").fetchall()
    assert datos == {}  # solo conserva su identificador y su fecha


def test_AC_REF_03_11_mensaje_vencido_se_elimina_de_revision(repo, bases_limpias):
    repo.retener(reserva_norm("<viejo@x>"), AHORA - timedelta(days=31))
    repo.retener(reserva_norm("<reciente@x>"), AHORA - timedelta(days=1))
    repo.retener(reserva_norm("<descartado@x>"), AHORA - timedelta(days=40))
    repo.descartar("t1", "<descartado@x>")
    assert repo.purgar(AHORA - timedelta(days=30)) == 2  # el viejo y el descartado vencido
    assert [m.id_mensaje for m in repo.pendientes("t1")] == ["<reciente@x>"]
    for dsn in (bases_limpias.viajes_primaria, bases_limpias.viajes_pasiva):
        with conectar(dsn) as c:
            assert c.execute("SELECT count(*) FROM mensaje_revision").fetchone()[0] == 1


def test_descartar_inexistente_ajeno_o_resuelto_no_cambia_nada(repo):
    repo.retener(reserva_norm(), AHORA)
    assert repo.descartar("t1", "<no-existe@x>") is False
    assert repo.descartar("otro-titular", "<m1@x>") is False
    assert len(repo.pendientes("t1")) == 1
    assert repo.descartar("t1", "<m1@x>") is True
    assert repo.descartar("t1", "<m1@x>") is False  # ya resuelto


def test_pendientes_de_un_remitente_y_resumen(repo):
    repo.retener(reserva_norm("<a@x>", remitente="Uno@x.com"), AHORA)
    repo.retener(reserva_norm("<b@x>", remitente="dos@x.com"), AHORA)
    [m] = repo.pendientes_de("t1", "uno@x.com")
    assert m.id_mensaje == "<a@x>" and m.remitente == "uno@x.com"
    assert m.reserva.remitente == "Uno@x.com"  # la reserva conserva el remitente original
    assert m.resumen == "hotel en Roma (2026-12-01 a 2026-12-05)"


def test_un_mensaje_ya_incorporado_al_itinerario_no_vuelve_a_revision(repo, bases_limpias):
    from trotamundos.dominio.registro_tipos import RegistroTipos
    from trotamundos.orquestador.arranque import registrar_tipos
    from trotamundos.orquestador.incorporacion import IncorporadorReservas
    from trotamundos.persistencia.repositorio_viajes import RepositorioViajes
    import asyncio

    registro = RegistroTipos()
    registrar_tipos(registro)
    viajes = RepositorioViajes(BaseViajes.desde_config(bases_limpias), registro)
    asyncio.run(IncorporadorReservas(viajes, registro).incorporar(reserva_norm("<ya@x>")))
    assert repo.retener(reserva_norm("<ya@x>"), AHORA) is ResultadoRetencion.DUPLICADA
    assert repo.pendientes("t1") == []
    # el mismo Message-ID de otro titular sí es otro mensaje
    assert repo.retener(reserva_norm("<ya@x>", titular="t2"), AHORA) is ResultadoRetencion.RETENIDA
