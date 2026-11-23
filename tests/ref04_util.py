"""Ayudas compartidas de los tests de SPEC-REF-04."""
from datetime import UTC, datetime

import pytest

from trotamundos.app import create_app
from trotamundos.config import Configuracion
from trotamundos.orquestador.gestion_reservas import SolicitudReserva
from trotamundos.persistencia.repositorio_gestion import RepositorioGestion

AHORA = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
ITIN = "familia"
ANA, LUIS, INTRUSO = "ana", "luis", "intruso"  # organizadora, participante y sin membresía


def solicitud(viaje_id="roma", tipo="actividad", lugar="Coliseo", **extra) -> SolicitudReserva:
    return SolicitudReserva(viaje_id=viaje_id, tipo=tipo, lugar=lugar,
                            inicio=datetime(2026, 12, 2, 9), fin=datetime(2026, 12, 2, 12), **extra)


def precargar(app, itinerario=ITIN):
    """Un itinerario compartido con un organizador y un participante (datos de prueba)."""
    base = app.state.base_viajes
    base.escribir(lambda c: RepositorioGestion.agregar_membresia(c, itinerario, ANA, "organizador"))
    base.escribir(lambda c: RepositorioGestion.agregar_membresia(c, itinerario, LUIS, "participante"))


@pytest.fixture
def app(bases_limpias):
    app = create_app(Configuracion(bases=bases_limpias))
    precargar(app)
    return app


def asientos(app, itinerario=ITIN):
    return app.state.base_viajes.leer(lambda c: RepositorioGestion.asientos(c, itinerario))


def contar(bases, tabla):
    """Filas de una tabla en cada base: [primaria, pasiva]."""
    from trotamundos.persistencia.conexion import conectar
    out = []
    for dsn in (bases.viajes_primaria, bases.viajes_pasiva):
        with conectar(dsn) as c:
            out.append(c.execute(f"SELECT count(*) FROM {tabla}").fetchone()[0])
    return out


def viaje_en(app, viaje_id="roma", itinerario=ITIN):
    app.state.base_viajes.escribir(lambda c: c.execute(
        "INSERT INTO viaje (id, viajero_id, itinerario_id) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
        (viaje_id, ANA, itinerario)))


def reserva_externa(app, identificador, origen, viaje_id="roma"):
    """Una reserva que vino de un proveedor o del correo: sin `creado_por`."""
    from trotamundos.dominio.tipos_reserva import ReservaHotel
    viaje_en(app, viaje_id)
    app.state.repositorio.insertar_reserva(ReservaHotel(
        identificador=identificador, viaje_id=viaje_id, origen=origen,
        inicio=datetime(2026, 12, 1, 14), fin=datetime(2026, 12, 4, 10), lugar="Hotel Roma"))
