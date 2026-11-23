"""Punto de entrada FastAPI. Cada slice agrega sus routers aquí."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import asynccontextmanager

from fastapi import FastAPI

from trotamundos.broker import Broker
from trotamundos.config import Configuracion
from trotamundos.dominio.registro_tipos import RegistroTipos
from trotamundos.orquestador import api as api_viajes
from trotamundos.orquestador.archivado import tarea_periodica
from trotamundos.orquestador.arranque import registrar_tipos
from trotamundos.persistencia.base_viajes import BaseViajes
from trotamundos.persistencia.repositorio_viajes import RepositorioViajes


def create_app(configuracion: Configuracion | None = None,
               tipos_extra: Mapping[str, type] | None = None) -> FastAPI:
    cfg = configuracion or Configuracion()
    registro = RegistroTipos()
    # Un tipo duplicado o una clase que no extiende Reserva rechaza el arranque (AC-REF-01-08).
    registrar_tipos(registro, tipos_extra)
    base_viajes = BaseViajes.desde_config(cfg.bases)
    repositorio = RepositorioViajes(base_viajes, registro)

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI):
        tarea = asyncio.create_task(tarea_periodica(repositorio))
        try:
            yield
        finally:
            tarea.cancel()

    app = FastAPI(title="Trotamundos (prototipo)", lifespan=ciclo_de_vida)
    app.state.configuracion = cfg
    app.state.broker = Broker(cfg.broker)
    app.state.registro_tipos = registro
    app.state.base_viajes = base_viajes
    app.state.repositorio = repositorio
    app.include_router(api_viajes.router)

    @app.get("/salud")
    def salud() -> dict[str, str]:
        return {"estado": "ok"}

    return app


app = create_app()
