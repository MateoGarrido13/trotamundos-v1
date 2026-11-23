# SPEC: SPEC-REF-06
# ELEMENTO PASO 5: Orquestador de viajes, publicación en la quinta cola (ITERACION_5)
# ADRs: ADR-IT5-001, ADR-IT3-002, ADR-IT3-003
# DRIVERS: REF-06, QA-PER-02
"""T-REF-06-02: el emisor publica sin demorar, reintenta y no rompe nada."""
import time
from datetime import UTC, datetime

import pytest

from trotamundos.broker import Aviso, Broker, Mensaje, NombreCola
from trotamundos.orquestador.eventos_analiticos import EmisorEventos

AHORA = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
DATOS = {"tipo": "alta", "tipo_reserva": "hotel", "destino": "Roma", "origen": "manual",
         "estado": "confirmada"}


def llenar(broker):
    for i in range(5):
        broker.publicar(NombreCola.EVENTOS_ANALITICOS, Mensaje(f"relleno-{i}", {}))


async def test_el_evento_se_publica_en_la_quinta_cola(cfg_broker):
    broker = Broker(cfg_broker)
    emisor = EmisorEventos(broker)
    emisor.emitir(DATOS, AHORA)
    await emisor.esperar()
    [mensaje] = list(broker._colas[NombreCola.EVENTOS_ANALITICOS])
    assert mensaje.cuerpo["tipo"] == "alta" and mensaje.cuerpo["destino"] == "Roma"
    assert mensaje.id == mensaje.cuerpo["id"] and mensaje.id.startswith("evt-")


async def test_cada_evento_lleva_un_identificador_distinto(cfg_broker):
    broker = Broker(cfg_broker)
    emisor = EmisorEventos(broker)
    for _ in range(3):
        emisor.emitir(DATOS, AHORA)
    await emisor.esperar()
    ids = [m.id for m in broker._colas[NombreCola.EVENTOS_ANALITICOS]]
    assert len(set(ids)) == 3


async def test_AC_REF_06_08_cola_llena_no_demora_reintenta_y_agotada_va_a_mensajes_muertos(cfg_broker):
    avisos: list[Aviso] = []
    broker = Broker(cfg_broker, avisar=avisos.append)
    llenar(broker)
    esperas: list[float] = []

    async def dormir(s):
        esperas.append(s)
    emisor = EmisorEventos(broker, dormir=dormir)

    inicio = time.perf_counter()
    emisor.emitir(DATOS, AHORA)
    assert time.perf_counter() - inicio < 0.05  # emitir vuelve enseguida: no espera a los reintentos
    assert esperas == []  # todavía no corrió ninguno
    await emisor.esperar()

    assert esperas == [1.0, 2.0, 4.0]  # 3 reintentos con espera de 1 s, 2 s y 4 s
    [muerto] = broker.mensajes_muertos(NombreCola.EVENTOS_ANALITICOS)
    assert muerto.cuerpo["tipo"] == "alta"
    assert [a.tipo for a in avisos].count("mensaje_muerto") == 1  # aviso a operaciones
    assert broker.tamano_actual(NombreCola.EVENTOS_ANALITICOS) == 5  # la cola siguió igual


async def test_si_hay_lugar_durante_los_reintentos_el_evento_se_publica(cfg_broker):
    broker = Broker(cfg_broker)
    llenar(broker)
    veces = 0

    async def dormir(_s):
        nonlocal veces
        veces += 1
        if veces == 2:
            broker._colas[NombreCola.EVENTOS_ANALITICOS].popleft()
    emisor = EmisorEventos(broker, dormir=dormir)
    emisor.emitir(DATOS, AHORA)
    await emisor.esperar()
    assert broker.mensajes_muertos(NombreCola.EVENTOS_ANALITICOS) == []
    assert broker.tamano_actual(NombreCola.EVENTOS_ANALITICOS) == 5


async def test_un_dato_invalido_no_lanza_ni_publica(cfg_broker):
    broker = Broker(cfg_broker)
    emisor = EmisorEventos(broker)
    emisor.emitir({"tipo": "alta", "cuenta": "ana"}, AHORA)  # un campo que el evento no admite
    emisor.emitir({"tipo": "compra"}, AHORA)
    await emisor.esperar()
    assert broker.tamano_actual(NombreCola.EVENTOS_ANALITICOS) == 0


def test_emitir_sin_un_lazo_de_eventos_no_rompe_la_operacion(cfg_broker):
    EmisorEventos(Broker(cfg_broker)).emitir(DATOS, AHORA)  # no hay loop corriendo: se registra y sigue
