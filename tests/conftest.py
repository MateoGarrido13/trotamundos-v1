from datetime import datetime

import pytest

from trotamundos.config import ConfiguracionBroker
from trotamundos.dominio.reserva import Reserva


class ReservaDePrueba(Reserva):
    """Tipo concreto mínimo para los tests del esqueleto."""

    def resumen(self) -> str:
        return f"Prueba {self.identificador}"


@pytest.fixture
def reserva_de_prueba():
    return ReservaDePrueba(
        identificador="r1", viaje_id="v1",
        inicio=datetime(2026, 12, 1), fin=datetime(2026, 12, 5),
    )


@pytest.fixture
def cfg_broker():
    """Colas de 5 y backoff 1 s, como las specs para los tests."""
    return ConfiguracionBroker(tamano_maximo_cola=5, reintentos=3, backoff_base_segundos=1.0)
