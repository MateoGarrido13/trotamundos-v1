"""Cliente de Gmail (SPEC-COMP-04). Solo `composicion.py` importa este paquete."""
from trotamundos.entrada.gmail.api import ApiGmail, ClienteHttp, crear_cliente_http
from trotamundos.entrada.gmail.oauth import AutorizacionRechazada, ServicioOAuth
from trotamundos.entrada.gmail.rutas import crear_router

__all__ = ["ApiGmail", "AutorizacionRechazada", "ClienteHttp", "ServicioOAuth", "crear_cliente_http", "crear_router"]
