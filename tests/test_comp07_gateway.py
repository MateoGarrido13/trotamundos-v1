# SPEC: SPEC-COMP-07 | PLAN-COMP-07 T-COMP-07-01 (D12)
"""El listener de Booking no pasa por el API Gateway: con el Gateway activo se autentica por su clave."""
import httpx
from fastapi import FastAPI

from tests.comp07_util import CLAVE, Entorno
from trotamundos.entrada.booking.simulado import BookingSimulado
from trotamundos.identidad.gateway.firma import es_publica
from trotamundos.identidad.gateway.gateway import Gateway
from trotamundos.identidad.gateway.limitador import LimitadorTasa
from trotamundos.identidad.tokens import ValidadorTokens


class _Validador(ValidadorTokens):
    def __init__(self):
        pass

    def validar(self, token, ahora):
        return f"amer-{token}"


def test_el_listener_es_una_ruta_publica_del_gateway_y_los_anuncios_no():
    assert es_publica("/proveedores/booking/avisos")
    assert not es_publica("/novedades/anuncios")


async def test_con_el_gateway_activo_el_aviso_entra_sin_token_y_la_lectura_lo_pide():
    e = Entorno()
    app = Gateway(e.app, validador=_Validador(), limitador=LimitadorTasa({}, 60), secreto="s")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/proveedores/booking/avisos", json=BookingSimulado.aviso(1),
                         headers={"X-Clave-Proveedor": CLAVE})
        assert r.status_code == 202 and e.en_cola() == 1  # sin Authorization: lo autentica la clave
        r = await c.post("/proveedores/booking/avisos", json=BookingSimulado.aviso(2),
                         headers={"X-Clave-Proveedor": "mala"})
        assert r.status_code == 401 and e.en_cola() == 1
        assert (await c.get("/novedades/anuncios")).status_code == 401  # esta sí exige token
