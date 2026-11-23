# SPEC: SPEC-REF-03
# ELEMENTO PASO 5: Adaptador de correo -> Parseo -> Filtro -> Ingesta -> Orquestador (ITERACION_3)
# ADRs: ADR-IT3-008, ADR-IT3-003, ADR-IT3-006, ADR-IT3-007
# DRIVERS: REF-03, REF-02, QA-SEG-03*
"""T-REF-03-08: el camino completo del correo hasta el itinerario real en PostgreSQL, con el
Parseo aislado como proceso del sistema operativo."""
import json
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from trotamundos.app import create_app
from trotamundos.broker import NombreCola, ResultadoEntrega
from trotamundos.config import Configuracion, ConfiguracionCorreo
from trotamundos.entrada.adaptador_correo import AdaptadorCorreo
from trotamundos.entrada.api_correo import CorreoCrudo, MockApiCorreo
from trotamundos.entrada.consumidor_correo import ConsumidorCorreo
from trotamundos.entrada.gestor_autorizacion import (
    CifradorTokens,
    GestorAutorizacion,
    RepositorioTokensPostgres,
)
from trotamundos.entrada.parseo_aislado.cliente import ClienteParseo

pytestmark = pytest.mark.db

AGENCIA = "agencia@x.com"


def correo(message_id="<m1@x>", remitente=AGENCIA, lugar="Roma"):
    cuerpo = json.dumps({"tipo": "hotel", "inicio": "2026-12-01T10:00:00",
                         "fin": "2026-12-05T10:00:00", "lugar": lugar, "codigo": "H-1"})
    return CorreoCrudo(cuerpo=cuerpo, remitente=remitente, message_id=message_id,
                       recibido=datetime.now(UTC) - timedelta(days=1))


class Sistema:
    """El sistema armado: lo único simulado es la API de correo."""

    def __init__(self, app, parseo):
        self.app = app
        self.api = MockApiCorreo()
        self.api.emitir_token("t1", "tok")
        cfg = ConfiguracionCorreo()
        self.gestor = GestorAutorizacion(
            RepositorioTokensPostgres(app.state.base_viajes), CifradorTokens(Fernet.generate_key()), cfg)
        self.gestor.autorizar("t1", "tok")
        self.adaptador = AdaptadorCorreo(self.api, self.gestor, app.state.broker, cfg)
        self.nodos = app.state.nodos_correo
        self.consumidor = ConsumidorCorreo(app.state.broker, parseo, self.nodos.filtro)
        self.revision = app.state.servicio_revision

    async def sondear_y_procesar(self):
        await self.adaptador.sondear("t1")
        await self.drenar()

    async def drenar(self):
        while await self.consumidor.procesar_uno() is not ResultadoEntrega.VACIA:
            pass
        while await self.nodos.ingesta.procesar_uno() is not ResultadoEntrega.VACIA:
            pass

    def reservas(self):
        repo = self.app.state.repositorio
        viajes = [v.id for v in repo.listar_viajes("t1", "activo")]
        return repo.reservas_de(viajes)


@pytest.fixture
async def sistema(bases_limpias):
    app = create_app(Configuracion(bases=bases_limpias))
    parseo = ClienteParseo()
    try:
        yield Sistema(app, parseo)
    finally:
        await parseo.cerrar()


async def test_AC_REF_03_16_tres_sondeos_del_mismo_mensaje_dejan_una_sola_reserva(sistema):
    await sistema.revision.aprobar("t1", AGENCIA)  # remitente seguro
    sistema.api.agregar_correo("t1", correo())
    for _ in range(3):  # el buzón sigue dentro de la ventana en tres sondeos seguidos
        await sistema.sondear_y_procesar()
    [reserva] = sistema.reservas()
    assert (reserva.identificador, reserva.lugar, reserva.codigo) == ("t1:<m1@x>", "Roma", "H-1")
    assert sistema.app.state.broker.mensajes_muertos(NombreCola.NOVEDADES) == []


async def test_AC_REF_03_01_remitente_seguro_entra_al_itinerario_de_punta_a_punta(sistema):
    await sistema.revision.aprobar("t1", AGENCIA)
    sistema.api.agregar_correo("t1", correo())
    await sistema.sondear_y_procesar()
    assert [r.lugar for r in sistema.reservas()] == ["Roma"]
    assert await sistema.revision.consultar("t1") == []


async def test_AC_REF_03_02_y_03_desconocido_espera_y_al_aprobar_entra_al_itinerario(sistema):
    sistema.api.agregar_correo("t1", correo())
    await sistema.sondear_y_procesar()
    assert sistema.reservas() == []  # no está en el itinerario hasta que el titular actúa
    [pendiente] = await sistema.revision.consultar("t1")
    assert pendiente.remitente == AGENCIA
    # el mismo mensaje se relee en otro sondeo: sigue habiendo una sola entrada en revisión
    await sistema.sondear_y_procesar()
    assert len(await sistema.revision.consultar("t1")) == 1

    assert await sistema.revision.aprobar("t1", AGENCIA) == 1
    await sistema.drenar()
    assert [r.lugar for r in sistema.reservas()] == ["Roma"]
    assert await sistema.revision.consultar("t1") == []
    # sondeos posteriores ya no la duplican, ni en revisión ni en el itinerario
    await sistema.sondear_y_procesar()
    assert len(sistema.reservas()) == 1 and await sistema.revision.consultar("t1") == []


async def test_AC_REF_03_09_quitar_remitente_manda_lo_nuevo_a_revision_y_conserva_lo_incorporado(sistema):
    await sistema.revision.aprobar("t1", AGENCIA)
    sistema.api.agregar_correo("t1", correo("<viejo@x>", lugar="Roma"))
    await sistema.sondear_y_procesar()
    assert len(sistema.reservas()) == 1

    await sistema.revision.quitar("t1", AGENCIA)
    sistema.api.agregar_correo("t1", correo("<nuevo@x>", lugar="Lima"))
    await sistema.sondear_y_procesar()

    assert [m.id_mensaje for m in await sistema.revision.consultar("t1")] == ["<nuevo@x>"]
    assert [r.lugar for r in sistema.reservas()] == ["Roma"]  # la incorporada permanece


async def test_descartar_un_mensaje_no_reaparece_en_sondeos_posteriores(sistema):
    sistema.api.agregar_correo("t1", correo())
    await sistema.sondear_y_procesar()
    await sistema.revision.descartar("t1", "<m1@x>")
    await sistema.sondear_y_procesar()
    assert await sistema.revision.consultar("t1") == []
    assert sistema.reservas() == []


async def test_un_tipo_desconocido_no_se_pierde_en_silencio(sistema):
    cuerpo = json.dumps({"tipo": "cohete", "inicio": "2026-12-01T10:00:00",
                         "fin": "2026-12-05T10:00:00", "lugar": "Luna", "codigo": "C-1"})
    await sistema.revision.aprobar("t1", AGENCIA)
    sistema.api.agregar_correo("t1", CorreoCrudo(
        cuerpo=cuerpo, remitente=AGENCIA, message_id="<cohete@x>",
        recibido=datetime.now(UTC) - timedelta(days=1)))

    async def sin_espera(_s):
        return None
    sistema.app.state.broker._dormir = sin_espera
    await sistema.sondear_y_procesar()
    assert sistema.reservas() == []
    assert [m.id for m in sistema.app.state.broker.mensajes_muertos(NombreCola.NOVEDADES)] == ["t1:<cohete@x>"]
