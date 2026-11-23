"""Punto de entrada FastAPI. Cada slice agrega sus routers aquí."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import asynccontextmanager

from fastapi import FastAPI

from trotamundos.broker import Broker
from trotamundos.config import Configuracion
from trotamundos.dominio.registro_tipos import RegistroTipos
from trotamundos.composicion import ensamblar_agencias, ensamblar_correo
from trotamundos.orquestador import api as api_viajes
from trotamundos.orquestador import api_casos, api_gestion, api_revision
from trotamundos.orquestador.archivado import tarea_periodica
from trotamundos.orquestador.arranque import registrar_tipos
from trotamundos.orquestador.casos import ServicioCasos
from trotamundos.orquestador.gestion_reservas import GestionReservas, tarea_purga_claves
from trotamundos.orquestador.incorporacion import IncorporadorReservas
from trotamundos.orquestador.novedades import ServicioNovedades
from trotamundos.orquestador.revision import ServicioRevision, tarea_purga
from trotamundos.persistencia.base_viajes import BaseViajes
from trotamundos.persistencia.repositorio_revision import RepositorioRevision
from trotamundos.persistencia.repositorio_viajes import RepositorioViajes


def create_app(configuracion: Configuracion | None = None,
               tipos_extra: Mapping[str, type] | None = None) -> FastAPI:
    cfg = configuracion or Configuracion()
    registro = RegistroTipos()
    # Un tipo duplicado o una clase que no extiende Reserva rechaza el arranque (AC-REF-01-08).
    registrar_tipos(registro, tipos_extra)
    base_viajes = BaseViajes.desde_config(cfg.bases)
    repositorio = RepositorioViajes(base_viajes, registro)
    gestion = GestionReservas(base_viajes, registro, repositorio, configuracion=cfg.gestion)
    broker = Broker(cfg.broker)
    casos = ServicioCasos(base_viajes, broker, cfg.agencias.disponibles, cfg.agencias)
    servicio_revision = ServicioRevision(
        RepositorioRevision(base_viajes, cfg.revision.tope_pendientes), cfg.revision)
    nodos_correo = ensamblar_correo(
        broker, servicio_revision, IncorporadorReservas(repositorio, registro), cfg.ingesta,
        entrega_casos=casos)

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI):
        tareas = [asyncio.create_task(tarea_periodica(repositorio)),
                  asyncio.create_task(tarea_purga(servicio_revision, cfg.revision.intervalo_purga_segundos)),
                  asyncio.create_task(tarea_purga_claves(gestion, cfg.revision.intervalo_purga_segundos))]
        try:
            yield
        finally:
            for tarea in tareas:
                tarea.cancel()

    app = FastAPI(title="Trotamundos (prototipo)", lifespan=ciclo_de_vida)
    app.state.configuracion = cfg
    app.state.broker = broker
    app.state.registro_tipos = registro
    app.state.base_viajes = base_viajes
    app.state.repositorio = repositorio
    app.state.servicio_revision = servicio_revision
    app.state.gestion = gestion
    app.state.casos = casos
    app.state.adaptador_agencia = ensamblar_agencias(broker, cfg.agencias)
    app.state.novedades = ServicioNovedades(base_viajes, registro)
    app.state.nodos_correo = nodos_correo
    app.include_router(api_viajes.router)
    app.include_router(api_revision.router)
    app.include_router(api_gestion.router)
    app.include_router(api_casos.router)

    @app.get("/salud")
    def salud() -> dict[str, str]:
        return {"estado": "ok"}

    return app


app = create_app()
