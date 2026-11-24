# SPEC: SPEC-COMP-06 | PLAN-COMP-06 T-COMP-06-05
import asyncio

from tests.comp06_util import CRITERIOS, Cronometro, Reloj, borde_con, criterios, estados, sistema


async def _con_copia(**cambios):
    """Un sistema con la grilla de CRITERIOS ya en la caché, y el reloj para envejecerla."""
    sis, reloj = sistema(**cambios), Reloj()
    borde = borde_con(sis, reloj, **cambios)
    primera = await borde.obtener(CRITERIOS)
    assert primera.completa and not primera.copia
    return sis, borde, reloj, primera


async def test_copia_vigente_se_entrega_sin_llamar_al_orquestador():
    sis, borde, reloj, primera = await _con_copia()
    atendidos = [n.atendidos for n in sis.nodos]
    reloj.avanzar(299)
    with Cronometro() as t:
        otra = await borde.obtener(CRITERIOS)
    assert otra.copia and otra.origenes == primera.origenes
    assert [n.atendidos for n in sis.nodos] == atendidos and t.segundos < 0.05


async def test_AC_COMP_06_04_cota_vencida_entrega_la_copia():
    sis, borde, reloj, primera = await _con_copia()
    reloj.avanzar(301)  # la copia ya no es vigente
    for n in sis.nodos:
        n.demora_segundos = 1.5  # la respuesta fresca no llega en 800 ms
    with Cronometro() as t:
        grilla = await borde.obtener(CRITERIOS)
    assert grilla.copia and grilla.origenes == primera.origenes
    assert 0.75 < t.segundos < 0.95  # se corta en la cota de 800 ms
    await borde.cerrar()


async def test_AC_COMP_06_05_respuesta_tardia_actualiza_la_copia():
    sis, borde, reloj, _ = await _con_copia()
    reloj.avanzar(301)
    sis.apis["hoteles"].caida = True  # la grilla fresca saldrá distinta: sin hoteles
    for n in sis.nodos:
        n.demora_segundos = 1.0
    cota = await borde.obtener(CRITERIOS)
    assert cota.copia and estados(cota)["hoteles"] == "ok"  # se entregó la copia vieja
    await asyncio.sleep(0.5)  # llega la respuesta fresca, ya fuera de la cota
    with Cronometro() as t:
        nueva = await borde.obtener(CRITERIOS)
    assert nueva.copia and estados(nueva)["hoteles"] == "no_respondio"  # la copia se actualizó
    assert t.segundos < 0.05  # y ahora es vigente: no consulta
    await borde.cerrar()


async def test_cota_vencida_sin_copia_entrega_la_grilla_parcial_que_ya_armo_el_orquestador():
    sis = sistema(cota_hoteles_ms=3000)  # el adaptador tarda más que el borde
    sis.apis["hoteles"].demora_segundos = 5
    borde = borde_con(sis, cota_hoteles_ms=3000)
    with Cronometro() as t:
        grilla = await borde.obtener(CRITERIOS)
    assert estados(grilla) == {"aerolineas": "ok", "arrendadoras": "ok", "hoteles": "no_respondio"}
    assert not grilla.completa and not grilla.copia and not grilla.en_curso
    assert 0.75 < t.segundos < 0.95
    await borde.cerrar()


async def test_AC_COMP_06_06_sin_copia_y_sin_origenes_responde_en_curso():
    # a) Los tres proveedores sin respuesta: el Orquestador devuelve sin ningún origen ok.
    sis = sistema()
    for api in sis.apis.values():
        api.caida = True
    borde = borde_con(sis)
    with Cronometro() as t:
        grilla = await borde.obtener(CRITERIOS)
    assert grilla.en_curso and not grilla.completa and not grilla.copia and t.segundos < 0.8
    # No se guardó: el próximo pedido vuelve a consultar.
    for api in sis.apis.values():
        api.caida = False
    assert (await borde.obtener(CRITERIOS)).completa

    # b) El nodo ni siquiera arma nada antes de la cota.
    sis2 = sistema()
    for n in sis2.nodos:
        n.demora_segundos = 3
    borde2 = borde_con(sis2)
    with Cronometro() as t:
        grilla2 = await borde2.obtener(criterios(3))
    assert grilla2.en_curso and grilla2.origenes == () and t.segundos < 0.95
    await borde2.cerrar()


async def test_si_no_hay_nodos_sanos_se_entrega_la_copia_y_sin_copia_en_curso():
    sis, borde, reloj, primera = await _con_copia()
    reloj.avanzar(301)
    for n in sis.nodos:
        n.sin_eco = True
    await sis.balanceador.verificar_nodos()
    assert (await borde.obtener(CRITERIOS)).copia
    assert (await borde.obtener(criterios(7))).en_curso


async def test_la_copia_vencida_se_usa_si_la_fresca_no_trae_ningun_origen():
    sis, borde, reloj, primera = await _con_copia()
    reloj.avanzar(301)
    for api in sis.apis.values():
        api.caida = True
    grilla = await borde.obtener(CRITERIOS)
    assert grilla.copia and grilla.origenes == primera.origenes


async def test_la_cache_descarta_la_copia_mas_antigua_al_llegar_al_tope():
    sis = sistema()
    borde = borde_con(sis, max_copias=2)
    for dia in (1, 2, 3):
        await borde.obtener(criterios(dia))
    assert [(await borde.obtener(criterios(d))).copia for d in (3, 2)] == [True, True]
    assert not (await borde.obtener(criterios(1))).copia  # la primera se descartó


async def test_cerrar_no_deja_tareas_colgadas():
    sis = sistema()
    for n in sis.nodos:
        n.demora_segundos = 3
    borde = borde_con(sis)
    await borde.obtener(CRITERIOS)
    assert borde._pendientes
    await borde.cerrar()
    assert not borde._pendientes
