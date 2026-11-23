"""Punto de entrada FastAPI. Cada slice agrega sus routers aquí."""
from __future__ import annotations

from fastapi import FastAPI

from trotamundos.broker import Broker
from trotamundos.config import Configuracion
from trotamundos.dominio.registro_tipos import RegistroTipos


def create_app(configuracion: Configuracion | None = None) -> FastAPI:
    cfg = configuracion or Configuracion()
    app = FastAPI(title="Trotamundos (prototipo)")
    app.state.configuracion = cfg
    app.state.broker = Broker(cfg.broker)
    app.state.registro_tipos = RegistroTipos()

    @app.get("/salud")
    def salud() -> dict[str, str]:
        return {"estado": "ok"}

    return app


app = create_app()
