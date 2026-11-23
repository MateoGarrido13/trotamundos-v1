# SPEC: SPEC-REF-01
# ELEMENTO PASO 5: Orquestador de viajes, agrupación y vista principal (ITERACION_1)
# ADRs: ADR-001, ADR-IT3-005
# DRIVERS: REF-01, CON-01, QA-EVO-01
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from trotamundos.app import create_app
from trotamundos.dominio.reserva import Reserva
from trotamundos.dominio.tipos_reserva import ReservaHotel, ReservaVuelo
from trotamundos.orquestador import agrupacion
from trotamundos.orquestador.agrupacion import Agrupacion


@dataclass
class _Viaje:
    id: str
    viajero_id: str
    estado: str


class RepoEnMemoria:
    def __init__(self, viajes=(), reservas=()):
        self.viajes, self.reservas = list(viajes), list(reservas)

    def listar_viajes(self, viajero_id, estado):
        return [v for v in self.viajes if v.viajero_id == viajero_id and v.estado == estado]

    def reservas_de(self, viaje_ids):
        return [r for r in self.reservas if r.viaje_id in viaje_ids]


def _r(cls, ident, viaje):
    return cls(identificador=ident, viaje_id=viaje, inicio=datetime(2026, 12, 1), fin=datetime(2026, 12, 5))


def test_AC_REF_01_01_vista_principal_agrupa_reservas_por_viaje():
    repo = RepoEnMemoria(
        [_Viaje("v1", "ana", "activo"), _Viaje("v2", "ana", "activo"), _Viaje("v9", "otro", "activo")],
        [_r(ReservaVuelo, "r1", "v1"), _r(ReservaHotel, "r2", "v1"), _r(ReservaHotel, "r3", "v2"),
         _r(ReservaHotel, "r9", "v9")])
    vista = Agrupacion(repo).vista_principal("ana")
    assert [(v.id, [r.identificador for r in v.reservas]) for v in vista] == [
        ("v1", ["r1", "r2"]), ("v2", ["r3"])]


def test_AC_REF_01_03_tipo_nuevo_queda_agrupado_sin_cambiar_agrupacion():
    class ReservaCrucero(Reserva):
        def resumen(self) -> str:
            return "Crucero"

    app = create_app(tipos_extra={"crucero": ReservaCrucero})
    assert app.state.registro_tipos.clase_de("crucero") is ReservaCrucero
    repo = RepoEnMemoria([_Viaje("v1", "ana", "activo")],
                         [_r(ReservaHotel, "r1", "v1"), _r(ReservaCrucero, "r2", "v1")])
    [viaje] = Agrupacion(repo).vista_principal("ana")
    assert [type(r).__name__ for r in viaje.reservas] == ["ReservaHotel", "ReservaCrucero"]
    fuente = Path(agrupacion.__file__).read_text()
    assert "tipos_reserva" not in fuente and "ReservaHotel" not in fuente


def test_AC_REF_01_06_archivados_devuelve_viajes_o_lista_vacia():
    repo = RepoEnMemoria([_Viaje("v1", "ana", "archivado"), _Viaje("v2", "ana", "activo")],
                         [_r(ReservaHotel, "r1", "v1")])
    ag = Agrupacion(repo)
    [viaje] = ag.archivados("ana")
    assert viaje.id == "v1" and [r.identificador for r in viaje.reservas] == ["r1"]
    assert ag.archivados("sin_archivo") == []


def test_AC_REF_01_07_sin_viajes_activos_devuelve_lista_vacia():
    ag = Agrupacion(RepoEnMemoria([_Viaje("v1", "ana", "archivado")]))
    assert ag.vista_principal("ana") == []
    assert ag.vista_principal("nadie") == []
