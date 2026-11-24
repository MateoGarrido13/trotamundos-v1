# SPEC: SPEC-COMP-08 | PLAN-COMP-08 T-COMP-08-01
from trotamundos.broker import Broker, Mensaje, NombreCola, ResultadoEntrega

COLA = NombreCola.NOTIFICACIONES


def _con(*ids_y_canal):
    broker = Broker()
    for i, canal in ids_y_canal:
        broker.publicar(COLA, Mensaje(i, {"canal": canal}))
    return broker


async def test_donde_toma_solo_el_primero_que_cumple_y_deja_los_demas_en_su_lugar():
    broker = _con(("a", "x"), ("b", "y"), ("c", "x"))
    vistos = []

    async def handler(m):
        vistos.append(m.id)

    assert await broker.procesar_uno(COLA, handler, donde=lambda m: m.cuerpo["canal"] == "y") is ResultadoEntrega.ENTREGADO
    assert vistos == ["b"] and broker.tamano_actual(COLA) == 2
    assert await broker.procesar_uno(COLA, handler) is ResultadoEntrega.ENTREGADO  # sin `donde`: el siguiente, a
    assert vistos == ["b", "a"]


async def test_donde_sin_coincidencia_es_cola_vacia_para_ese_consumidor():
    broker = _con(("a", "x"))

    async def handler(m):
        raise AssertionError("no debía entregarse")

    assert await broker.procesar_uno(COLA, handler, donde=lambda m: False) is ResultadoEntrega.VACIA
    assert broker.tamano_actual(COLA) == 1


async def test_donde_conserva_el_retry_y_los_muertos_del_broker():
    esperas = []

    async def dormir(segundos):
        esperas.append(segundos)

    avisos = []
    broker = Broker(avisar=avisos.append, dormir=dormir)
    broker.publicar(COLA, Mensaje("a", {"canal": "x"}))

    async def falla(m):
        raise RuntimeError("canal caído")

    assert await broker.procesar_uno(COLA, falla, donde=lambda m: True) is ResultadoEntrega.MUERTO
    assert esperas == [1.0, 2.0, 4.0]
    assert [m.id for m in broker.mensajes_muertos(COLA)] == ["a"] and avisos[-1].tipo == "mensaje_muerto"
