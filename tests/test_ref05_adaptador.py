# SPEC: SPEC-REF-05
# ELEMENTO PASO 5: Adaptador de agencia, IAgencia, cola de casos de ayuda (ITERACION_4)
# ADRs: ADR-IT4-010, ADR-IT3-003
# DRIVERS: REF-05, CON-02
"""T-REF-05-05: el Adaptador de agencia con un Broker real y agencias simuladas (sin base)."""
import pytest

from trotamundos.broker import Aviso, Broker, ColaLlena, Mensaje, NombreCola, ResultadoEntrega
from trotamundos.config import ConfiguracionAgencias
from trotamundos.dominio.agencias import PedidoCaso
from trotamundos.entrada.agencia import AdaptadorAgencia, MockAgencia


def pedido(id_caso="caso-1", agencia="agencia-a", resumen=None) -> Mensaje:
    p = PedidoCaso(id_caso=id_caso, agencia=agencia, descripcion="No tengo habitación",
                   reserva={"identificador": "r1", "tipo": "hotel", "lugar": "Roma",
                            "inicio": "2026-12-01T10:00:00", "fin": "2026-12-05T10:00:00"},
                   resumen_dialogo=resumen)
    return Mensaje(id_caso, p.model_dump(mode="json"))


class Reloj:
    def __init__(self):
        self.esperas: list[float] = []

    async def dormir(self, s):
        self.esperas.append(s)


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def avisos():
    return []


@pytest.fixture
def broker(cfg_broker, reloj, avisos):
    return Broker(cfg_broker, avisar=avisos.append, dormir=reloj.dormir)


@pytest.fixture
def agencia_a():
    return MockAgencia("agencia-a")


@pytest.fixture
def adaptador(broker, agencia_a, reloj):
    return AdaptadorAgencia(broker, {"agencia-a": agencia_a}, ConfiguracionAgencias(), dormir=reloj.dormir)


def novedades(broker):
    return [(m.id, m.cuerpo) for m in broker._colas[NombreCola.NOVEDADES]]


async def test_AC_REF_05_02_el_adaptador_consume_la_cola_y_llama_a_abrir_caso(broker, adaptador, agencia_a):
    broker.publicar(NombreCola.CASOS_AYUDA, pedido())
    assert await adaptador.procesar_uno() is ResultadoEntrega.ENTREGADO
    assert agencia_a.llamadas_abrir == 1
    assert [p.id_caso for p in agencia_a.pedidos] == ["caso-1"]
    assert agencia_a.pedidos[0].reserva["lugar"] == "Roma"
    assert broker.tamano_actual(NombreCola.CASOS_AYUDA) == 0
    assert await adaptador.procesar_uno() is ResultadoEntrega.VACIA


async def test_AC_REF_05_03_un_reintento_no_abre_un_segundo_caso(broker, adaptador, agencia_a, reloj):
    agencia_a.respuestas_perdidas = 1  # la agencia abre el caso y la respuesta se pierde
    broker.publicar(NombreCola.CASOS_AYUDA, pedido())
    assert await adaptador.procesar_uno() is ResultadoEntrega.ENTREGADO  # el reintento sale bien
    assert agencia_a.llamadas_abrir == 2  # hubo un reintento con el mismo identificador
    assert list(agencia_a.casos) == ["caso-1"] and len(agencia_a.pedidos) == 1  # un solo caso
    assert reloj.esperas == [1.0]
    assert novedades(broker) == []


async def test_AC_REF_05_04_reintentos_agotados_publican_sin_entregar(broker, adaptador, agencia_a, reloj, avisos):
    agencia_a.caida = True
    broker.publicar(NombreCola.CASOS_AYUDA, pedido())
    assert await adaptador.procesar_uno() is ResultadoEntrega.MUERTO
    assert agencia_a.llamadas_abrir == 4  # el primero y tres reintentos
    assert reloj.esperas == [1.0, 2.0, 4.0]
    assert [m.id for m in broker.mensajes_muertos(NombreCola.CASOS_AYUDA)] == ["caso-1"]
    assert avisos == [Aviso("mensaje_muerto", NombreCola.CASOS_AYUDA, "caso-1")]  # aviso a operaciones
    assert novedades(broker) == [("caso:caso-1:sin_entregar",
                                  {"origen": "caso", "id_caso": "caso-1", "estado": "sin_entregar"})]


async def test_una_demora_de_la_agencia_no_es_un_fallo(broker, adaptador, agencia_a):
    agencia_a.demora_segundos = 0.01
    broker.publicar(NombreCola.CASOS_AYUDA, pedido())
    assert await adaptador.procesar_uno() is ResultadoEntrega.ENTREGADO


async def test_AC_REF_05_16_una_segunda_agencia_recibe_el_pedido_sin_cambios_en_el_orquestador(
        broker, agencia_a, reloj):
    agencia_b = MockAgencia("agencia-b")  # un adaptador más en el registro
    adaptador = AdaptadorAgencia(broker, {"agencia-a": agencia_a, "agencia-b": agencia_b},
                                 ConfiguracionAgencias(), dormir=reloj.dormir)
    broker.publicar(NombreCola.CASOS_AYUDA, pedido("caso-a", "agencia-a"))
    broker.publicar(NombreCola.CASOS_AYUDA, pedido("caso-b", "agencia-b"))
    await adaptador.procesar_uno()
    await adaptador.procesar_uno()
    assert list(agencia_a.casos) == ["caso-a"] and list(agencia_b.casos) == ["caso-b"]


async def test_un_pedido_para_una_agencia_sin_adaptador_termina_sin_entregar(broker, adaptador):
    broker.publicar(NombreCola.CASOS_AYUDA, pedido("caso-x", "agencia-fantasma"))
    assert await adaptador.procesar_uno() is ResultadoEntrega.MUERTO
    assert novedades(broker)[0][0] == "caso:caso-x:sin_entregar"


async def test_AC_REF_05_17_el_resumen_del_dialogo_llega_a_la_agencia(broker, adaptador, agencia_a):
    broker.publicar(NombreCola.CASOS_AYUDA, pedido(resumen="El asistente no pudo reprogramar"))
    await adaptador.procesar_uno()
    assert agencia_a.pedidos[0].resumen_dialogo == "El asistente no pudo reprogramar"
    assert agencia_a.pedidos[0].descripcion == "No tengo habitación"


async def test_sin_entregar_con_la_cola_de_novedades_llena_reintenta_y_si_no_hay_lugar_avisa(
        broker, adaptador, agencia_a, reloj):
    agencia_a.caida = True
    for i in range(5):  # la cola de novedades (5 en los tests) no tiene lugar
        broker.publicar(NombreCola.NOVEDADES, Mensaje(f"relleno-{i}", {}))
    broker.publicar(NombreCola.CASOS_AYUDA, pedido())
    await adaptador.procesar_uno()
    assert reloj.esperas[-3:] == [1.0, 2.0, 4.0]  # los reintentos de publicar la novedad
    assert broker.tamano_actual(NombreCola.NOVEDADES) == 5  # no se pudo: queda en mensajes muertos
    assert [m.id for m in broker.mensajes_muertos(NombreCola.CASOS_AYUDA)] == ["caso-1"]

