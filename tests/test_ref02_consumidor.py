# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Cola de correo del Broker / Parseo aislado (ITERACION_3)
# ADRs: ADR-IT3-002, ADR-IT3-003, ADR-IT3-007
# DRIVERS: REF-02
"""T-REF-02-07: ConsumidorCorreo con parseo real (proceso del SO) y Broker real."""
import json

import pytest

from trotamundos.broker import Aviso, Broker, Mensaje, NombreCola, ResultadoEntrega
from trotamundos.entrada.consumidor_correo import ConsumidorCorreo
from trotamundos.entrada.filtro_remitentes import FiltroRemitentesNulo
from trotamundos.entrada.parseo_aislado.cliente import ClienteParseo

VALIDO = {
    "tipo": "hotel", "inicio": "2026-12-01T10:00:00", "fin": "2026-12-05T10:00:00",
    "lugar": "Roma", "codigo": "H-99",
}


async def _sin_espera(_s):
    return None


@pytest.fixture
async def parseo():
    cliente = ClienteParseo()
    try:
        yield cliente
    finally:
        await cliente.cerrar()


def _publicar(broker, ident, cuerpo):
    broker.publicar(
        NombreCola.CORREO,
        Mensaje(ident, {"titular_id": "t1", "remitente": "a@x.com", "cuerpo": cuerpo}),
    )


async def test_AC_REF_02_05_reserva_valida_llega_al_filtro_con_su_identificador(cfg_broker, parseo):
    broker = Broker(cfg_broker, dormir=_sin_espera)
    filtro = FiltroRemitentesNulo()
    consumidor = ConsumidorCorreo(broker, parseo, filtro)
    _publicar(broker, "<m1@x>", json.dumps(VALIDO))
    _publicar(broker, "<malo@x>", "esto no es una reserva")
    assert await consumidor.procesar_uno() is ResultadoEntrega.ENTREGADO
    assert await consumidor.procesar_uno() is ResultadoEntrega.ENTREGADO  # descartado, no falla
    assert [r.id_mensaje for r in filtro.recibidas] == ["<m1@x>"]  # el inválido no llega
    r = filtro.recibidas[0]
    assert (r.titular_id, r.remitente, r.lugar, r.codigo) == ("t1", "a@x.com", "Roma", "H-99")
    assert broker.mensajes_muertos(NombreCola.CORREO) == []


async def test_AC_REF_02_10_reintentos_agotados_van_a_mensajes_muertos_con_aviso(cfg_broker, parseo):
    avisos: list[Aviso] = []
    esperas: list[float] = []

    async def dormir(s):
        esperas.append(s)

    class FiltroQueFalla:
        llamadas = 0

        async def recibir(self, reserva):
            self.llamadas += 1
            raise RuntimeError("filtro caído")

    filtro = FiltroQueFalla()
    broker = Broker(cfg_broker, avisar=avisos.append, dormir=dormir)
    _publicar(broker, "<m1@x>", json.dumps(VALIDO))
    assert await ConsumidorCorreo(broker, parseo, filtro).procesar_uno() is ResultadoEntrega.MUERTO
    assert filtro.llamadas == 4  # 1 intento + 3 reintentos
    assert esperas == [1.0, 2.0, 4.0]
    assert [m.id for m in broker.mensajes_muertos(NombreCola.CORREO)] == ["<m1@x>"]
    assert avisos == [Aviso("mensaje_muerto", NombreCola.CORREO, "<m1@x>")]
