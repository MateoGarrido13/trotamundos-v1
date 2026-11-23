# SPEC: SPEC-REF-01
# ELEMENTO PASO 5: Reserva y Registro de tipos (ITERACION_3)
# ADRs: ADR-IT3-005
# DRIVERS: QA-EVO-01, REF-01
import pytest

from tests.conftest import ReservaDePrueba
from trotamundos.app import create_app
from trotamundos.dominio.registro_tipos import ErrorRegistroTipos
from trotamundos.dominio.reserva import Reserva
from trotamundos.dominio.tipos_reserva import (
    ReservaAutobus, ReservaAuto, ReservaHotel, ReservaTren, ReservaVuelo,
)


def test_AC_REF_01_08_arranque_rechaza_tipo_duplicado_o_clase_invalida():
    with pytest.raises(ErrorRegistroTipos, match="ya está registrado"):
        create_app(tipos_extra={"hotel": ReservaDePrueba})
    with pytest.raises(ErrorRegistroTipos, match="no extiende Reserva"):
        create_app(tipos_extra={"nuevo": dict})


def test_arranque_registra_los_cinco_tipos_base():
    tipos = create_app().state.registro_tipos.tipos()
    assert tipos == {"hotel": ReservaHotel, "auto": ReservaAuto, "vuelo": ReservaVuelo,
                     "tren": ReservaTren, "autobus": ReservaAutobus}
    assert all(issubclass(c, Reserva) for c in tipos.values())


def test_arranque_acepta_tipo_extra_valido():
    app = create_app(tipos_extra={"prueba": ReservaDePrueba})
    assert app.state.registro_tipos.clase_de("prueba") is ReservaDePrueba
