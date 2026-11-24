# SPEC: SPEC-COMP-08 | PLAN-COMP-08 T-COMP-08-06
# ELEMENTO PASO 5: Servicio de notificaciones, ICanal (ITERACION_3)
# DRIVERS: QA-INT-02, QA-SEG-01
"""La app armada: el correo de recuperación de SPEC-COMP-05 sale por el canal Email de este servicio."""
import asyncio
from dataclasses import replace

import httpx
import pytest

from trotamundos.app import create_app
from trotamundos.broker import NombreCola, ResultadoEntrega
from trotamundos.config import Configuracion, ConfiguracionNotificaciones

pytestmark = pytest.mark.db


@pytest.fixture
def cfg(cuentas_limpias, bases_limpias, analitica_limpia):
    return Configuracion(bases=bases_limpias, analitica=analitica_limpia, identidad=cuentas_limpias)


@pytest.fixture
async def app(cfg):
    sistema = create_app(cfg)
    yield sistema
    sistema.state.red_regiones.cerrar()


async def test_AC_COMP_08_09_el_correo_de_recuperacion_sale_por_el_canal_email(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/auth/alta", json={"correo": "ana@mail.com", "contrasena": "clave-1", "region": "amer"})
        assert r.status_code == 201
        assert (await c.post("/auth/recuperacion", json={"correo": "ana@mail.com", "region": "amer"})).status_code == 202
    cola = NombreCola.NOTIFICACIONES
    servicio, canales = app.state.notificaciones.servicio, app.state.notificaciones.canales
    assert app.state.broker.tamano_actual(cola) == 1  # el publicador dejó el pedido en la cola
    assert await servicio.procesar_canal("email") is ResultadoEntrega.ENTREGADO
    [(destinatario, propuesta)] = canales["email"].enviados
    assert destinatario == "ana@mail.com" and "código" in propuesta.cuerpo
    assert canales["whatsapp"].llamadas == 0 and canales["instagram"].llamadas == 0
    assert app.state.broker.mensajes_muertos(cola) == []


async def test_el_supervisor_tiene_un_consumidor_por_canal(app):
    nombres = set(app.state.supervisor._consumidores)
    assert {"notificaciones:email", "notificaciones:whatsapp", "notificaciones:instagram",
            "notificaciones:sin_canal"} <= nombres
    assert {"novedades", "correo", "casos_ayuda", "eventos_analiticos"} <= nombres  # y los de antes


async def test_los_consumidores_corren_con_la_app_en_marcha(app):
    """Con el ciclo de vida activo (como en `uvicorn`), un pedido en la cola sale solo, sin invocar nada."""
    async with app.router.lifespan_context(app):
        await app.state.notificaciones.publicador.publicar(
            {"id": "n1", "canal": "email", "destinatario": "ana@mail.com", "propuesta": {"asunto": "A", "cuerpo": "C"}})
        for _ in range(100):
            if app.state.notificaciones.canales["email"].enviados:
                break
            await asyncio.sleep(0.05)
    assert [d for d, _ in app.state.notificaciones.canales["email"].enviados] == ["ana@mail.com"]


def test_la_cola_de_notificaciones_toma_su_tamano_de_la_configuracion(cfg):
    app = create_app(replace(cfg, notificaciones=ConfiguracionNotificaciones(tamano_cola_notificaciones=3)))
    try:
        broker = app.state.broker
        for i in range(3):
            asyncio.run(app.state.notificaciones.publicador.publicar(
                {"id": f"n{i}", "canal": "email", "destinatario": "a@x.com", "propuesta": {"asunto": "A", "cuerpo": "C"}}))
        assert broker.tamano_actual(NombreCola.NOTIFICACIONES) == 3
    finally:
        app.state.red_regiones.cerrar()


def test_un_canal_configurado_que_no_existe_rechaza_el_arranque(cfg):
    with pytest.raises(ValueError, match="telegram"):
        create_app(replace(cfg, notificaciones=ConfiguracionNotificaciones(canales=("email", "telegram"))))
