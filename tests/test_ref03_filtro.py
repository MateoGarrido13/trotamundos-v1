# SPEC: SPEC-REF-03
# ELEMENTO PASO 5: Filtro de remitentes (ITERACION_3)
# ADRs: ADR-IT3-008, ADR-IT3-003
# DRIVERS: REF-03, QA-SEG-03*
"""T-REF-03-04: el filtro, con un almacén en memoria y un doble de la ingesta."""
import json

import pytest

from tests.ref03_util import reserva_norm
from trotamundos.broker import Broker, Mensaje, NombreCola, ResultadoEntrega
from trotamundos.dominio.puertos_correo import ResultadoRetencion
from trotamundos.entrada.consumidor_correo import ConsumidorCorreo
from trotamundos.entrada.filtro_remitentes import FiltroWhitelist
from trotamundos.entrada.parseo_aislado.cliente import ClienteParseo


class AlmacenEnMemoria:
    def __init__(self, tope=50):
        self.seguros, self.retenidos, self.descartados, self.tope = set(), {}, set(), tope

    async def remitente_seguro(self, titular_id, remitente):
        return (titular_id, remitente.lower()) in self.seguros

    async def retener(self, reserva):
        clave = (reserva.titular_id, reserva.id_mensaje)
        if clave in self.retenidos or clave in self.descartados:
            return ResultadoRetencion.DUPLICADA
        if len(self.retenidos) >= self.tope:
            return ResultadoRetencion.TOPE_ALCANZADO
        self.retenidos[clave] = reserva
        return ResultadoRetencion.RETENIDA


class IngestaEspia:
    def __init__(self):
        self.recibidas = []

    async def recibir(self, reserva):
        self.recibidas.append(reserva)


@pytest.fixture
def almacen():
    return AlmacenEnMemoria()


@pytest.fixture
def ingesta():
    return IngestaEspia()


@pytest.fixture
def filtro(almacen, ingesta):
    return FiltroWhitelist(almacen, ingesta)


async def test_AC_REF_03_01_remitente_seguro_pasa_a_la_ingesta(filtro, almacen, ingesta):
    almacen.seguros.add(("t1", "agencia@x.com"))
    await filtro.recibir(reserva_norm())
    assert [r.id_mensaje for r in ingesta.recibidas] == ["<m1@x>"]
    assert almacen.retenidos == {}


async def test_AC_REF_03_02_remitente_desconocido_queda_en_revision(filtro, almacen, ingesta):
    await filtro.recibir(reserva_norm())
    assert ingesta.recibidas == []  # no entra al itinerario
    assert list(almacen.retenidos) == [("t1", "<m1@x>")]  # tampoco se descarta


async def test_la_whitelist_es_de_cada_titular(filtro, almacen, ingesta):
    almacen.seguros.add(("t1", "agencia@x.com"))
    await filtro.recibir(reserva_norm(titular="t2"))
    assert ingesta.recibidas == [] and len(almacen.retenidos) == 1


async def test_AC_REF_03_05_mismo_mensaje_deja_una_sola_entrada_en_revision_en_el_filtro(
        filtro, almacen):
    for _ in range(3):  # tres sondeos releen el mismo mensaje
        await filtro.recibir(reserva_norm())
    assert len(almacen.retenidos) == 1


async def test_AC_REF_03_06_tope_alcanzado_no_retiene_ni_falla(filtro, almacen, ingesta):
    almacen.tope = 1
    await filtro.recibir(reserva_norm("<a@x>"))
    await filtro.recibir(reserva_norm("<b@x>"))  # no lanza: no hay reintento ni mensajes muertos
    assert list(almacen.retenidos) == [("t1", "<a@x>")]
    assert ingesta.recibidas == []


async def test_liberar_entrega_las_reservas_aprobadas_a_la_ingesta(filtro, ingesta):
    await filtro.liberar([reserva_norm("<a@x>"), reserva_norm("<b@x>")])
    assert [r.id_mensaje for r in ingesta.recibidas] == ["<a@x>", "<b@x>"]


async def test_AC_REF_03_04_contenido_invalido_no_llega_a_revision(cfg_broker, almacen, ingesta, filtro):
    async def sin_espera(_s):
        return None

    broker = Broker(cfg_broker, dormir=sin_espera)
    parseo = ClienteParseo()
    try:
        consumidor = ConsumidorCorreo(broker, parseo, filtro)
        broker.publicar(NombreCola.CORREO, Mensaje("<malo@x>", {
            "titular_id": "t1", "remitente": "agencia@x.com", "cuerpo": "esto no es una reserva"}))
        broker.publicar(NombreCola.CORREO, Mensaje("<peligro@x>", {
            "titular_id": "t1", "remitente": "agencia@x.com",
            "cuerpo": json.dumps({"tipo": "hotel", "inicio": "2026-12-01T10:00:00",
                                  "fin": "2026-12-05T10:00:00", "lugar": "Roma\x00", "codigo": "H"})}))
        assert await consumidor.procesar_uno() is ResultadoEntrega.ENTREGADO
        assert await consumidor.procesar_uno() is ResultadoEntrega.ENTREGADO
    finally:
        await parseo.cerrar()
    # el descarte ya ocurrió en el parseo: el filtro no vio nada ni retuvo nada
    assert almacen.retenidos == {} and ingesta.recibidas == []
