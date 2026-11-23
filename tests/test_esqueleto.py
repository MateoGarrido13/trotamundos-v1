from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from tests.conftest import ReservaDePrueba
from trotamundos.app import create_app
from trotamundos.broker import Aviso, Broker, ColaLlena, Mensaje, NombreCola, ResultadoEntrega
from trotamundos.dominio.registro_tipos import ErrorRegistroTipos, RegistroTipos
from trotamundos.dominio.reserva import Reserva


# --- app -----------------------------------------------------------------------
def test_salud():
    assert TestClient(create_app()).get("/salud").json() == {"estado": "ok"}


# --- Reserva y Registro de tipos -----------------------------------------------
def test_reserva_es_abstracta():
    with pytest.raises(TypeError):
        Reserva(identificador="x", viaje_id="v", inicio=datetime.now(), fin=datetime.now())


def test_registro_acepta_subclase(reserva_de_prueba):
    reg = RegistroTipos()
    reg.registrar("prueba", ReservaDePrueba)
    assert reg.clase_de("prueba") is ReservaDePrueba
    assert reserva_de_prueba.resumen() == "Prueba r1"


def test_registro_rechaza_duplicado():
    reg = RegistroTipos()
    reg.registrar("prueba", ReservaDePrueba)
    with pytest.raises(ErrorRegistroTipos, match="ya está registrado"):
        reg.registrar("prueba", ReservaDePrueba)


def test_registro_rechaza_clase_que_no_extiende_reserva():
    class NoEsReserva(BaseModel):
        pass

    with pytest.raises(ErrorRegistroTipos, match="no extiende Reserva"):
        RegistroTipos().registrar("x", NoEsReserva)


# --- Broker --------------------------------------------------------------------
async def _sin_espera(_s: float) -> None:
    return None


def test_cola_llena_no_pierde_ni_descarta(cfg_broker):
    avisos: list[Aviso] = []
    b = Broker(cfg_broker, avisar=avisos.append)
    for i in range(5):
        b.publicar(NombreCola.CORREO, Mensaje(f"m{i}", i))
    with pytest.raises(ColaLlena):
        b.publicar(NombreCola.CORREO, Mensaje("m5", 5))
    assert b.tamano_actual(NombreCola.CORREO) == 5
    assert avisos == [Aviso("cola_llena", NombreCola.CORREO, "m5")]


def test_las_colas_son_independientes(cfg_broker):
    b = Broker(cfg_broker)
    for i in range(5):
        b.publicar(NombreCola.CORREO, Mensaje(f"m{i}", i))
    b.publicar(NombreCola.NOVEDADES, Mensaje("n0", 0))  # no falla


async def test_entrega_normal(cfg_broker):
    b = Broker(cfg_broker, dormir=_sin_espera)
    b.publicar(NombreCola.CORREO, Mensaje("m1", "hola"))
    vistos = []

    async def handler(m: Mensaje) -> None:
        vistos.append(m)

    assert await b.procesar_uno(NombreCola.CORREO, handler) is ResultadoEntrega.ENTREGADO
    assert [m.id for m in vistos] == ["m1"]
    assert await b.procesar_uno(NombreCola.CORREO, handler) is ResultadoEntrega.VACIA


async def test_retry_con_backoff_y_exito(cfg_broker):
    esperas: list[float] = []

    async def dormir(s: float) -> None:
        esperas.append(s)

    b = Broker(cfg_broker, dormir=dormir)
    b.publicar(NombreCola.CORREO, Mensaje("m1", None))
    intentos = 0

    async def handler(_m: Mensaje) -> None:
        nonlocal intentos
        intentos += 1
        if intentos < 3:
            raise RuntimeError("transitorio")

    assert await b.procesar_uno(NombreCola.CORREO, handler) is ResultadoEntrega.ENTREGADO
    assert intentos == 3
    assert esperas == [1.0, 2.0]


async def test_agota_reintentos_va_a_mensajes_muertos_con_aviso(cfg_broker):
    esperas: list[float] = []

    async def dormir(s: float) -> None:
        esperas.append(s)

    avisos: list[Aviso] = []
    b = Broker(cfg_broker, avisar=avisos.append, dormir=dormir)
    b.publicar(NombreCola.CORREO, Mensaje("m1", None))

    async def handler(_m: Mensaje) -> None:
        raise RuntimeError("siempre falla")

    assert await b.procesar_uno(NombreCola.CORREO, handler) is ResultadoEntrega.MUERTO
    assert esperas == [1.0, 2.0, 4.0]  # 3 reintentos: 1 s, 2 s, 4 s
    assert [m.id for m in b.mensajes_muertos(NombreCola.CORREO)] == ["m1"]
    assert avisos == [Aviso("mensaje_muerto", NombreCola.CORREO, "m1")]
    assert b.tamano_actual(NombreCola.CORREO) == 0
