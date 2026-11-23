"""Ayudas compartidas de los tests de SPEC-REF-05."""
import pytest

from tests.ref04_util import ANA, INTRUSO, ITIN, LUIS, precargar, solicitud
from trotamundos.app import create_app
from trotamundos.broker import NombreCola
from trotamundos.config import Configuracion, ConfiguracionAgencias, ConfiguracionBroker

CLAVE_AGENCIA = "clave-compartida"
AGENCIAS = ("agencia-a", "agencia-b")


async def sin_espera(_s):
    return None


@pytest.fixture
def app(bases_limpias):
    """Colas de 5 y backoff 1 s, como las specs para los tests; sin esperar tiempo real."""
    cfg = Configuracion(
        bases=bases_limpias,
        broker=ConfiguracionBroker(tamano_maximo_cola=5, reintentos=3, backoff_base_segundos=1.0),
        agencias=ConfiguracionAgencias(disponibles=AGENCIAS, clave_aviso=CLAVE_AGENCIA))
    app = create_app(cfg)
    precargar(app)
    app.state.broker._dormir = sin_espera
    app.state.casos._dormir = sin_espera
    return app


async def reserva_de(app, actor=LUIS, clave="alta-reserva", viaje="roma"):
    """Una reserva en el itinerario compartido; devuelve su identificador."""
    r = await app.state.gestion.agregar(actor, ITIN, clave, solicitud(viaje_id=viaje))
    assert r.estado == "ok"
    return r.reserva["identificador"]


async def con_agencia(app, actor=LUIS, agencia="agencia-a"):
    r = await app.state.casos.elegir_agencia(actor, agencia, True)
    assert r.estado == "ok"


def pedido_en_cola(app, indice=0):
    return list(app.state.broker._colas[NombreCola.CASOS_AYUDA])[indice]


def llenar_cola_de_casos(app):
    """Deja la cola de casos de ayuda sin lugar (5 en los tests)."""
    from trotamundos.broker import Mensaje
    for i in range(5):
        app.state.broker.publicar(NombreCola.CASOS_AYUDA, Mensaje(f"relleno-{i}", {}))


def vaciar_un_lugar(app):
    app.state.broker._colas[NombreCola.CASOS_AYUDA].popleft()


def estado_del_caso(app, caso_id):
    from trotamundos.persistencia.repositorio_casos import RepositorioCasos
    return app.state.base_viajes.leer(lambda c: RepositorioCasos.caso(c, caso_id)).estado
