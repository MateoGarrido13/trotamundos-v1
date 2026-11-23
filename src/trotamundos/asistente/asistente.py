# SPEC: SPEC-REF-07
# ELEMENTO PASO 5: Módulo de Asistente Virtual (RONDA_2/ITERACION_1 y RONDA_2/ITERACION_2)
# ADRs: ADR-IT6-001, ADR-IT6-002, ADR-IT6-003, ADR-IT6-004, ADR-IT7-001, ADR-IT7-002, ADR-IT7-003, ADR-IT7-004
# DRIVERS: REF-07, QA-PER-05, QA-DIS-02, QA-SEG-04, QA-SEG-02
"""Módulo de Asistente Virtual: primer nivel de soporte interactivo.

**Sin estado**: lo que hay que recordar entre turnos viaja en el contexto firmado. No lee ni escribe
ninguna base, no llama a la API de la agencia y no importa al Orquestador: toda escritura es una
operación del Orquestador, con la identidad del actor y una clave de operación, y solo después de
una confirmación explícita del viajero. Nunca hace un Retry bloqueante contra el motor.

Un turno corre dentro de la cota de 35 segundos. Si el motor no responde (time-out de 20 segundos o
circuito abierto), si el filtro rechaza el mensaje o si el motor devuelve algo que no está en el
conjunto cerrado de intenciones, el viajero recibe el número de contacto de su agencia preferida y
el menú guiado. Las acciones guiadas (consultar, reprogramar, derivar, confirmar, cancelar) no usan el
motor."""
from __future__ import annotations

import asyncio
import time
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from trotamundos.asistente.circuito import CircuitBreaker
from trotamundos.asistente.contexto import AccionPendiente, Contexto, FirmaContexto
from trotamundos.asistente.filtro import FiltroInyeccion
from trotamundos.asistente.intenciones import Intencion, TipoIntencion, normalizar
from trotamundos.asistente.motor import ContextoMotor, IMotorConversacional
from trotamundos.config import ConfiguracionAsistente
from trotamundos.dominio.puertos_asistente import OrquestadorInterno, ResultadoOrquestador

T = TipoIntencion
MENU = ("consultar_estado", "reprogramar", "derivar_a_la_agencia")
MAX_DESCRIPCION = 2000


def _plano(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")


@dataclass
class RespuestaAsistente:
    tipo: str  # respuesta | propuesta | menu | rechazo | candidatas | resultado | caso_en_tramite | denegado | sin_agencia
    texto: str
    contexto: str  # el contexto firmado nuevo, que el cliente devuelve en el próximo turno
    agencia: str | None = None
    numero_agencia: str | None = None
    menu: list[str] | None = None
    propuesta: dict | None = None
    candidatas: list[dict] | None = None
    resultado: dict | None = None
    motivo: str | None = None

    def a_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


class ModuloAsistente:
    def __init__(
        self,
        motor: IMotorConversacional,
        orquestador: OrquestadorInterno,
        configuracion: ConfiguracionAsistente | None = None,
        *,
        filtro: FiltroInyeccion | None = None,
        circuito: CircuitBreaker | None = None,
        firma: FirmaContexto | None = None,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self._cfg = configuracion or ConfiguracionAsistente()
        self._motor = motor
        self._orq = orquestador
        self._filtro = filtro or FiltroInyeccion(self._cfg)
        self._reloj = reloj
        self._circuito = circuito or CircuitBreaker(
            self._cfg.umbral_circuito, self._cfg.apertura_circuito, reloj)
        self._firma = firma or FirmaContexto(self._cfg.clave_contexto, self._cfg.vigencia_contexto_minutos * 60)

    @property
    def circuito(self) -> CircuitBreaker:
        return self._circuito

    # --- turno de chat -------------------------------------------------------------------------
    async def turno(self, actor: str, itinerario_id: str, mensaje: str,
                    contexto_firmado: str | None = None) -> RespuestaAsistente:
        ctx = self._contexto(actor, itinerario_id, contexto_firmado)
        try:
            async with asyncio.timeout(self._cfg.cota_turno):  # 35 segundos para todo el turno
                return await self._turno(actor, itinerario_id, mensaje, ctx, self._reloj())
        except TimeoutError:
            return await self._degradar(actor, ctx, "tiempo_agotado")

    async def _turno(self, actor: str, itin: str, mensaje: str, ctx: Contexto, inicio: float) -> RespuestaAsistente:
        filtrado = self._filtro.revisar(mensaje)
        if not filtrado.aceptado:  # el filtro corre antes del motor y lo rechazado no entra al contexto
            return await self._degradar(actor, ctx, filtrado.motivo or "filtro", tipo="rechazo")
        self._recordar(ctx, mensaje)
        if not self._circuito.permitir():  # circuito abierto: sale de inmediato, sin llamar al proveedor
            return await self._degradar(actor, ctx, "circuito_abierto")

        reservas = await self._reservas_del_itinerario(actor, itin)
        restante = max(self._cfg.cota_turno - (self._reloj() - inicio), 0.0)
        try:
            crudo = await asyncio.wait_for(
                self._motor.interpretar(mensaje, ContextoMotor(
                    tuple(ctx.mensajes[-self._cfg.mensajes_resumen:]),
                    tuple({k: r.get(k) for k in ("identificador", "tipo", "lugar")} for r in reservas))),
                timeout=min(self._cfg.timeout_motor, restante))
        except asyncio.CancelledError:
            self._circuito.fallo()  # la cota del turno cortó una llamada de prueba
            raise
        except Exception:  # noqa: BLE001 - time-out o caída del proveedor: se degrada, sin Retry
            self._circuito.fallo()
            return await self._degradar(actor, ctx, "motor_no_responde")
        self._circuito.exito()
        return await self._atender(actor, itin, ctx, normalizar(crudo), mensaje, reservas)

    async def _atender(self, actor: str, itin: str, ctx: Contexto, i: Intencion, mensaje: str,
                       reservas: list[dict]) -> RespuestaAsistente:
        if i.tipo is T.FUERA_DE_ALCANCE:
            return await self._degradar(actor, ctx, "fuera_de_alcance", tipo="rechazo")
        if i.tipo is T.CONSULTAR_ESTADO:
            return await self._estado(actor, itin, ctx, i.referencia)
        if i.tipo is T.AGREGAR_RESERVA:
            return self._proponer_alta(ctx, itin, i.datos)
        # reprogramar, eliminar y caso complejo necesitan una única reserva: si no, se muestran las candidatas
        elegida = self._resolver(i.referencia, reservas)
        if elegida is None:
            return self._candidatas(ctx, reservas)
        if i.tipo is T.REPROGRAMAR:
            if not i.cambios:
                return self._responder(ctx, "respuesta", "¿Qué querés cambiar de esa reserva? Por ejemplo, la fecha de inicio o el lugar.")
            return self._proponer(ctx, T.REPROGRAMAR, {"reserva_id": elegida["identificador"], "cambios": i.cambios},
                                  f"Voy a reprogramar {self._nombre(elegida)}: {self._cambios(i.cambios)}.")
        if i.tipo is T.ELIMINAR_RESERVA:
            return self._proponer(ctx, T.ELIMINAR_RESERVA, {"reserva_id": elegida["identificador"]},
                                  f"Voy a eliminar {self._nombre(elegida)}.")
        return self._proponer(ctx, T.CASO_COMPLEJO, {"reserva_id": elegida["identificador"], "motivo": i.motivo or mensaje},
                              f"Esto necesita a tu agencia. Voy a abrir un caso por {self._nombre(elegida)}.")

    # --- acciones guiadas: no usan el motor ------------------------------------------------------
    async def accion(self, actor: str, itinerario_id: str, accion: dict[str, Any],
                     contexto_firmado: str | None = None) -> RespuestaAsistente:
        ctx = self._contexto(actor, itinerario_id, contexto_firmado)
        try:
            async with asyncio.timeout(self._cfg.cota_turno):
                return await self._accion(actor, itinerario_id, accion if isinstance(accion, dict) else {}, ctx)
        except TimeoutError:
            return await self._degradar(actor, ctx, "tiempo_agotado")

    async def _accion(self, actor: str, itin: str, accion: dict, ctx: Contexto) -> RespuestaAsistente:
        tipo = accion.get("tipo")
        if tipo == "consultar_estado":
            return await self._estado(actor, itin, ctx, accion.get("reserva_id"))
        if tipo == "reprogramar":
            reserva_id, cambios = accion.get("reserva_id"), accion.get("cambios")
            if not isinstance(reserva_id, str) or not isinstance(cambios, dict) or not cambios:
                return self._responder(ctx, "rechazo", "Indicá la reserva y qué querés cambiar.", motivo="datos_incompletos")
            # La existencia y el permiso los decide el Orquestador al confirmar, con su rechazo y su asiento.
            return self._proponer(ctx, T.REPROGRAMAR, {"reserva_id": reserva_id, "cambios": cambios},
                                  f"Voy a reprogramar la reserva {reserva_id}: {self._cambios(cambios)}.")
        if tipo == "derivar":
            reserva_id, motivo = accion.get("reserva_id"), accion.get("motivo")
            if not isinstance(reserva_id, str) or not isinstance(motivo, str):
                return self._responder(ctx, "rechazo", "Indicá la reserva y el motivo.", motivo="datos_incompletos")
            if not self._filtro.revisar(motivo).aceptado:  # el texto libre de una acción también pasa por el filtro
                return await self._degradar(actor, ctx, "filtro", tipo="rechazo")
            return self._proponer(ctx, T.CASO_COMPLEJO, {"reserva_id": reserva_id, "motivo": motivo},
                                  f"Voy a derivar a tu agencia el problema de la reserva {reserva_id}.")
        if tipo == "confirmar":
            return await self._confirmar(actor, itin, ctx)
        if tipo == "cancelar":
            ctx.pendiente = None
            return self._responder(ctx, "respuesta", "Listo, cancelé la acción. No se hizo ningún cambio.")
        return self._responder(ctx, "rechazo", "No reconozco esa acción.", motivo="accion_desconocida")

    async def _confirmar(self, actor: str, itin: str, ctx: Contexto) -> RespuestaAsistente:
        p = ctx.pendiente
        if p is None:  # confirmar sin acción pendiente: rechazo sin efecto
            return self._responder(ctx, "rechazo", "No hay ninguna acción pendiente de confirmar.", motivo="sin_accion_pendiente")
        try:
            r = await self._ejecutar(actor, itin, ctx, p)
        except Exception:  # noqa: BLE001 - la acción sigue pendiente: reintentar usa la misma clave de operación
            return self._responder(ctx, "rechazo", "No pude completar la acción. Podés reintentar la confirmación.", motivo="error")
        ctx.pendiente = None
        return await self._resultado(actor, ctx, p, r)

    async def _ejecutar(self, actor: str, itin: str, ctx: Contexto, p: AccionPendiente) -> ResultadoOrquestador:
        d = p.datos
        if p.tipo == T.REPROGRAMAR:
            return await self._orq.actualizar_reserva(actor, itin, d["reserva_id"], p.clave, d["cambios"])
        if p.tipo == T.ELIMINAR_RESERVA:
            return await self._orq.eliminar_reserva(actor, itin, d["reserva_id"], p.clave)
        if p.tipo == T.AGREGAR_RESERVA:
            return await self._orq.agregar_reserva(actor, itin, p.clave, d["solicitud"])
        # Caso complejo: el resumen se arma sin el motor. La agencia no se llama desde acá.
        return await self._orq.abrir_caso(actor, itin, p.clave, d["reserva_id"], d["motivo"][:MAX_DESCRIPCION],
                                          self._resumen(ctx, d))

    async def _resultado(self, actor: str, ctx: Contexto, p: AccionPendiente, r: ResultadoOrquestador) -> RespuestaAsistente:
        if r.estado == "ok":
            if p.tipo == T.CASO_COMPLEJO:
                return self._responder(ctx, "caso_en_tramite",
                                       "Abrí el caso con tu agencia: está «en trámite». Vas a ver las novedades en «Novedades».",
                                       resultado=r.datos)
            return self._responder(ctx, "resultado", f"Listo. {p.descripcion}", resultado=r.datos)
        if r.estado == "denegado":  # el Orquestador ya la auditó, igual que en la gestión manual
            return self._responder(ctx, "denegado", "No tenés permiso para hacer eso en este itinerario. Quedó registrado. "
                                   "Si querés, puedo derivarlo a tu agencia.", menu=list(MENU), motivo="acceso_denegado")
        if r.motivo == "sin_agencia_o_consentimiento":
            return self._responder(ctx, "sin_agencia", "Todavía no elegiste una agencia de viajes (o no diste tu consentimiento). "
                                   "Elegila para que pueda derivar el caso.", motivo=r.motivo)
        return self._responder(ctx, "rechazo", f"No se pudo completar: {self._motivo(r.motivo)}.", motivo=r.motivo)

    # --- estado, candidatas y propuestas ---------------------------------------------------------------
    async def _estado(self, actor: str, itin: str, ctx: Contexto, referencia: str | None) -> RespuestaAsistente:
        r = await self._orq.estado(actor, itin)
        if r.estado == "denegado":
            return self._responder(ctx, "denegado", "No tenés permiso para ver este itinerario.", motivo="acceso_denegado")
        reservas = r.datos.get("reservas", [])
        if referencia:
            reservas = self._coincidencias(referencia, reservas) or reservas
        lineas = [f"- {self._nombre(x)} ({x.get('estado', '')})" for x in reservas[:10]] or ["- No hay reservas vigentes."]
        novedades, casos = r.datos.get("novedades", []), r.datos.get("casos", [])
        texto = "Reservas:\n" + "\n".join(lineas)
        if novedades:
            texto += f"\nNovedades pendientes: {len(novedades)}."
        if casos:
            texto += "\nCasos: " + ", ".join(c.get("estado", "") for c in casos) + "."
        return self._responder(ctx, "respuesta", texto, resultado=r.datos)

    def _proponer_alta(self, ctx: Contexto, itin: str, datos: dict) -> RespuestaAsistente:
        faltan = [c for c in ("lugar", "inicio") if not datos.get(c)]
        if faltan:
            return self._responder(ctx, "respuesta", "Para agregarla necesito el lugar y la fecha. Por ejemplo: "
                                   "«agregar una actividad en Florencia el 2026-12-12».")
        solicitud = {"viaje_id": datos.get("viaje_id") or f"viaje-{itin}", "tipo": datos.get("tipo") or "actividad",
                     "inicio": datos["inicio"], "fin": datos.get("fin") or datos["inicio"], "lugar": datos["lugar"]}
        return self._proponer(ctx, T.AGREGAR_RESERVA, {"solicitud": solicitud},
                              f"Voy a agregar {solicitud['tipo']} en {solicitud['lugar']} el {solicitud['inicio']}.")

    def _proponer(self, ctx: Contexto, tipo: TipoIntencion, datos: dict, descripcion: str) -> RespuestaAsistente:
        """La clave de operación se genera acá, al proponer, y viaja en la acción pendiente: reintentar
        la confirmación usa la misma clave y el Orquestador no aplica la escritura dos veces."""
        ctx.pendiente = AccionPendiente(tipo=tipo.value, clave=f"asist-{uuid.uuid4().hex}", datos=datos,
                                        descripcion=descripcion)
        return self._responder(ctx, "propuesta", f"{descripcion} ¿Confirmás?",
                               propuesta={"accion": tipo.value, "descripcion": descripcion})

    def _candidatas(self, ctx: Contexto, reservas: list[dict]) -> RespuestaAsistente:
        """La intención no identifica una única reserva: no se adivina, se muestran las candidatas."""
        if not reservas:
            return self._responder(ctx, "respuesta", "No encuentro reservas en este itinerario.")
        return self._responder(ctx, "candidatas", "¿A cuál de estas reservas te referís?",
                               candidatas=[{k: r.get(k) for k in ("identificador", "tipo", "lugar", "inicio")}
                                           for r in reservas[:10]])

    def _resolver(self, referencia: str | None, reservas: list[dict]) -> dict | None:
        if not referencia:
            return None
        encontradas = self._coincidencias(referencia, reservas)
        return encontradas[0] if len(encontradas) == 1 else None

    @staticmethod
    def _coincidencias(referencia: str, reservas: list[dict]) -> list[dict]:
        exactas = [r for r in reservas if r.get("identificador") == referencia]
        if exactas:
            return exactas
        ref = _plano(referencia)
        return [r for r in reservas if ref and (ref in _plano(r.get("lugar") or "") or ref == _plano(r.get("tipo") or ""))]

    # --- degradación: número de la agencia y menú ----------------------------------------------------------
    async def _degradar(self, actor: str, ctx: Contexto, motivo: str, tipo: str = "menu") -> RespuestaAsistente:
        try:
            ag = await self._orq.agencia_preferida(actor)
        except Exception:  # noqa: BLE001
            ag = {"agencia": None, "contacto": None}
        if not ag.get("agencia"):  # sin agencia: se dice y se propone elegirla; nunca otro número
            return self._responder(ctx, "sin_agencia", "Por ahora no puedo ayudarte con eso, y todavía no tenés una agencia "
                                   "de viajes elegida. Elegila para poder contactarla.", menu=list(MENU), motivo=motivo)
        texto = (f"Por ahora no puedo ayudarte con eso. Podés comunicarte con {ag['agencia']}"
                 + (f" al {ag['contacto']}." if ag.get("contacto") else "."))
        r = self._responder(ctx, tipo, texto, menu=list(MENU), motivo=motivo)
        r.agencia, r.numero_agencia = ag["agencia"], ag.get("contacto")
        return r

    # --- contexto y utilidades ---------------------------------------------------------------------------------
    def _contexto(self, actor: str, itin: str, token: str | None) -> Contexto:
        """El contexto del cliente, o uno nuevo si falta, la firma no coincide, venció o es de otra cuenta."""
        return self._firma.verificar(token, actor, itin) or self._firma.nuevo(actor, itin)

    def _recordar(self, ctx: Contexto, mensaje: str) -> None:
        ctx.mensajes = (ctx.mensajes + [mensaje])[-self._cfg.mensajes_resumen:]

    def _responder(self, ctx: Contexto, tipo: str, texto: str, **extra: Any) -> RespuestaAsistente:
        return RespuestaAsistente(tipo=tipo, texto=texto, contexto=self._firma.firmar(ctx), **extra)

    async def _reservas_del_itinerario(self, actor: str, itin: str) -> list[dict]:
        try:
            r = await self._orq.reservas(actor, itin)
        except Exception:  # noqa: BLE001 - el motor puede interpretar sin las candidatas
            return []
        return list(r.datos.get("reservas", [])) if r.estado == "ok" else []

    def _resumen(self, ctx: Contexto, datos: dict) -> str:
        """El resumen del diálogo, armado sin el motor: motivo, reserva afectada y los últimos
        mensajes del viajero. Los que rechazó el filtro nunca entraron al contexto."""
        mensajes = "\n".join(f"- {m}" for m in ctx.mensajes[-self._cfg.mensajes_resumen:])
        return f"Motivo: {datos['motivo']}\nReserva afectada: {datos['reserva_id']}\nÚltimos mensajes del viajero:\n{mensajes}"

    @staticmethod
    def _nombre(r: dict) -> str:
        return f"{r.get('tipo', 'reserva')} en {r['lugar']}" if r.get("lugar") else f"{r.get('tipo', 'reserva')} {r.get('identificador', '')}"

    @staticmethod
    def _cambios(cambios: dict) -> str:
        return ", ".join(f"{k} → {v}" for k, v in cambios.items())

    @staticmethod
    def _motivo(motivo: str | None) -> str:
        return {"no_existe": "la reserva no existe", "en_baja": "la reserva ya está dada de baja",
                "campos_invalidos": "los datos no son válidos", "tipo_no_registrado": "ese tipo de reserva no existe",
                "reserva_inexistente": "la reserva no existe"}.get(motivo or "", motivo or "error")
