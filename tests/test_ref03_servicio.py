# SPEC: SPEC-REF-03
# ELEMENTO PASO 5: Orquestador de viajes, whitelist y Mensajes en revisión (ITERACION_3)
# ADRs: ADR-IT3-008
# DRIVERS: REF-03, QA-SEG-03*
from datetime import timedelta

import pytest

from tests.ref03_util import AHORA, reserva_norm
from trotamundos.config import ConfiguracionRevision
from trotamundos.dominio.puertos_correo import ResultadoRetencion
from trotamundos.orquestador.revision import ErrorMensajeNoEncontrado, ServicioRevision
from trotamundos.persistencia.base_viajes import BaseViajes
from trotamundos.persistencia.repositorio_revision import RepositorioRevision

pytestmark = pytest.mark.db


class LiberadorEspia:
    def __init__(self, falla=False):
        self.liberadas, self.falla = [], falla

    async def liberar(self, reservas):
        if self.falla:
            raise RuntimeError("la ingesta no responde")
        self.liberadas.extend(reservas)


@pytest.fixture
def liberador():
    return LiberadorEspia()


@pytest.fixture
def servicio(bases_limpias, liberador):
    cfg = ConfiguracionRevision(tope_pendientes=50)
    repo = RepositorioRevision(BaseViajes.desde_config(bases_limpias), cfg.tope_pendientes)
    return ServicioRevision(repo, cfg, liberador=liberador, reloj=lambda: AHORA)


async def test_AC_REF_03_03_aprobar_remitente_libera_la_reserva_retenida(servicio, liberador):
    assert await servicio.retener(reserva_norm()) is ResultadoRetencion.RETENIDA
    assert not await servicio.remitente_seguro("t1", "agencia@x.com")
    assert await servicio.aprobar("t1", "agencia@x.com") == 1
    assert await servicio.remitente_seguro("t1", "agencia@x.com")
    assert [r.id_mensaje for r in liberador.liberadas] == ["<m1@x>"]
    assert await servicio.consultar("t1") == []  # ya no está pendiente


async def test_AC_REF_03_08_alta_directa_del_remitente_libera_la_reserva(servicio, liberador):
    await servicio.retener(reserva_norm(remitente="Agencia@X.com"))
    # el titular da de alta el remitente a mano, sin elegir el mensaje: mismo resultado
    await servicio.aprobar("t1", "agencia@x.com")
    assert await servicio.remitente_seguro("t1", "agencia@x.com")
    assert [r.id_mensaje for r in liberador.liberadas] == ["<m1@x>"]


async def test_aprobar_libera_todos_los_pendientes_de_ese_remitente_y_solo_esos(servicio, liberador):
    await servicio.retener(reserva_norm("<a@x>", remitente="uno@x.com"))
    await servicio.retener(reserva_norm("<b@x>", remitente="uno@x.com"))
    await servicio.retener(reserva_norm("<c@x>", remitente="dos@x.com"))
    assert await servicio.aprobar("t1", "uno@x.com") == 2
    assert {r.id_mensaje for r in liberador.liberadas} == {"<a@x>", "<b@x>"}
    assert [m.id_mensaje for m in await servicio.consultar("t1")] == ["<c@x>"]


async def test_aprobar_un_remitente_ya_aprobado_no_es_error_ni_libera_dos_veces(servicio, liberador):
    await servicio.retener(reserva_norm())
    await servicio.aprobar("t1", "agencia@x.com")
    assert await servicio.aprobar("t1", "agencia@x.com") == 0
    assert len(liberador.liberadas) == 1


async def test_si_la_liberacion_falla_el_mensaje_no_se_pierde_y_aprobar_de_nuevo_reintenta(
        servicio, liberador):
    await servicio.retener(reserva_norm())
    liberador.falla = True
    with pytest.raises(RuntimeError):
        await servicio.aprobar("t1", "agencia@x.com")
    assert len(await servicio.consultar("t1")) == 1  # sigue pendiente
    liberador.falla = False
    assert await servicio.aprobar("t1", "agencia@x.com") == 1
    assert await servicio.consultar("t1") == []


async def test_AC_REF_03_09_quitar_remitente_manda_lo_nuevo_a_revision(servicio, liberador):
    await servicio.aprobar("t1", "agencia@x.com")
    await servicio.quitar("t1", "agencia@x.com")
    await servicio.quitar("t1", "agencia@x.com")  # ya no está: no es error
    assert not await servicio.remitente_seguro("t1", "agencia@x.com")
    assert await servicio.retener(reserva_norm("<nuevo@x>")) is ResultadoRetencion.RETENIDA
    assert [m.id_mensaje for m in await servicio.consultar("t1")] == ["<nuevo@x>"]


async def test_AC_REF_03_10_sin_mensajes_en_revision_devuelve_lista_vacia(servicio):
    assert await servicio.consultar("t1") == []


async def test_AC_REF_03_12_descartar_inexistente_o_ajeno_se_rechaza_sin_cambios(servicio):
    await servicio.retener(reserva_norm())
    with pytest.raises(ErrorMensajeNoEncontrado):
        await servicio.descartar("t1", "<no-existe@x>")
    with pytest.raises(ErrorMensajeNoEncontrado):
        await servicio.descartar("otro", "<m1@x>")
    assert len(await servicio.consultar("t1")) == 1
    await servicio.descartar("t1", "<m1@x>")
    with pytest.raises(ErrorMensajeNoEncontrado):  # ya resuelto
        await servicio.descartar("t1", "<m1@x>")


async def test_descartar_no_bloquea_al_remitente(servicio):
    await servicio.retener(reserva_norm("<a@x>"))
    await servicio.descartar("t1", "<a@x>")
    assert not await servicio.remitente_seguro("t1", "agencia@x.com")
    assert await servicio.retener(reserva_norm("<b@x>")) is ResultadoRetencion.RETENIDA


async def test_AC_REF_03_11_purga_elimina_lo_que_cumplio_la_retencion(servicio):
    await servicio.retener(reserva_norm())
    assert await servicio.purgar(AHORA + timedelta(days=29)) == 0
    assert await servicio.purgar(AHORA + timedelta(days=31)) == 1
    assert await servicio.consultar("t1") == []
