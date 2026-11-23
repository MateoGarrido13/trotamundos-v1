"""Ayudas compartidas de los tests de SPEC-REF-07."""
from typing import Any

import pytest

from trotamundos.asistente.asistente import ModuloAsistente
from trotamundos.asistente.motor import MotorSimulado
from trotamundos.config import ConfiguracionAsistente
from trotamundos.dominio.puertos_asistente import ResultadoOrquestador

ESCALA = 0.02  # 35 s -> 0,7 s; time-out de 20 s -> 0,4 s; apertura de 30 s -> 0,6 s
CFG = ConfiguracionAsistente(clave_contexto="clave-de-prueba", escala_tiempos=ESCALA)
CONTACTO = "+54 11 4000-0001"
ESCRITURAS = {"agregar", "actualizar", "eliminar", "abrir_caso"}

RESERVAS = [
    {"identificador": "res-1", "viaje_id": "roma", "tipo": "hotel", "lugar": "Roma",
     "inicio": "2026-12-01T10:00:00", "fin": "2026-12-05T10:00:00", "estado": "confirmada"},
    {"identificador": "res-2", "viaje_id": "lima", "tipo": "vuelo", "lugar": "Lima",
     "inicio": "2026-12-08T10:00:00", "fin": "2026-12-08T18:00:00", "estado": "confirmada"},
]


class OrquestadorDeMemoria:
    """Doble del Orquestador: registra cada llamada y reconoce las claves de operación repetidas."""

    def __init__(self, reservas=None, agencia="agencia-a", contacto=CONTACTO):
        self.datos_reservas = list(RESERVAS if reservas is None else reservas)
        self.agencia = {"agencia": agencia, "contacto": contacto if agencia else None}
        self.llamadas: list[tuple] = []
        self.denegar = False
        self.rechazo: str | None = None
        self._claves: dict[str, ResultadoOrquestador] = {}

    @property
    def escrituras(self) -> list[tuple]:
        return [c for c in self.llamadas if c[0] in ESCRITURAS]

    async def reservas(self, actor, itinerario_id):
        self.llamadas.append(("reservas", actor, itinerario_id))
        if self.denegar:
            return ResultadoOrquestador("denegado")
        return ResultadoOrquestador("ok", datos={"reservas": self.datos_reservas})

    async def estado(self, actor, itinerario_id):
        self.llamadas.append(("estado", actor, itinerario_id))
        if self.denegar:
            return ResultadoOrquestador("denegado")
        return ResultadoOrquestador("ok", datos={"reservas": self.datos_reservas, "novedades": [{"id": "n1"}],
                                                 "casos": [{"estado": "abierto"}]})

    def _escribir(self, operacion: str, clave: str, *args: Any) -> ResultadoOrquestador:
        self.llamadas.append((operacion, clave, *args))
        if clave in self._claves:
            previa = self._claves[clave]
            return ResultadoOrquestador(previa.estado, previa.motivo, previa.datos, repetida=True)
        if self.denegar:
            return ResultadoOrquestador("denegado")
        if self.rechazo:
            return ResultadoOrquestador("rechazado", self.rechazo)
        r = ResultadoOrquestador("ok", datos={"operacion": operacion})
        self._claves[clave] = r
        return r

    async def agregar_reserva(self, actor, itinerario_id, clave, solicitud):
        return self._escribir("agregar", clave, actor, itinerario_id, solicitud)

    async def actualizar_reserva(self, actor, itinerario_id, reserva_id, clave, cambios):
        return self._escribir("actualizar", clave, actor, itinerario_id, reserva_id, cambios)

    async def eliminar_reserva(self, actor, itinerario_id, reserva_id, clave):
        return self._escribir("eliminar", clave, actor, itinerario_id, reserva_id)

    async def abrir_caso(self, actor, itinerario_id, clave, reserva_id, descripcion, resumen_dialogo):
        return self._escribir("abrir_caso", clave, actor, itinerario_id, reserva_id, descripcion, resumen_dialogo)

    async def agencia_preferida(self, actor):
        self.llamadas.append(("agencia_preferida", actor))
        return dict(self.agencia)


@pytest.fixture
def orq():
    return OrquestadorDeMemoria()


@pytest.fixture
def motor():
    return MotorSimulado()


@pytest.fixture
def modulo(orq, motor):
    return ModuloAsistente(motor, orq, CFG)


async def confirmar(modulo, respuesta, actor="luis", itinerario="familia"):
    return await modulo.accion(actor, itinerario, {"tipo": "confirmar"}, respuesta.contexto)
