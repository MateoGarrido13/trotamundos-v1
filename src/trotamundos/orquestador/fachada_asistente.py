# SPEC: SPEC-REF-07
# ELEMENTO PASO 5: Orquestador de viajes, interfaz interna que usa el Asistente (RONDA_2/ITERACION_1)
# ADRs: ADR-IT6-002, ADR-IT6-003
# DRIVERS: REF-07, QA-SEG-02
"""Implementa `OrquestadorInterno` con los servicios que ya existen. El Asistente propaga la identidad
del actor y una clave de operación: el control de acceso, la auditoría y la idempotencia son los de
cada operación (gestión manual de SPEC-REF-04, casos de SPEC-REF-05). No importa al Asistente."""
from __future__ import annotations

from typing import Any

from trotamundos.dominio.puertos_asistente import ResultadoOrquestador
from trotamundos.dominio.registro_tipos import RegistroTipos
from trotamundos.orquestador.casos import RespuestaCaso, ServicioCasos
from trotamundos.orquestador.gestion_reservas import (
    AccesoDenegado,
    GestionReservas,
    RespuestaOperacion,
    SolicitudReserva,
)
from trotamundos.orquestador.novedades import ServicioNovedades


class FachadaAsistente:
    def __init__(self, gestion: GestionReservas, casos: ServicioCasos, novedades: ServicioNovedades,
                 registro: RegistroTipos) -> None:
        self._gestion, self._casos, self._novedades = gestion, casos, novedades
        self._nombres = {clase: nombre for nombre, clase in registro.tipos().items()}

    async def reservas(self, actor: str, itinerario_id: str) -> ResultadoOrquestador:
        try:
            viajes = await self._gestion.vista(actor, itinerario_id)
        except AccesoDenegado:
            return ResultadoOrquestador("denegado")
        reservas = [{
            "identificador": r.identificador, "viaje_id": r.viaje_id, "tipo": self._nombres.get(type(r), type(r).__name__),
            "lugar": str(r.lugar) if r.lugar else None, "inicio": r.inicio.isoformat(),
            "fin": r.fin.isoformat(), "estado": r.estado.value,
        } for v in viajes for r in v.reservas]
        return ResultadoOrquestador("ok", datos={"reservas": reservas})

    async def estado(self, actor: str, itinerario_id: str) -> ResultadoOrquestador:
        r = await self.reservas(actor, itinerario_id)
        if r.estado != "ok":
            return r
        try:
            pendientes = await self._novedades.pendientes(actor, itinerario_id)
        except AccesoDenegado:
            pendientes = []
        casos = [c for c in await self._casos.consultar(actor) if c["itinerario_id"] == itinerario_id]
        return ResultadoOrquestador("ok", datos={
            **r.datos, "novedades": [{"id": n.id, "reserva_id": n.reserva_id} for n in pendientes], "casos": casos})

    async def agregar_reserva(self, actor, itinerario_id, clave, solicitud: dict[str, Any]) -> ResultadoOrquestador:
        s = SolicitudReserva(viaje_id=solicitud.get("viaje_id"), tipo=solicitud.get("tipo"),
                             inicio=solicitud.get("inicio"), fin=solicitud.get("fin"),
                             lugar=solicitud.get("lugar"), datos=solicitud.get("datos") or {})
        return self._operacion(await self._gestion.agregar(actor, itinerario_id, clave, s))

    async def actualizar_reserva(self, actor, itinerario_id, reserva_id, clave, cambios) -> ResultadoOrquestador:
        return self._operacion(await self._gestion.actualizar(actor, itinerario_id, reserva_id, clave, cambios))

    async def eliminar_reserva(self, actor, itinerario_id, reserva_id, clave) -> ResultadoOrquestador:
        return self._operacion(await self._gestion.eliminar(actor, itinerario_id, reserva_id, clave))

    async def abrir_caso(self, actor, itinerario_id, clave, reserva_id, descripcion, resumen_dialogo) -> ResultadoOrquestador:
        r: RespuestaCaso = await self._casos.reportar(actor, itinerario_id, clave, reserva_id, descripcion, resumen_dialogo)
        return ResultadoOrquestador(r.estado, r.motivo, r.caso or {}, r.repetida)

    async def agencia_preferida(self, actor: str) -> dict[str, str | None]:
        return await self._casos.consultar_agencia_preferida(actor)

    @staticmethod
    def _operacion(r: RespuestaOperacion) -> ResultadoOrquestador:
        return ResultadoOrquestador(r.estado, r.motivo, r.reserva or {}, r.repetida)
