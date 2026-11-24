# SPEC: SPEC-COMP-06 | PLAN-COMP-06 T-COMP-06-02
import asyncio
from decimal import Decimal

import pytest

from tests.comp06_util import CRITERIOS, Cronometro, sistema
from trotamundos.composicion import ensamblar_cotizacion
from trotamundos.config import ConfiguracionCotizacion
from trotamundos.cotizacion.adaptadores import AdaptadorAerolineas, AdaptadorHoteles
from trotamundos.cotizacion.apis_simuladas import ApiAerolineasSoap, ApiHoteles, ErrorApiProveedor


def adaptadores(sis):
    servicio = sis.nodos[0]._servicio
    return {c.nombre: c for c in servicio._cotizadores}


async def test_los_tres_adaptadores_traducen_al_modelo_interno():
    sis = sistema()
    for nombre, adaptador in adaptadores(sis).items():
        r = await adaptador.cotizar(CRITERIOS)
        assert r.estado.value == "ok" and len(r.precios) == 2, nombre
        assert all(isinstance(p.monto, Decimal) and p.moneda == "USD" for p in r.precios)
    assert (await adaptadores(sis)["aerolineas"].cotizar(CRITERIOS)).precios[0].monto == Decimal("480.50")


async def test_respuesta_que_no_se_puede_traducir_es_origen_que_no_respondio():
    assert (await AdaptadorAerolineas(_Api(ApiAerolineasSoap, "<roto"), 0.5).cotizar(CRITERIOS)).estado.value == "no_respondio"
    assert (await AdaptadorHoteles(_Api(ApiHoteles, {"otra": 1}), 0.5).cotizar(CRITERIOS)).estado.value == "no_respondio"


def _Api(clase, respuesta):
    api = clase()
    api._respuesta = lambda *_: respuesta
    return api


async def test_AC_COMP_06_03_demora_mayor_que_la_cota_se_corta():
    """Hoteles tarda más que su cota (500 ms): se corta en la cota y el resto responde."""
    sis = sistema()
    sis.apis["hoteles"].demora_segundos = 2.0
    with Cronometro() as t:
        r = await adaptadores(sis)["hoteles"].cotizar(CRITERIOS)
    assert r.estado.value == "no_respondio"
    assert 0.45 < t.segundos < 0.7  # cota propia, no los 2 s de la API
    resto = await asyncio.gather(adaptadores(sis)["aerolineas"].cotizar(CRITERIOS),
                                 adaptadores(sis)["arrendadoras"].cotizar(CRITERIOS))
    assert [x.estado.value for x in resto] == ["ok", "ok"]


async def test_AC_COMP_06_07_sin_eco_no_se_pide_precio():
    sis = sistema()
    sis.apis["aerolineas"].sin_eco = True
    r = await adaptadores(sis)["aerolineas"].cotizar(CRITERIOS)
    assert r.estado.value == "no_respondio"
    assert sis.apis["aerolineas"].llamadas_ping == 1
    assert sis.apis["aerolineas"].llamadas_precio == 0


async def test_AC_COMP_06_08_sin_reintento_dentro_del_pedido():
    sis = sistema()
    ad = adaptadores(sis)
    # 1) API caída: un solo ping y nada más.
    sis.apis["hoteles"].caida = True
    assert (await ad["hoteles"].cotizar(CRITERIOS)).estado.value == "no_respondio"
    assert (sis.apis["hoteles"].llamadas_ping, sis.apis["hoteles"].llamadas_precio) == (1, 0)

    # 2) Responde al ping pero falla al pedir el precio: un solo pedido de precio.
    async def falla(*_):
        sis.apis["arrendadoras"].llamadas_precio += 1
        raise ErrorApiProveedor("falla")

    sis.apis["arrendadoras"].precio = falla
    assert (await ad["arrendadoras"].cotizar(CRITERIOS)).estado.value == "no_respondio"
    assert sis.apis["arrendadoras"].llamadas_precio == 1

    # 3) Vence la cota: tampoco reintenta después.
    sis.apis["aerolineas"].demora_segundos = 5
    await ad["aerolineas"].cotizar(CRITERIOS)
    await asyncio.sleep(0.3)
    assert sis.apis["aerolineas"].llamadas_ping == 1
