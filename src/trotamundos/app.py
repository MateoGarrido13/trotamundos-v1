"""Punto de entrada FastAPI. Cada slice agrega sus routers aquí."""
from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import Mapping
from contextlib import asynccontextmanager
from dataclasses import replace

from cryptography.fernet import Fernet
from fastapi import FastAPI

from trotamundos.broker import Broker, NombreCola
from trotamundos.config import Configuracion
from trotamundos.dominio.registro_tipos import RegistroTipos
from trotamundos.analitica import app as app_analitica
from trotamundos.analitica.base import aplicar_esquema as aplicar_esquema_analitico
from trotamundos.analitica.base import conectar as conectar_analitica
from trotamundos.analitica.consultas import ServicioConsultas
from trotamundos.analitica.proyector import Proyector
from trotamundos.asistente import app as app_asistente
from trotamundos.composicion import (
    ensamblar_agencias, ensamblar_asistente, ensamblar_correo, ensamblar_cotizacion, ensamblar_gmail)
from trotamundos.cotizacion import api as api_cotizacion
from trotamundos.consumidores import Supervisor
from trotamundos.entrada import app as app_entrada
from trotamundos.entrada import api_agencia
from trotamundos.entrada.adaptador_correo import AdaptadorCorreo
from trotamundos.entrada.api_correo import MockApiCorreo
from trotamundos.entrada.consumidor_correo import ConsumidorCorreo
from trotamundos.entrada.gestor_autorizacion import CifradorTokens, GestorAutorizacion, RepositorioTokensPostgres
from trotamundos.entrada.parseo_aislado.cliente import ClienteParseo
from trotamundos.entrada.programador_sondeo import ProgramadorSondeo
from trotamundos.orquestador import api as api_viajes
from trotamundos.orquestador import api_casos, api_gestion, api_miembros, api_revision
from trotamundos.orquestador.alta_viajes import ServicioViajes
from trotamundos.orquestador.archivado import tarea_periodica
from trotamundos.orquestador.arranque import registrar_tipos
from trotamundos.orquestador.casos import ServicioCasos
from trotamundos.orquestador.eventos_analiticos import EmisorEventos
from trotamundos.orquestador.gestion_reservas import GestionReservas, tarea_purga_claves
from trotamundos.orquestador.incorporacion import IncorporadorReservas
from trotamundos.orquestador.novedades import ServicioNovedades
from trotamundos.orquestador.revision import ServicioRevision, tarea_purga
from trotamundos.persistencia.base_viajes import BaseViajes
from trotamundos.persistencia.conexion import conectar
from trotamundos.persistencia.esquemas import aplicar_esquemas
from trotamundos.persistencia.repositorio_revision import RepositorioRevision
from trotamundos.persistencia.repositorio_viajes import RepositorioViajes

log = logging.getLogger(__name__)


def _con_claves_de_desarrollo(cfg: Configuracion) -> Configuracion:
    """SPEC-COMP-01, D3: sin clave en el entorno se genera una efímera y se avisa. En producción
    las claves se exigen por entorno (`TROTA_CLAVE_TOKENS`, `TROTA_CLAVE_ASISTENTE`)."""
    if not cfg.correo.clave_tokens:
        log.warning("TROTA_CLAVE_TOKENS vacía: se usa una clave efímera (los tokens no sobreviven al reinicio)")
        cfg = replace(cfg, correo=replace(cfg.correo, clave_tokens=Fernet.generate_key().decode()))
    if not cfg.asistente.clave_contexto:
        log.warning("TROTA_CLAVE_ASISTENTE vacía: se usa una clave efímera")
        cfg = replace(cfg, asistente=replace(cfg.asistente, clave_contexto=secrets.token_hex(32)))
    return cfg


def _aplicar_esquemas(cfg: Configuracion) -> None:
    """Las bases nuevas quedan listas al arrancar (todos los `.sql` usan IF NOT EXISTS). Una base
    caída no impide arrancar: la operación que la necesite responderá 503."""
    for dsn in (cfg.bases.viajes_primaria, cfg.bases.viajes_pasiva):
        try:
            with conectar(dsn, autocommit=True) as conn:
                aplicar_esquemas(conn)
        except Exception:  # noqa: BLE001
            log.exception("no se pudieron aplicar los esquemas en una base de viajes")
    try:
        with conectar_analitica(cfg.analitica.dsn, autocommit=True) as conn:
            aplicar_esquema_analitico(conn)
    except Exception:  # noqa: BLE001
        log.exception("no se pudo aplicar el esquema de la Base analítica")


def create_app(configuracion: Configuracion | None = None,
               tipos_extra: Mapping[str, type] | None = None) -> FastAPI:
    cfg = _con_claves_de_desarrollo(configuracion or Configuracion())
    registro = RegistroTipos()
    # Un tipo duplicado o una clase que no extiende Reserva rechaza el arranque (AC-REF-01-08).
    registrar_tipos(registro, tipos_extra)
    base_viajes = BaseViajes.desde_config(cfg.bases)
    repositorio = RepositorioViajes(base_viajes, registro)
    broker = Broker(cfg.broker, tamanos={NombreCola.EVENTOS_ANALITICOS: cfg.analitica.tamano_cola_eventos})
    emisor = EmisorEventos(broker, cfg.analitica)  # SPEC-REF-06: eventos anonimizados tras cada commit
    gestion = GestionReservas(base_viajes, registro, repositorio, configuracion=cfg.gestion, emisor=emisor)
    casos = ServicioCasos(base_viajes, broker, cfg.agencias.disponibles, cfg.agencias)
    servicio_revision = ServicioRevision(
        RepositorioRevision(base_viajes, cfg.revision.tope_pendientes), cfg.revision)
    nodos_correo = ensamblar_correo(
        broker, servicio_revision, IncorporadorReservas(repositorio, registro, emisor), cfg.ingesta,
        entrega_casos=casos)

    # SPEC-COMP-01: correo (mock hasta que exista el adaptador real), consumidores y analítica.
    gestor_correo = GestorAutorizacion(
        RepositorioTokensPostgres(base_viajes), CifradorTokens(cfg.correo.clave_tokens), cfg.correo)
    # SPEC-COMP-04: con credenciales de Google el correo es real; sin ellas, el simulado.
    gmail = ensamblar_gmail(cfg.gmail, gestor_correo) if cfg.gmail.habilitado else None
    if gmail is None:
        log.warning("TROTA_GMAIL_CLIENT_ID/TROTA_GMAIL_CLIENT_SECRET sin definir: se usa el correo simulado")
    api_correo = gmail.api if gmail else MockApiCorreo()
    sondeo = ProgramadorSondeo(AdaptadorCorreo(api_correo, gestor_correo, broker, cfg.correo), gestor_correo, cfg.correo)
    parseo = ClienteParseo()
    consumidor_correo = ConsumidorCorreo(broker, parseo, nodos_correo.filtro)
    adaptador_agencia = ensamblar_agencias(broker, cfg.agencias)
    proyector = Proyector(broker, cfg.analitica.dsn)
    supervisor = Supervisor()
    cotizacion = ensamblar_cotizacion(cfg.cotizacion)  # SPEC-COMP-06: sin Broker ni base
    # Un consumidor por cola. La de notificaciones no tiene consumidor: no hay spec que la use (QA-INT-02).
    supervisor.registrar("novedades", nodos_correo.ingesta.procesar_uno)
    supervisor.registrar("correo", consumidor_correo.procesar_uno)
    supervisor.registrar("casos_ayuda", adaptador_agencia.procesar_uno)
    supervisor.registrar("eventos_analiticos", proyector.procesar_uno)

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI):
        await asyncio.to_thread(_aplicar_esquemas, cfg)
        tareas = [asyncio.create_task(tarea_periodica(repositorio, emisor=emisor)),
                  asyncio.create_task(tarea_purga(servicio_revision, cfg.revision.intervalo_purga_segundos)),
                  asyncio.create_task(tarea_purga_claves(gestion, cfg.revision.intervalo_purga_segundos)),
                  asyncio.create_task(sondeo.ejecutar()),
                  asyncio.create_task(cotizacion.balanceador.ejecutar())]
        supervisor.iniciar()
        try:
            yield
        finally:
            await supervisor.detener()
            for tarea in tareas:
                tarea.cancel()
            await asyncio.gather(*tareas, return_exceptions=True)
            await parseo.cerrar()
            await cotizacion.borde.cerrar()
            if gmail:
                await gmail.cerrar()

    app = FastAPI(title="Trotamundos (prototipo)", lifespan=ciclo_de_vida)
    app.state.configuracion = cfg
    app.state.broker = broker
    app.state.registro_tipos = registro
    app.state.base_viajes = base_viajes
    app.state.repositorio = repositorio
    app.state.servicio_revision = servicio_revision
    app.state.gestion = gestion
    app.state.casos = casos
    app.state.adaptador_agencia = adaptador_agencia
    app.state.novedades = ServicioNovedades(base_viajes, registro, emisor=emisor)
    app.state.emisor_eventos = emisor
    app.state.nodos_correo = nodos_correo
    app.state.servicio_viajes = ServicioViajes(base_viajes)
    app.state.supervisor = supervisor
    app.state.api_correo = api_correo
    app.state.gestor_correo = gestor_correo
    app.state.gmail = gmail
    app.state.proyector = proyector
    app.state.cotizacion = cotizacion
    app.include_router(api_viajes.router)
    app.include_router(api_revision.router)
    app.include_router(api_gestion.router)
    app.include_router(api_casos.router)
    app.include_router(api_miembros.router)
    app.include_router(api_agencia.crear_router(adaptador_agencia))
    app.include_router(app_entrada.crear_router(gestor_correo, al_revocar=gmail.al_revocar if gmail else None))
    if gmail:
        app.include_router(gmail.router)
    app.include_router(api_cotizacion.crear_router(cotizacion.borde))
    app.include_router(app_analitica.crear_router(ServicioConsultas(cfg.analitica)))
    app.include_router(app_asistente.crear_router(ensamblar_asistente(app, configuracion=cfg.asistente)))

    @app.get("/salud")
    def salud() -> dict[str, str]:
        return {"estado": "ok"}

    return app


app = create_app()
