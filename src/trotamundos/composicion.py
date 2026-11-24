# SPEC: SPEC-REF-03
# ELEMENTO PASO 5: Filtro de remitentes, Servicio de ingesta y Orquestador de viajes (ITERACION_3)
# ADRs: ADR-IT3-008, ADR-IT3-010
# DRIVERS: REF-03, QA-SEG-03*
"""Ensamble del camino del correo: Filtro de remitentes -> Servicio de ingesta -> Orquestador.

Es el único lugar que conecta `entrada` con `orquestador`. En el paso 5 esas conexiones son
HTTP/REST interno; en el prototipo son llamadas a método detrás de los `Protocol` de
`dominio/puertos_correo.py`."""
from __future__ import annotations

from dataclasses import dataclass

from collections.abc import Mapping

from fastapi import APIRouter

from trotamundos.asistente.asistente import ModuloAsistente
from trotamundos.asistente.motor import IMotorConversacional, MotorSimulado
from trotamundos.broker import Broker
from trotamundos.config import ConfiguracionAgencias, ConfiguracionAsistente, ConfiguracionGmail, ConfiguracionIngesta
from trotamundos.dominio.agencias import IAgencia
from trotamundos.dominio.puertos_casos import EntregaNovedadCaso
from trotamundos.entrada.agencia import AdaptadorAgencia, MockAgencia
from trotamundos.entrada.filtro_remitentes import FiltroWhitelist
from trotamundos.entrada.gestor_autorizacion import GestorAutorizacion
from trotamundos.entrada.gmail import ApiGmail, ClienteHttp, ServicioOAuth, crear_cliente_http
from trotamundos.entrada.gmail import crear_router as crear_router_oauth
from trotamundos.entrada.ingesta import ServicioIngesta
from trotamundos.orquestador.fachada_asistente import FachadaAsistente
from trotamundos.orquestador.incorporacion import IncorporadorReservas
from trotamundos.orquestador.revision import ServicioRevision


@dataclass(frozen=True)
class NodosCorreo:
    filtro: FiltroWhitelist
    ingesta: ServicioIngesta


def ensamblar_correo(
    broker: Broker,
    servicio_revision: ServicioRevision,
    incorporador: IncorporadorReservas,
    configuracion_ingesta: ConfiguracionIngesta | None = None,
    entrega_casos: EntregaNovedadCaso | None = None,
) -> NodosCorreo:
    ingesta = ServicioIngesta(broker, incorporador, configuracion_ingesta, entrega_casos=entrega_casos)
    filtro = FiltroWhitelist(servicio_revision, ingesta)
    servicio_revision.liberador = filtro  # el Orquestador avisa y el filtro libera hacia la ingesta
    return NodosCorreo(filtro, ingesta)


def ensamblar_agencias(
    broker: Broker,
    configuracion: ConfiguracionAgencias,
    agencias: Mapping[str, IAgencia] | None = None,
) -> AdaptadorAgencia:
    """Registra un adaptador por cada agencia configurada (SPEC-REF-05). En el prototipo cada una
    es un `MockAgencia`; una agencia nueva es un adaptador más en este registro, y el
    Orquestador solo necesita conocer su nombre."""
    registro = dict(agencias) if agencias is not None else {
        nombre: MockAgencia(nombre) for nombre in configuracion.disponibles}
    return AdaptadorAgencia(broker, registro, configuracion)


def ensamblar_asistente(
    orquestador_app,
    motor: IMotorConversacional | None = None,
    configuracion: ConfiguracionAsistente | None = None,
) -> ModuloAsistente:
    """El Módulo de Asistente sobre los servicios del Orquestador (`app.state` de su app). Es el
    único lugar que conecta `asistente` con `orquestador`. Sin motor, usa el simulado."""
    st = orquestador_app.state
    fachada = FachadaAsistente(st.gestion, st.casos, st.novedades, st.registro_tipos)
    cfg = configuracion or st.configuracion.asistente
    return ModuloAsistente(motor or MotorSimulado(), fachada, cfg)


@dataclass(frozen=True)
class SistemaGmail:
    """El correo real (SPEC-COMP-04): la API de lectura, el flujo OAuth y sus rutas."""

    api: ApiGmail
    oauth: ServicioOAuth
    router: APIRouter
    cliente: ClienteHttp

    async def al_revocar(self, titular_id: str, token: str) -> None:
        await self.oauth.revocar_en_google(titular_id, token)

    async def cerrar(self) -> None:
        await self.cliente.aclose()


def ensamblar_gmail(
    configuracion: ConfiguracionGmail,
    gestor: GestorAutorizacion,
    cliente: ClienteHttp | None = None,
) -> SistemaGmail:
    """Es el único lugar que conecta `entrada.gmail` con el resto. Un `cliente` inyectado (con
    transporte simulado) permite probarlo sin red."""
    cliente = cliente or crear_cliente_http()
    oauth = ServicioOAuth(gestor, cliente, configuracion)
    return SistemaGmail(ApiGmail(cliente, configuracion), oauth, crear_router_oauth(oauth), cliente)
