# SPEC: SPEC-REF-03
# ELEMENTO PASO 5: Servicio de ingesta (ITERACION_3)
# ADRs: ADR-IT3-003, ADR-IT3-010
# DRIVERS: REF-03
"""T-REF-03-05: duplicados, límite de tasa, Retry y mensajes muertos de la ingesta."""
from datetime import timedelta

import pytest

from tests.ref03_util import AHORA, reserva_norm
from trotamundos.broker import Aviso, Broker, ColaLlena, NombreCola, ResultadoEntrega
from trotamundos.config import ConfiguracionBroker, ConfiguracionIngesta
from trotamundos.entrada.ingesta import LimitadorTasa, ServicioIngesta


class EntregaEspia:
    def __init__(self):
        self.entregadas, self.fallos_pendientes, self.intentos = [], 0, 0

    async def incorporar(self, reserva):
        self.intentos += 1
        if self.fallos_pendientes:
            self.fallos_pendientes -= 1
            raise TimeoutError("el Orquestador no responde")
        self.entregadas.append(reserva)


class Reloj:
    """Reloj virtual: dormir lo adelanta, así los tests no esperan tiempo real."""

    def __init__(self):
        self.t = 0.0
        self.esperas = []

    def __call__(self):
        return self.t

    async def dormir(self, s):
        self.esperas.append(s)
        self.t += s


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def entrega():
    return EntregaEspia()


@pytest.fixture
def armado(cfg_broker, entrega, reloj):
    avisos: list[Aviso] = []
    broker = Broker(cfg_broker, avisar=avisos.append, dormir=reloj.dormir)
    limitador = LimitadorTasa(20, reloj=reloj, dormir=reloj.dormir)
    ingesta = ServicioIngesta(broker, entrega, ConfiguracionIngesta(), limitador=limitador,
                              reloj=lambda: AHORA)
    return broker, ingesta, avisos


async def test_AC_REF_03_13_ingesta_descarta_identificador_ya_procesado(armado, entrega):
    _, ingesta, _ = armado
    for _ in range(3):  # el mismo mensaje llega en tres sondeos
        await ingesta.recibir(reserva_norm())
    for _ in range(3):
        assert await ingesta.procesar_uno() is ResultadoEntrega.ENTREGADO
    assert [r.id_mensaje for r in entrega.entregadas] == ["<m1@x>"]  # el Orquestador recibe una sola


async def test_el_mismo_correo_para_dos_titulares_no_se_confunde(armado, entrega):
    _, ingesta, _ = armado
    await ingesta.recibir(reserva_norm(titular="t1"))
    await ingesta.recibir(reserva_norm(titular="t2"))  # mismo Message-ID, otro titular
    await ingesta.procesar_uno()
    await ingesta.procesar_uno()
    assert sorted(r.titular_id for r in entrega.entregadas) == ["t1", "t2"]


async def test_un_identificador_vencido_de_la_retencion_se_vuelve_a_aceptar(cfg_broker, entrega, reloj):
    ahora = [AHORA]
    broker = Broker(cfg_broker, dormir=reloj.dormir)
    ingesta = ServicioIngesta(broker, entrega, ConfiguracionIngesta(retencion_ids_dias=7),
                              limitador=LimitadorTasa(20, reloj=reloj, dormir=reloj.dormir),
                              reloj=lambda: ahora[0])
    await ingesta.recibir(reserva_norm())
    await ingesta.procesar_uno()
    ahora[0] = AHORA + timedelta(days=8)
    await ingesta.recibir(reserva_norm())
    await ingesta.procesar_uno()
    assert len(entrega.entregadas) == 2


async def test_AC_REF_03_14_entrega_no_supera_el_limite_de_tasa(reloj, entrega):
    broker = Broker(ConfiguracionBroker(tamano_maximo_cola=200), dormir=reloj.dormir)
    ingesta = ServicioIngesta(broker, entrega, ConfiguracionIngesta(),
                              limitador=LimitadorTasa(20, reloj=reloj, dormir=reloj.dormir),
                              reloj=lambda: AHORA)
    instantes = []

    async def incorporar(reserva):
        instantes.append(reloj())
    entrega.incorporar = incorporar

    for i in range(100):  # un pico muy por encima de 20 por segundo
        await ingesta.recibir(reserva_norm(f"<m{i}@x>"))
    for _ in range(100):
        await ingesta.procesar_uno()
    assert len(instantes) == 100
    eps = 1e-9  # tolerancia de punto flotante en el borde de la ventana
    for t in instantes:  # en ninguna ventana de 1 s hay más de 20 entregas
        assert sum(1 for x in instantes if t <= x < t + 1.0 - eps) <= 20
    assert max(instantes) >= 4.9  # 100 entregas a 20/s tardan unos 5 s


async def test_AC_REF_03_15_entrega_fallida_agota_reintentos_y_va_a_mensajes_muertos(
        armado, entrega, reloj):
    broker, ingesta, avisos = armado
    entrega.fallos_pendientes = 99
    await ingesta.recibir(reserva_norm())
    assert await ingesta.procesar_uno() is ResultadoEntrega.MUERTO
    assert entrega.intentos == 4  # el primero y tres reintentos
    assert [m.id for m in broker.mensajes_muertos(NombreCola.NOVEDADES)] == ["t1:<m1@x>"]
    assert avisos == [Aviso("mensaje_muerto", NombreCola.NOVEDADES, "t1:<m1@x>")]
    assert reloj.esperas[-3:] == [1.0, 2.0, 4.0]  # backoff 1 s, 2 s, 4 s


async def test_un_fallo_transitorio_se_reintenta_sin_duplicar(armado, entrega):
    _, ingesta, avisos = armado
    entrega.fallos_pendientes = 1  # el primer intento da timeout
    await ingesta.recibir(reserva_norm())
    assert await ingesta.procesar_uno() is ResultadoEntrega.ENTREGADO
    assert len(entrega.entregadas) == 1 and avisos == []


async def test_cola_llena_hace_fallar_al_filtro_y_no_pierde(armado):
    _, ingesta, avisos = armado
    for i in range(5):
        await ingesta.recibir(reserva_norm(f"<m{i}@x>"))
    with pytest.raises(ColaLlena):
        await ingesta.recibir(reserva_norm("<m5@x>"))
    assert avisos and avisos[0].tipo == "cola_llena"
