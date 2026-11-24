# SPEC: SPEC-COMP-03
# ELEMENTO PASO 5: Cliente móvil con módulo local de proximidad GPS (ITERACION_5)
# DRIVERS: CON-01, QA-PER-03, QA-USA-01, REF-07, QA-PER-01, REF-03
"""Criterios del cliente móvil, en Chromium, contra la app principal."""
from __future__ import annotations

import json
import socket
import threading
import time
import urllib.request
import uuid
from dataclasses import replace
from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect

from trotamundos.app import create_app
from trotamundos.config import Configuracion

pytestmark = [pytest.mark.db, pytest.mark.navegador]

AQUI = {"latitude": -34.6037, "longitude": -58.3816}
LEJOS = {"latitude": -34.70, "longitude": -58.50}
CERCA = {"latitude": -34.6040, "longitude": -58.3820}


@pytest.fixture
def cfg(cuentas_limpias, bases_limpias, analitica_limpia):
    return Configuracion(
        bases=bases_limpias, analitica=analitica_limpia,
        identidad=replace(cuentas_limpias, exigir_gateway=True))


@pytest.fixture
def servidor(cfg):
    import uvicorn

    class Servidor(uvicorn.Server):
        def install_signal_handlers(self) -> None:
            pass

    sistema = create_app(cfg)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    puerto = sock.getsockname()[1]
    server = Servidor(uvicorn.Config(sistema, log_level="warning"))
    hilo = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    hilo.start()
    base = f"http://127.0.0.1:{puerto}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/salud", timeout=0.3).close()
            break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError("el cliente móvil no llegó a /salud")
    yield base
    server.should_exit = True
    hilo.join(5)
    sistema.state.red_regiones.cerrar()


@pytest.fixture
def navegador():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


def _correo() -> str:
    return f"movil-{uuid.uuid4().hex[:8]}@mail.com"


def _espia_gps(context):
    context.add_init_script("""
      window.__gps = 0;
      const geo = navigator.geolocation;
      const leer = geo.getCurrentPosition.bind(geo);
      const vigilar = geo.watchPosition.bind(geo);
      geo.getCurrentPosition = function(...args) { window.__gps += 1; return leer(...args); };
      geo.watchPosition = function(...args) { window.__gps += 1; return vigilar(...args); };
    """)


def _entrar(page, base, correo=None):
    page.goto(base + "/movil/")
    page.locator("#correo-cuenta").fill(correo or _correo())
    page.locator("#contrasena").fill("clave-1")
    page.locator("#region").select_option("amer")
    with page.expect_response("**/auth/alta") as info:
        page.locator("#crear-cuenta").click()
    assert info.value.status == 201, info.value.text()
    expect(page.get_by_role("heading", name="Mis viajes")).to_be_visible()
    return page.locator("#cuenta").inner_text()


def _viaje(page):
    page.locator("#viaje-nombre").fill("Salida")
    page.get_by_role("button", name="Crear viaje").click()
    expect(page.get_by_role("button", name="Abrir viaje")).to_be_visible()
    page.get_by_role("button", name="Abrir viaje").click()
    expect(page.get_by_role("heading", name="Viaje", exact=True)).to_be_visible()


def _reserva(page, nombre, destino="", lat="", lon="", inicio="2026-12-02T09:00", fin="2026-12-02T12:00"):
    page.locator("#reserva-inicio").fill(inicio)
    page.locator("#reserva-fin").fill(fin)
    page.locator("#lugar-nombre").fill(nombre)
    page.locator("#lugar-destino").fill(destino)
    page.locator("#lugar-latitud").fill(str(lat) if lat != "" else "")
    page.locator("#lugar-longitud").fill(str(lon) if lon != "" else "")
    with page.expect_response("**/reservas") as info:
        page.get_by_role("button", name="Dar de alta").click()
    assert info.value.status in (200, 201), info.value.text()
    expect(page.locator("#lista-reservas").get_by_text(nombre)).to_be_visible()


def test_AC_COMP_03_01_el_login_se_pinta_en_menos_de_1_4_s(navegador, servidor):
    context = navegador.new_context()
    page = context.new_page()
    cliente = context.new_cdp_session(page)
    cliente.send("Network.enable")
    cliente.send("Network.emulateNetworkConditions", {
        "offline": False, "latency": 150,
        "downloadThroughput": int(1.6 * 1024 * 1024 / 8),
        "uploadThroughput": int(750 * 1024 / 8),
    })
    page.goto(servidor + "/movil/")
    fcp = page.evaluate("""() => {
      const pintura = performance.getEntriesByType('paint').find((e) => e.name === 'first-contentful-paint');
      return pintura ? pintura.startTime : null;
    }""")
    expect(page.get_by_role("heading", name="Ingreso")).to_be_visible()
    assert fcp is not None and fcp < 1400
    context.close()


def test_AC_COMP_03_02_la_segunda_apertura_sale_de_la_copia_local(navegador, servidor):
    context = navegador.new_context()
    page = context.new_page()
    page.goto(servidor + "/movil/")
    page.wait_for_function("() => navigator.serviceWorker.ready")
    page.reload()
    page.wait_for_function("() => navigator.serviceWorker.controller")
    respuesta = page.reload()
    assert respuesta is not None and respuesta.from_service_worker
    expect(page.get_by_role("heading", name="Ingreso")).to_be_visible()
    context.close()


def test_AC_COMP_03_03_el_login_no_pide_el_gps(navegador, servidor):
    context = navegador.new_context()
    _espia_gps(context)
    page = context.new_page()
    page.goto(servidor + "/movil/")
    expect(page.get_by_role("heading", name="Ingreso")).to_be_visible()
    assert page.evaluate("() => window.__gps") == 0
    context.close()


def test_AC_COMP_03_04_con_permiso_muestra_distancia_ruta_y_la_mas_cercana(navegador, servidor):
    context = navegador.new_context(geolocation=AQUI, permissions=["geolocation"])
    page = context.new_page()
    _entrar(page, servidor)
    _viaje(page)
    _reserva(page, "Obelisco", "Buenos Aires", CERCA["latitude"], CERCA["longitude"], "2026-12-02T10:00", "2026-12-02T11:00")
    _reserva(page, "Lejos", "La Plata", LEJOS["latitude"], LEJOS["longitude"], "2026-12-02T12:00", "2026-12-02T13:00")
    cercana = page.locator(".cercana")
    expect(cercana).to_contain_text("Obelisco")
    expect(cercana).to_contain_text("más cercana")
    expect(cercana.locator("a")).to_have_attribute("href", f"geo:{CERCA['latitude']},{CERCA['longitude']}")
    expect(page.locator(".reserva", has_text="Lejos").locator("a")).to_have_attribute(
        "href", f"geo:{LEJOS['latitude']},{LEJOS['longitude']}")
    context.close()


def test_AC_COMP_03_05_sin_permiso_muestra_el_itinerario_sin_distancia_ni_error(navegador, servidor):
    context = navegador.new_context()
    _espia_gps(context)
    page = context.new_page()
    _entrar(page, servidor)
    _viaje(page)
    _reserva(page, "Museo", "Recoleta", CERCA["latitude"], CERCA["longitude"])
    expect(page.get_by_text("Museo")).to_be_visible()
    expect(page.get_by_text("Recoleta")).to_be_visible()
    expect(page.locator("a[href^='geo:']")).to_have_count(0)
    expect(page.get_by_text("m", exact=True)).to_have_count(0)
    assert "error" not in page.locator("#viaje").inner_text().lower()
    context.close()


def test_AC_COMP_03_06_la_reserva_sin_coordenadas_no_muestra_distancia(navegador, servidor):
    context = navegador.new_context(geolocation=AQUI, permissions=["geolocation"])
    page = context.new_page()
    _entrar(page, servidor)
    _viaje(page)
    _reserva(page, "Sin mapa", "Centro")
    _reserva(page, "Con mapa", "Centro", CERCA["latitude"], CERCA["longitude"], "2026-12-02T15:00", "2026-12-02T16:00")
    sin_mapa = page.locator(".reserva", has_text="Sin mapa")
    expect(sin_mapa.locator("a")).to_have_count(0)
    expect(sin_mapa.get_by_text("m", exact=True)).to_have_count(0)
    expect(page.locator(".reserva", has_text="Con mapa").locator("a")).to_have_count(1)
    context.close()


def test_AC_COMP_03_07_las_coordenadas_del_dispositivo_no_salen_en_la_red(navegador, servidor):
    context = navegador.new_context(geolocation=AQUI, permissions=["geolocation"])
    page = context.new_page()
    _entrar(page, servidor)
    _viaje(page)
    vistos = []
    page.on("request", lambda r: vistos.append(r.url + " " + (r.post_data or "")))
    _reserva(page, "Plaza", "Centro", CERCA["latitude"], CERCA["longitude"])
    marca = str(AQUI["latitude"])
    assert all(marca not in pedido for pedido in vistos)
    context.close()


def test_AC_COMP_03_08_sin_red_la_distancia_se_recalcula(navegador, servidor):
    context = navegador.new_context(geolocation=AQUI, permissions=["geolocation"])
    page = context.new_page()
    _entrar(page, servidor)
    _viaje(page)
    _reserva(page, "Plaza", "Centro", CERCA["latitude"], CERCA["longitude"])
    antes = page.locator(".reserva", has_text="Plaza").inner_text()
    context.set_offline(True)
    context.set_geolocation(LEJOS)
    expect(page.locator(".reserva", has_text="Plaza")).not_to_have_text(antes, timeout=5000)
    context.close()


def test_AC_COMP_03_09_sin_permiso_muestra_error_401(navegador, servidor):
    context = navegador.new_context()
    page = context.new_page()
    correo_ana, correo_luis = _correo(), _correo()
    _entrar(page, servidor, correo_ana)
    _viaje(page)
    _reserva(page, "De Ana", "Centro")
    ident = page.locator(".reserva", has_text="De Ana").get_by_role("button", name="Dar de baja").get_attribute("title")
    page.locator("#salir").click()
    luis = _entrar(page, servidor, correo_luis)
    page.locator("#salir").click()
    page.locator("#correo-cuenta").fill(correo_ana)
    page.locator("#contrasena").fill("clave-1")
    with page.expect_response("**/auth/login") as info:
        page.locator("#entrar").click()
    assert info.value.ok
    expect(page.get_by_role("button", name="Abrir viaje")).to_be_visible()
    itinerario = page.locator("#arbol-viajes h2").inner_text()
    page.evaluate("""async ({luis, itinerario}) => {
      const sesion = JSON.parse(sessionStorage.getItem('trotamundos.sesion'));
      const r = await fetch('/itinerarios/' + itinerario + '/miembros', {
        method: 'POST',
        headers: {'Authorization': 'Bearer ' + sesion.token_acceso, 'Content-Type': 'application/json',
                  'X-Clave-Operacion': crypto.randomUUID()},
        body: JSON.stringify({cuenta: luis, rol: 'participante'}),
      });
      if (!r.ok) throw new Error(await r.text());
    }""", {"luis": luis, "itinerario": itinerario})
    page.locator("#salir").click()
    page.locator("#correo-cuenta").fill(correo_luis)
    page.locator("#contrasena").fill("clave-1")
    with page.expect_response("**/auth/login") as info:
        page.locator("#entrar").click()
    assert info.value.ok
    page.get_by_role("button", name="Abrir viaje").click()
    page.get_by_role("button", name="Dar de baja " + ident).click()
    expect(page.get_by_role("heading", name="Error 401")).to_be_visible()
    context.close()


def test_AC_COMP_03_10_el_manifiesto_permite_instalar(navegador, servidor):
    context = navegador.new_context()
    page = context.new_page()
    page.goto(servidor + "/movil/")
    manifiesto = page.evaluate("""async () => {
      const href = document.querySelector('link[rel="manifest"]').href;
      const r = await fetch(href);
      return r.json();
    }""")
    assert manifiesto["name"] and manifiesto["start_url"] == "/movil/"
    assert manifiesto["display"] == "standalone" and manifiesto["icons"]
    context.close()


def test_AC_COMP_03_11_el_menu_del_asistente_no_es_un_error(navegador, servidor):
    context = navegador.new_context()
    page = context.new_page()
    _entrar(page, servidor)
    _viaje(page)
    page.get_by_role("button", name="Asistente").click()
    page.locator("#asistente-mensaje").fill("hola")
    page.get_by_role("button", name="Enviar").click()
    expect(page.get_by_role("button", name="consultar_estado")).to_be_visible()
    expect(page.locator("#aviso")).to_be_hidden()
    context.close()
