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

from trotamundos.broker import Broker
from trotamundos.config import ConfiguracionAgencias, ConfiguracionIngesta
from trotamundos.dominio.agencias import IAgencia
from trotamundos.dominio.puertos_casos import EntregaNovedadCaso
from trotamundos.entrada.agencia import AdaptadorAgencia, MockAgencia
from trotamundos.entrada.filtro_remitentes import FiltroWhitelist
from trotamundos.entrada.ingesta import ServicioIngesta
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
