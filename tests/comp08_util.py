"""Ayudas de los tests de SPEC-COMP-08."""
import asyncio
import time
from types import SimpleNamespace

from trotamundos.broker import Broker, Mensaje, NombreCola
from trotamundos.config import ConfiguracionBroker
from trotamundos.notificaciones.canales import descubrir
from trotamundos.notificaciones.servicio import ServicioNotificaciones


def pedido(identificador: str, canal: str = "email", destinatario: str = "ana@mail.com", asunto: str = "Hola",
           cuerpo: str = "Texto") -> dict:
    return {"id": identificador, "canal": canal, "destinatario": destinatario,
            "propuesta": {"asunto": asunto, "cuerpo": cuerpo}}


def mensaje(**kw) -> Mensaje:
    p = pedido(**kw)
    return Mensaje(p["id"], p)


def armar(tamano_cola: int = 100, reintentos: int = 3, escala_espera: float = 0.0):
    """Un Broker, los tres canales simulados y el servicio. `escala_espera` hace que la espera del Retry
    dure esa fracción del valor real (0 = no espera) y queda registrada en `esperas` con el valor real."""
    esperas: list[float] = []
    avisos: list = []

    async def dormir(segundos: float) -> None:
        esperas.append(segundos)
        if escala_espera:
            await asyncio.sleep(segundos * escala_espera)

    broker = Broker(ConfiguracionBroker(tamano_maximo_cola=tamano_cola, reintentos=reintentos, backoff_base_segundos=1.0),
                    avisar=avisos.append, dormir=dormir)
    canales = {nombre: clase() for nombre, clase in descubrir().items()}
    servicio = ServicioNotificaciones(broker, canales)
    return SimpleNamespace(broker=broker, canales=canales, servicio=servicio, esperas=esperas, avisos=avisos)


def publicar(broker: Broker, **kw) -> Mensaje:
    m = mensaje(**kw)
    broker.publicar(NombreCola.NOTIFICACIONES, m)
    return m


class Cronometro:
    def __enter__(self):
        self.inicio = time.perf_counter()
        return self

    def __exit__(self, *_):
        self.segundos = time.perf_counter() - self.inicio


async def drenar(servicio, nombre: str) -> float:
    """Consume los pedidos de un canal hasta vaciarlos; devuelve cuánto tardó."""
    from trotamundos.broker import ResultadoEntrega

    inicio = time.perf_counter()
    while await servicio.procesar_canal(nombre) is not ResultadoEntrega.VACIA:
        pass
    return time.perf_counter() - inicio
