# SPEC: SPEC-COMP-08 | PLAN-COMP-08 T-COMP-08-05
import asyncio
import threading

import pytest

from tests.comp08_util import pedido
from trotamundos.broker import Broker, NombreCola
from trotamundos.config import ConfiguracionBroker, ConfiguracionNotificaciones
from trotamundos.orquestador.notificaciones import PublicadorNotificaciones

COLA = NombreCola.NOTIFICACIONES


def armar(tamano=1):
    esperas, avisos = [], []

    async def dormir(segundos):
        esperas.append(segundos)

    broker = Broker(ConfiguracionBroker(tamano_maximo_cola=tamano), avisar=avisos.append)
    return broker, PublicadorNotificaciones(broker, ConfiguracionNotificaciones(), dormir=dormir), esperas, avisos


async def test_publica_el_pedido_con_su_identificador_en_la_cola():
    broker, publicador, esperas, _ = armar(tamano=5)
    assert await publicador.publicar(pedido("n1")) is True
    assert broker.tamano_actual(COLA) == 1 and esperas == []


async def test_AC_COMP_08_07_cola_llena_reintenta_con_1_2_y_4_segundos_y_avisa():
    broker, publicador, esperas, avisos = armar()
    await publicador.publicar(pedido("n1"))  # la cola (de 1) queda llena
    assert await publicador.publicar(pedido("n2")) is False
    assert esperas == [1.0, 2.0, 4.0]
    assert [m.id for m in broker.mensajes_muertos(COLA)] == ["n2"]  # agotados: a muertos
    tipos = [a.tipo for a in avisos]
    assert tipos.count("cola_llena") == 4 and tipos[-1] == "mensaje_muerto"  # avisa a operaciones


async def test_si_la_cola_se_libera_durante_los_reintentos_el_pedido_entra():
    broker, publicador, esperas, _ = armar()
    await publicador.publicar(pedido("n1"))

    async def liberar(segundos):
        esperas.append(segundos)
        if len(esperas) == 2:
            broker._colas[COLA].clear()

    publicador._dormir = liberar
    assert await publicador.publicar(pedido("n2")) is True
    assert esperas == [1.0, 2.0] and broker.mensajes_muertos(COLA) == []
    assert broker.tamano_actual(COLA) == 1


@pytest.mark.parametrize("malo", [None, "texto", {}, {"id": "a"}, pedido("a", canal=""),
                                  {**pedido("a"), "propuesta": {"asunto": "x"}}, {**pedido("a"), "destinatario": 3}])
async def test_un_pedido_mal_formado_no_entra_a_la_cola(malo):
    broker, publicador, _, _ = armar(tamano=5)
    with pytest.raises(ValueError):
        await publicador.publicar(malo)
    with pytest.raises(ValueError):
        publicador.publicar_desde_hilo(malo)
    assert broker.tamano_actual(COLA) == 0


async def test_publicar_desde_un_hilo_con_cola_llena_programa_los_reintentos_en_el_bucle():
    broker, publicador, esperas, avisos = armar()
    publicador.enlazar_bucle(asyncio.get_running_loop())
    await publicador.publicar(pedido("n1"))
    hilo = threading.Thread(target=publicador.publicar_desde_hilo, args=(pedido("n2"),))
    hilo.start()
    await asyncio.to_thread(hilo.join)
    for _ in range(50):  # espera los reintentos programados en el bucle
        if broker.mensajes_muertos(COLA):
            break
        await asyncio.sleep(0.01)
    assert esperas == [1.0, 2.0, 4.0] and [m.id for m in broker.mensajes_muertos(COLA)] == ["n2"]
    assert avisos[-1].tipo == "mensaje_muerto"


async def test_sin_bucle_enlazado_un_pedido_que_no_cabe_va_a_muertos_en_lugar_de_perderse():
    broker, publicador, _, avisos = armar()
    publicador.publicar_desde_hilo(pedido("n1"))
    publicador.publicar_desde_hilo(pedido("n2"))
    assert [m.id for m in broker.mensajes_muertos(COLA)] == ["n2"] and avisos[-1].tipo == "mensaje_muerto"
