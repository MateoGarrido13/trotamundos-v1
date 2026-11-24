# SPEC: SPEC-REF-04
# ELEMENTO PASO 5: Operaciones manuales de reserva (agregarReserva, actualizarReserva, eliminarReserva) (ITERACION_4)
# ADRs: ADR-IT4-008, ADR-IT4-007, ADR-IT4-009
# DRIVERS: REF-04, QA-SEG-02
"""Gestión manual de reservas: un único camino de escritura y de validación.

Cada operación es **una sola** escritura de `BaseViajes` (commit en dos fases): verifica el
permiso, revisa la clave de operación, valida, escribe la reserva y el asiento de auditoría y
guarda el resultado de la clave. Si algo falla, no queda ni la reserva ni el asiento de éxito.

Orden de validación (spec): permiso, clave de operación, existencia y estado, alcance del
participante, y al final el tipo y los campos. Primero el permiso, para no revelar a quien no
puede ver una reserva si existe.

La operación corre dos veces (una por base), así que todo lo que no es determinista (el
identificador de la reserva y la hora) se calcula antes y se pasa adentro."""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
from pydantic import ValidationError

from trotamundos.config import ConfiguracionGestion
from trotamundos.dominio.registro_tipos import ErrorRegistroTipos, RegistroTipos
from trotamundos.dominio.reserva import Origen, Reserva, texto_destino
from trotamundos.orquestador.agrupacion import Agrupacion, ViajeAgrupado
from trotamundos.orquestador.eventos_analiticos import EmisorEventos
from trotamundos.orquestador.control_acceso import (
    Decision,
    ModuloControlAcceso,
    Permiso,
    alcanza,
)
from trotamundos.persistencia.base_viajes import BaseViajes
from trotamundos.persistencia.repositorio_gestion import FilaReserva, RepositorioGestion
from trotamundos.persistencia.repositorio_viajes import CAMPOS_COMUNES, RepositorioViajes

log = logging.getLogger(__name__)

# Lo único de las reservas que se puede cambiar de las comunes; el tipo, el viaje, el
# identificador, el origen y el creador nunca cambian.
EDITABLES_COMUNES = {"inicio", "fin", "lugar", "estado"}


class AccesoDenegado(Exception):
    """El actor no tiene permiso sobre el itinerario (la respuesta de red lleva 403)."""


@dataclass(frozen=True)
class SolicitudReserva:
    viaje_id: str
    tipo: str
    inicio: datetime
    fin: datetime
    lugar: str | None = None
    datos: dict[str, Any] = field(default_factory=dict)  # campos propios del tipo


@dataclass(frozen=True)
class RespuestaOperacion:
    estado: str  # "ok" | "denegado" | "rechazado"
    operacion: str  # "agregar" | "actualizar" | "eliminar"
    motivo: str | None = None  # "no_existe" | "en_baja" | "tipo_no_registrado" | "campos_invalidos"
    reserva: dict | None = None
    repetida: bool = False  # el resultado es el de una operación anterior con la misma clave
    # Datos del evento analítico (SPEC-REF-06). No se guarda con la clave: una operación repetida no publica otro.
    evento: dict | None = None

    def a_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if k not in ("repetida", "evento")}

    @classmethod
    def repetida_de(cls, guardado: dict) -> RespuestaOperacion:
        return cls(**guardado, repetida=True)


def _ahora_utc() -> datetime:
    return datetime.now(UTC)


def reconstruir(registro: RegistroTipos, fila: FilaReserva, cambios: dict[str, Any]) -> Reserva:
    """La reserva con los cambios aplicados, validada por su clase concreta. Lanza
    `ValidationError` o `ValueError` si los cambios no son válidos."""
    clase = registro.clase_de(fila.tipo)
    propios = set(clase.model_fields) - CAMPOS_COMUNES - {"identificador"}
    desconocidos = set(cambios) - EDITABLES_COMUNES - propios
    if desconocidos:
        raise ValueError(f"campos que no se pueden cambiar: {sorted(desconocidos)}")
    datos = {
        "identificador": fila.identificador, "viaje_id": fila.viaje_id, "inicio": fila.inicio,
        "fin": fila.fin, "estado": fila.estado, "lugar": fila.lugar, "origen": fila.origen,
        "creado_por": fila.creado_por, "editada_manualmente": fila.editada_manualmente,
        "baja_en": fila.baja_en, **fila.datos, **cambios,
    }
    reserva = clase(**datos)
    if reserva.fin < reserva.inicio:
        raise ValueError("fin anterior a inicio")
    return reserva


class _FuenteItinerario:
    """Adapta el itinerario a lo que espera `Agrupacion`: la «identidad» es el itinerario."""

    def __init__(self, base: BaseViajes, repositorio: RepositorioViajes) -> None:
        self._base, self._repositorio = base, repositorio

    def listar_viajes(self, itinerario_id: str, estado: str) -> list:
        from types import SimpleNamespace
        filas = self._base.leer(
            lambda c: RepositorioGestion.viajes_del_itinerario(c, itinerario_id, estado))
        return [SimpleNamespace(id=i, estado=e) for i, e in filas]

    def reservas_de(self, viaje_ids: list[str]) -> list[Reserva]:
        return self._repositorio.reservas_de(viaje_ids)


class GestionReservas:
    def __init__(
        self,
        base: BaseViajes,
        registro: RegistroTipos,
        repositorio_viajes: RepositorioViajes,
        acceso: ModuloControlAcceso | None = None,
        configuracion: ConfiguracionGestion | None = None,
        *,
        reloj: Callable[[], datetime] = _ahora_utc,
        gancho_fallo: Callable[[], None] | None = None,
        emisor: EmisorEventos | None = None,
    ) -> None:
        self._base = base
        self._registro = registro
        self._acceso = acceso or ModuloControlAcceso()
        self._cfg = configuracion or ConfiguracionGestion()
        self._reloj = reloj
        # Solo para pruebas: se ejecuta dentro de la transacción, entre la reserva y el asiento.
        self._gancho_fallo = gancho_fallo
        self._fuente = _FuenteItinerario(base, repositorio_viajes)
        self._emisor = emisor  # SPEC-REF-06: publica el evento analítico después del commit

    # --- operaciones -------------------------------------------------------------
    async def agregar(self, actor: str, itinerario_id: str, clave: str,
                      solicitud: SolicitudReserva) -> RespuestaOperacion:
        ident, ahora = f"res-{uuid.uuid4().hex}", self._reloj()  # una vez: la operación corre en las dos bases
        respuesta = await asyncio.to_thread(
            self._escribir, lambda c: self._agregar(c, actor, itinerario_id, clave, solicitud, ident, ahora))
        self._emitir(respuesta, ahora)
        return respuesta

    async def actualizar(self, actor: str, itinerario_id: str, reserva_id: str, clave: str,
                         cambios: dict[str, Any]) -> RespuestaOperacion:
        ahora = self._reloj()
        respuesta = await asyncio.to_thread(
            self._escribir, lambda c: self._modificar(
                c, "actualizar", actor, itinerario_id, reserva_id, clave, cambios, ahora))
        self._emitir(respuesta, ahora)
        return respuesta

    async def eliminar(self, actor: str, itinerario_id: str, reserva_id: str,
                       clave: str) -> RespuestaOperacion:
        ahora = self._reloj()
        respuesta = await asyncio.to_thread(
            self._escribir, lambda c: self._modificar(
                c, "eliminar", actor, itinerario_id, reserva_id, clave, None, ahora))
        self._emitir(respuesta, ahora)
        return respuesta

    async def vista(self, actor: str, itinerario_id: str) -> list[ViajeAgrupado]:
        """Las reservas vigentes del itinerario, agrupadas por viaje. Cualquier miembro con
        permiso de ver la ve en su próxima consulta. Sin permiso: acceso denegado, con asiento."""
        decision = await asyncio.to_thread(
            self._base.leer, lambda c: self._acceso.verificar_permiso(c, actor, itinerario_id, Permiso.VER))
        if decision is Decision.DENEGADO:
            ahora = self._reloj()
            await asyncio.to_thread(self._base.escribir, lambda c: RepositorioGestion.auditar(
                c, cuenta_id=actor, itinerario_id=itinerario_id, operacion="vista",
                permiso=Permiso.VER, resultado="denegado", ahora=ahora))
            raise AccesoDenegado(f"{actor} no puede ver el itinerario {itinerario_id}")
        return await asyncio.to_thread(Agrupacion(self._fuente).vista_principal, itinerario_id)

    async def purgar_claves(self, ahora: datetime | None = None) -> int:
        limite = (ahora or self._reloj()) - timedelta(days=self._cfg.retencion_claves_dias)
        return await asyncio.to_thread(
            self._base.escribir, lambda c: RepositorioGestion.purgar_claves(c, limite))

    # --- dentro de la transacción ---------------------------------------------------
    def _agregar(self, c: psycopg.Connection, actor: str, itin: str, clave: str,
                 s: SolicitudReserva, ident: str, ahora: datetime) -> RespuestaOperacion:
        previo = self._previo(c, "agregar", Permiso.REGISTRAR, actor, itin, clave, ahora)
        if isinstance(previo, RespuestaOperacion):
            return previo
        # Tipo y campos, al final de la validación.
        try:
            clase = self._registro.clase_de(s.tipo)
        except ErrorRegistroTipos:
            return self._rechazar(c, "agregar", Permiso.REGISTRAR, actor, itin, clave, ahora,
                                  "tipo_no_registrado")
        itin_del_viaje = RepositorioGestion.itinerario_del_viaje(c, s.viaje_id)
        if itin_del_viaje is not None and itin_del_viaje != itin:
            return self._rechazar(c, "agregar", Permiso.REGISTRAR, actor, itin, clave, ahora,
                                  "campos_invalidos")
        if set(s.datos) & (CAMPOS_COMUNES | {"identificador"}):
            return self._rechazar(c, "agregar", Permiso.REGISTRAR, actor, itin, clave, ahora,
                                  "campos_invalidos")
        try:
            reserva = clase(identificador=ident, viaje_id=s.viaje_id, inicio=s.inicio, fin=s.fin,
                            lugar=s.lugar, origen=Origen.MANUAL, creado_por=actor, **s.datos)
            if reserva.fin < reserva.inicio:
                raise ValueError("fin anterior a inicio")
        except (ValidationError, ValueError, TypeError):
            return self._rechazar(c, "agregar", Permiso.REGISTRAR, actor, itin, clave, ahora,
                                  "campos_invalidos")
        if itin_del_viaje is None:
            RepositorioGestion.crear_viaje(c, s.viaje_id, actor, itin)
        RepositorioGestion.insertar_reserva(c, reserva, s.tipo)
        return self._confirmar(
            c, "agregar", Permiso.REGISTRAR, actor, itin, clave, ahora, ident,
            {"tipo": s.tipo, **reserva.model_dump(mode="json")},
            evento={"tipo": "alta", "tipo_reserva": s.tipo, "destino": texto_destino(reserva.lugar),
                    "inicio": reserva.inicio, "fin": reserva.fin, "origen": reserva.origen.value,
                    "estado": reserva.estado.value})

    def _modificar(self, c: psycopg.Connection, operacion: str, actor: str, itin: str,
                   reserva_id: str, clave: str, cambios: dict | None,
                   ahora: datetime) -> RespuestaOperacion:
        previo = self._previo(c, operacion, Permiso.MODIFICAR, actor, itin, clave, ahora, reserva_id)
        if isinstance(previo, RespuestaOperacion):
            return previo
        decision: Decision = previo
        fila = RepositorioGestion.reserva(c, reserva_id)
        if fila is None or fila.itinerario_id != itin:
            return self._rechazar(c, operacion, Permiso.MODIFICAR, actor, itin, clave, ahora,
                                  "no_existe", reserva_id)
        if fila.baja_en is not None:
            return self._rechazar(c, operacion, Permiso.MODIFICAR, actor, itin, clave, ahora,
                                  "en_baja", reserva_id)
        if not alcanza(decision, fila.creado_por, actor):  # el participante solo toca lo suyo
            return self._denegar(c, operacion, Permiso.MODIFICAR, actor, itin, clave, ahora, reserva_id)
        if operacion == "eliminar":
            RepositorioGestion.dar_de_baja(c, reserva_id, ahora)
            cuerpo: dict = {"identificador": reserva_id, "baja_en": ahora.isoformat()}
            evento = {"tipo": "baja", "tipo_reserva": fila.tipo, "destino": texto_destino(fila.lugar),
                      "inicio": fila.inicio, "fin": fila.fin, "origen": fila.origen, "estado": fila.estado}
        else:
            try:
                if not cambios:
                    raise ValueError("sin cambios")
                reserva = reconstruir(self._registro, fila, cambios)
            except (ValidationError, ValueError, TypeError, ErrorRegistroTipos):
                return self._rechazar(c, operacion, Permiso.MODIFICAR, actor, itin, clave, ahora,
                                      "campos_invalidos", reserva_id)
            RepositorioGestion.actualizar_reserva(c, reserva)  # queda marcada como editada a mano
            cuerpo = {"tipo": fila.tipo, **reserva.model_dump(mode="json"), "editada_manualmente": True}
            evento = {"tipo": "modificacion", "tipo_reserva": fila.tipo, "destino": texto_destino(reserva.lugar),
                      "inicio": reserva.inicio, "fin": reserva.fin, "origen": fila.origen,
                      "estado": reserva.estado.value}
        return self._confirmar(c, operacion, Permiso.MODIFICAR, actor, itin, clave, ahora, reserva_id,
                               cuerpo, evento=evento)

    def _previo(self, c, operacion, permiso, actor, itin, clave, ahora, reserva_id=None):
        """Permiso y clave de operación. Devuelve una `RespuestaOperacion` si ya se resolvió
        (denegado o repetida) o la decisión de acceso si hay que seguir."""
        decision = self._acceso.verificar_permiso(c, actor, itin, permiso)
        if decision is Decision.DENEGADO:
            return self._denegar(c, operacion, permiso, actor, itin, clave, ahora, reserva_id)
        guardado = RepositorioGestion.clave(c, actor, clave)
        if guardado is not None:  # mismo resultado, aunque el contenido sea distinto
            return RespuestaOperacion.repetida_de(guardado)
        return decision

    def _denegar(self, c, operacion, permiso, actor, itin, clave, ahora, reserva_id=None):
        self._auditar(c, operacion, permiso, actor, itin, "denegado", ahora, reserva_id, clave)
        return RespuestaOperacion("denegado", operacion)

    def _rechazar(self, c, operacion, permiso, actor, itin, clave, ahora, motivo, reserva_id=None):
        self._auditar(c, operacion, permiso, actor, itin, "rechazado", ahora, reserva_id, clave, motivo)
        return RespuestaOperacion("rechazado", operacion, motivo)

    def _emitir(self, respuesta: RespuestaOperacion, ahora: datetime) -> None:
        """Publica el evento analítico **después** del commit y sin esperar. Una operación
        repetida (la clave ya se aplicó) no publica otro."""
        if self._emisor and respuesta.estado == "ok" and not respuesta.repetida and respuesta.evento:
            self._emisor.emitir(respuesta.evento, ahora)

    def _confirmar(self, c, operacion, permiso, actor, itin, clave, ahora, reserva_id, cuerpo, evento=None):
        if self._gancho_fallo:
            self._gancho_fallo()
        self._auditar(c, operacion, permiso, actor, itin, "permitido", ahora, reserva_id, clave)
        respuesta = RespuestaOperacion("ok", operacion, reserva=cuerpo, evento=evento)
        RepositorioGestion.guardar_clave(c, actor, clave, respuesta.a_dict(), ahora)
        return respuesta

    @staticmethod
    def _auditar(c, operacion, permiso, actor, itin, resultado, ahora, reserva_id, clave, motivo=None):
        RepositorioGestion.auditar(
            c, cuenta_id=actor, itinerario_id=itin, operacion=operacion, permiso=permiso,
            resultado=resultado, ahora=ahora, reserva_id=reserva_id, clave=clave, motivo=motivo)

    def _escribir(self, operacion):
        try:
            return self._base.escribir(operacion)
        except psycopg.errors.UniqueViolation:
            # Dos pedidos con la misma clave chocaron: el segundo ya encuentra el resultado.
            return self._base.escribir(operacion)


async def tarea_purga_claves(gestion: GestionReservas, intervalo_segundos: float) -> None:
    """Proceso periódico que elimina las claves de operación que cumplieron la retención."""
    while True:
        try:
            await gestion.purgar_claves()
        except Exception:  # una base caída no mata el proceso periódico
            log.exception("falló la purga periódica de claves de operación")
        await asyncio.sleep(intervalo_segundos)
