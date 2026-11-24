# SPEC: SPEC-COMP-06 | PLAN-COMP-06 T-COMP-06-03
import ast
from pathlib import Path

from tests.comp06_util import CRITERIOS, Cronometro, HotelNuevo, estados, sistema
from trotamundos.composicion import ensamblar_cotizacion
from trotamundos.config import ConfiguracionCotizacion
from trotamundos.dominio.cotizacion import ProgresoGrilla


async def test_AC_COMP_06_01_tres_proveedores_en_paralelo_no_suman():
    sis = sistema()
    for api in sis.apis.values():
        api.demora_segundos = 0.15  # ping y precio: 0,3 s por proveedor
    with Cronometro() as t:
        grilla = await sis.nodos[0].atender(CRITERIOS, ProgresoGrilla())
    assert grilla.completa and not grilla.en_curso and not grilla.copia
    assert set(estados(grilla).values()) == {"ok"}
    assert 0.28 < t.segundos < 0.55  # si se sumaran serían 0,9 s


async def test_AC_COMP_06_02_proveedor_caido_da_grilla_parcial():
    sis = sistema()
    sis.apis["hoteles"].caida = True
    with Cronometro() as t:
        grilla = await sis.nodos[0].atender(CRITERIOS, ProgresoGrilla())
    assert estados(grilla) == {"aerolineas": "ok", "arrendadoras": "ok", "hoteles": "no_respondio"}
    assert not grilla.completa and not grilla.en_curso
    assert t.segundos < 0.8


async def test_proveedor_sin_respuesta_hasta_su_cota_no_retrasa_a_los_demas_mas_que_esa_cota():
    sis = sistema()
    sis.apis["arrendadoras"].demora_segundos = 5
    with Cronometro() as t:
        grilla = await sis.nodos[0].atender(CRITERIOS, ProgresoGrilla())
    assert estados(grilla)["arrendadoras"] == "no_respondio"
    assert t.segundos < 0.7


async def test_un_cotizador_que_explota_solo_afecta_a_su_origen():
    class Roto(HotelNuevo):
        nombre = "roto"

        async def cotizar(self, criterios):
            raise RuntimeError("bug del proveedor")

    sis = ensamblar_cotizacion(ConfiguracionCotizacion(), cotizadores_extra=(Roto(),))
    grilla = await sis.nodos[0].atender(CRITERIOS, ProgresoGrilla())
    assert estados(grilla)["roto"] == "no_respondio" and estados(grilla)["hoteles"] == "ok"


async def test_AC_COMP_06_09_hotel_nuevo_no_modifica_el_orquestador():
    sis = ensamblar_cotizacion(ConfiguracionCotizacion(), cotizadores_extra=(HotelNuevo(),))
    grilla = await sis.nodos[0].atender(CRITERIOS, ProgresoGrilla())
    assert estados(grilla)["hotel_nuevo"] == "ok" and grilla.completa
    # El Orquestador no importa ningún adaptador: no cambia al sumar un proveedor.
    fuente = Path(__import__("trotamundos.cotizacion.servicio", fromlist=["x"]).__file__).read_text()
    importados = {n.module for n in ast.walk(ast.parse(fuente)) if isinstance(n, ast.ImportFrom)}
    assert not any(m and ("adaptadores" in m or "apis_simuladas" in m) for m in importados)
