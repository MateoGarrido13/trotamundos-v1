# SPEC: SPEC-COMP-07 | PLAN-COMP-07 T-COMP-07-04
import asyncio
import logging

from tests.comp07_util import CFG, Entorno
from trotamundos.config import ConfiguracionBooking
from trotamundos.entrada.booking import adaptador as modulo


async def test_con_eco_no_se_avisa_a_nadie():
    e = Entorno()
    assert await e.adaptador.verificar_eco() is True and e.adaptador.avisos == [] and e.booking.pings == 1


async def test_AC_COMP_07_08_sin_eco_se_avisa_a_operaciones(caplog):
    caplog.set_level(logging.ERROR, logger="trotamundos.operaciones")
    e = Entorno()
    e.booking.sin_eco = True
    assert await e.adaptador.verificar_eco() is False
    assert e.adaptador.avisos == ["Booking no responde al ping (sin eco)"]
    assert "sin eco" in caplog.text


async def test_booking_caido_o_demasiado_lento_tambien_es_sin_eco(monkeypatch):
    monkeypatch.setattr(modulo, "COTA_ECO_SEGUNDOS", 0.05)
    e = Entorno()
    e.booking.caida = True
    assert await e.adaptador.verificar_eco() is False
    e.booking.caida, e.booking.demora_segundos = False, 1.0
    assert await e.adaptador.verificar_eco() is False
    assert len(e.adaptador.avisos) == 2


async def test_el_eco_se_verifica_periodicamente_hasta_que_se_cancela():
    e = Entorno(cfg=ConfiguracionBooking(clave_proveedor=CFG.clave_proveedor, intervalo_eco_segundos=0.02))
    e.booking.sin_eco = True
    tarea = asyncio.create_task(e.adaptador.ejecutar_eco())
    await asyncio.sleep(0.15)
    tarea.cancel()
    await asyncio.gather(tarea, return_exceptions=True)
    assert e.booking.pings >= 3 and len(e.adaptador.avisos) >= 3
