# SPEC: SPEC-COMP-02
# ELEMENTO PASO 5: Cliente web (ITERACION_1, ITERACION_3, RONDA_2/ITERACION_1)
# DRIVERS: CON-01, REF-01, REF-03, REF-04, REF-05, REF-07, QA-SEG-02, QA-PER-01, QA-PER-02
"""Criterios del cliente web, en Chromium, contra la app principal."""
from __future__ import annotations

import json
import re
import socket
import threading
import time
import urllib.request
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect
from psycopg.types.json import Json

from trotamundos.app import create_app
from trotamundos.config import Configuracion
from trotamundos.persistencia.conexion import conectar

pytestmark = [pytest.mark.db, pytest.mark.navegador]


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
        raise RuntimeError("el cliente web no llegó a /salud")
    yield base
    server.should_exit = True
    hilo.join(5)
    sistema.state.red_regiones.cerrar()


@pytest.fixture
def pagina():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        dialogos: list[str] = []
        page.on("dialog", lambda d: dialogos.append(d.message) or d.dismiss())
        page.dialogos = dialogos
        yield page
        browser.close()


def _correo() -> str:
    return f"viajero-{uuid.uuid4().hex[:8]}@mail.com"


def _abrir(page, base):
    page.goto(base + "/web/")


def _enviar_identidad(page, correo, alta):
    page.locator("#correo-cuenta").fill(correo)
    page.locator("#contrasena").fill("clave-1")
    page.locator("#region").select_option("amer")
    ruta = "**/auth/alta" if alta else "**/auth/login"
    with page.expect_response(ruta) as info:
        page.locator("#crear-cuenta" if alta else "#entrar").click()
    assert info.value.status in (200, 201), info.value.text()
    expect(page.get_by_role("heading", name="Mis viajes")).to_be_visible()
    return page.locator("#cuenta").inner_text()


def _crear_viaje(page, nombre="Roma"):
    page.locator("#viaje-nombre").fill(nombre)
    page.get_by_role("button", name="Crear viaje").click()
    expect(page.locator("#arbol-viajes h3")).to_be_visible()


def _gestionar(page):
    page.get_by_role("button", name="Gestionar").click()
    expect(page.get_by_role("heading", name="Viaje", exact=True)).to_be_visible()


def _alta_reserva(page, lugar):
    page.locator("#reserva-tipo").select_option("actividad")
    page.locator("#reserva-inicio").fill("2026-12-02T09:00")
    page.locator("#reserva-fin").fill("2026-12-02T12:00")
    page.locator("#reserva-lugar").fill(lugar)
    with page.expect_response("**/reservas") as info:
        page.get_by_role("button", name="Dar de alta").click()
    assert info.value.status in (200, 201), info.value.text()
    expect(page.locator("#reservas-viaje").get_by_text(lugar, exact=False)).to_be_visible()


def _itinerario(page) -> str:
    return page.locator("[data-itinerario]").first.get_attribute("data-itinerario")


def test_AC_COMP_02_01_mis_viajes_muestra_las_reservas_agrupadas(pagina, servidor):
    _abrir(pagina, servidor)
    _enviar_identidad(pagina, _correo(), alta=True)
    _crear_viaje(pagina)
    _gestionar(pagina)
    _alta_reserva(pagina, "Coliseo")
    pagina.get_by_role("button", name="Mis viajes").click()
    grupo = pagina.locator("#arbol-viajes .viaje", has_text="Coliseo")
    expect(grupo.locator("h3")).to_be_visible()
    expect(grupo).to_contain_text("Coliseo")


def test_AC_COMP_02_02_quitar_un_miembro_sin_permiso_muestra_error_401(pagina, servidor):
    correo_luis, correo_ana = _correo(), _correo()
    _abrir(pagina, servidor)
    luis = _enviar_identidad(pagina, correo_luis, alta=True)
    pagina.locator("#salir").click()
    _enviar_identidad(pagina, correo_ana, alta=True)
    ana = pagina.locator("#cuenta").inner_text()
    _crear_viaje(pagina)
    pagina.get_by_role("button", name="Miembros").click()
    pagina.locator("#miembro-cuenta").fill(luis)
    pagina.get_by_role("button", name="Agregar miembro").click()
    expect(pagina.get_by_role("button", name=f"Quitar {luis}")).to_be_visible()
    pagina.locator("#salir").click()
    _abrir(pagina, servidor)
    _enviar_identidad(pagina, correo_luis, alta=False)
    pagina.get_by_role("button", name="Miembros").click()
    pagina.get_by_role("button", name=f"Quitar {ana}").click()
    expect(pagina.get_by_role("heading", name="Error 401")).to_be_visible()


def test_AC_COMP_02_03_el_reintento_reutiliza_la_clave_y_la_reserva_queda_una_vez(pagina, servidor):
    claves = []

    def cortar(route):
        if route.request.method == "POST" and "/reservas" in urlparse(route.request.url).path:
            claves.append(route.request.headers["x-clave-operacion"])
            if len(claves) == 1:
                route.abort("failed")
                return
        route.continue_()

    _abrir(pagina, servidor)
    _enviar_identidad(pagina, _correo(), alta=True)
    _crear_viaje(pagina)
    _gestionar(pagina)
    pagina.locator("#reserva-tipo").select_option("actividad")
    pagina.locator("#reserva-inicio").fill("2026-12-02T09:00")
    pagina.locator("#reserva-fin").fill("2026-12-02T12:00")
    pagina.locator("#reserva-lugar").fill("Unica")
    pagina.route("**/reservas", cortar)
    pagina.get_by_role("button", name="Dar de alta").click()
    expect(pagina.locator("#aviso")).to_be_visible()
    with pagina.expect_response("**/reservas") as info:
        pagina.get_by_role("button", name="Reintentar").click()
    assert info.value.ok, info.value.status
    pagina.get_by_role("button", name="Mis viajes").click()
    expect(pagina.locator("#arbol-viajes .viaje", has_text="Unica")).to_have_count(1)
    assert claves[0] == claves[1]


def test_AC_COMP_02_04_si_la_vista_falla_se_conserva_lo_mostrado(pagina, servidor):
    _abrir(pagina, servidor)
    _enviar_identidad(pagina, _correo(), alta=True)
    _crear_viaje(pagina)
    _gestionar(pagina)
    _alta_reserva(pagina, "Roma estable")
    pagina.get_by_role("button", name="Mis viajes").click()
    expect(pagina.locator("#arbol-viajes").get_by_text("Roma estable")).to_be_visible()

    def caido(route):
        if urlparse(route.request.url).path == "/itinerarios":
            route.fulfill(status=503, content_type="application/json", body='{"detail":"no"}')
        else:
            route.continue_()

    pagina.route("**/itinerarios", caido)
    pagina.get_by_role("button", name="Actualizar").click()
    expect(pagina.locator("#arbol-viajes").get_by_text("Roma estable")).to_be_visible()
    expect(pagina.locator("#aviso")).to_contain_text("Se conserva lo que ya ves")
    expect(pagina.get_by_role("button", name="Reintentar")).to_be_visible()


def test_AC_COMP_02_05_reintentar_un_caso_sin_entregar_lo_vuelve_a_en_tramite(pagina, servidor, cfg):
    _abrir(pagina, servidor)
    cuenta = _enviar_identidad(pagina, _correo(), alta=True)
    _crear_viaje(pagina)
    itinerario = _itinerario(pagina)
    ahora = datetime.now(UTC)
    for dsn in (cfg.bases.viajes_primaria, cfg.bases.viajes_pasiva):
        with conectar(dsn, autocommit=True) as conn:
            conn.execute(
                "INSERT INTO caso (id, cuenta_id, itinerario_id, reserva_id, agencia, descripcion,"
                " pedido, estado, creado_en, actualizado_en) VALUES"
                " (%s, %s, %s, %s, %s, %s, %s, 'sin_entregar', %s, %s)",
                ("caso-1", cuenta, itinerario, "r1", "agencia-a", "demo", Json({}), ahora, ahora))
    pagina.get_by_role("button", name="Novedades").click()
    expect(pagina.get_by_text("sin entregar")).to_be_visible()
    pagina.get_by_role("button", name="Reintentar caso").click()
    expect(pagina.get_by_text("en trámite")).to_be_visible()


def test_AC_COMP_02_06_un_script_del_backend_se_muestra_como_texto(pagina, servidor):
    _abrir(pagina, servidor)
    _enviar_identidad(pagina, _correo(), alta=True)
    _crear_viaje(pagina, nombre="Viaje")
    _gestionar(pagina)
    _alta_reserva(pagina, "<script>alert(1)</script>")
    pagina.get_by_role("button", name="Mis viajes").click()
    expect(pagina.locator("#arbol-viajes").get_by_text("<script>alert(1)</script>")).to_be_visible()
    assert pagina.locator("#arbol-viajes script").count() == 0
    assert pagina.dialogos == []


def test_AC_COMP_02_07_sin_agencia_reportar_pide_el_consentimiento(pagina, servidor):
    posts = []
    pagina.on("request", lambda r: posts.append(r.url) if r.method == "POST" and urlparse(r.url).path == "/casos" else None)
    _abrir(pagina, servidor)
    _enviar_identidad(pagina, _correo(), alta=True)
    _crear_viaje(pagina)
    _gestionar(pagina)
    _alta_reserva(pagina, "Museo")
    pagina.get_by_role("button", name="Mis viajes").click()
    pagina.locator("#arbol-viajes").get_by_role("button", name=re.compile(r"Reportar problema")).click()
    expect(pagina.get_by_text("Doy mi consentimiento")).to_be_visible()
    expect(pagina.locator("#falta-agencia")).to_be_visible()
    assert posts == []


def test_AC_COMP_02_08_aprobar_un_remitente_lo_saca_de_revision_y_entra_al_itinerario(pagina, servidor, cfg):
    _abrir(pagina, servidor)
    cuenta = _enviar_identidad(pagina, _correo(), alta=True)
    reserva = {
        "id_mensaje": "msg-1", "titular_id": cuenta, "remitente": "hotel@ejemplo.com",
        "tipo": "hotel", "inicio": "2026-12-01T00:00:00+00:00", "fin": "2026-12-05T00:00:00+00:00",
        "lugar": "Lisboa", "codigo": "ABC",
    }
    ahora = datetime.now(UTC)
    for dsn in (cfg.bases.viajes_primaria, cfg.bases.viajes_pasiva):
        with conectar(dsn, autocommit=True) as conn:
            conn.execute(
                "INSERT INTO mensaje_revision (titular_id, id_mensaje, remitente, reserva, creado_en)"
                " VALUES (%s, %s, %s, %s, %s)",
                (cuenta, "msg-1", "hotel@ejemplo.com", Json(reserva), ahora))
    pagina.get_by_role("button", name="Mensajes en revisión").click()
    lista = pagina.locator("#lista-revision")
    expect(lista.locator("p", has_text="hotel@ejemplo.com")).to_be_visible()
    pagina.get_by_role("button", name="Aprobar hotel@ejemplo.com").click()
    expect(lista.locator("p", has_text="hotel@ejemplo.com")).to_have_count(0)
    pagina.get_by_role("button", name="Mis viajes").click()
    for _ in range(20):
        if pagina.get_by_text("Lisboa").count():
            break
        pagina.get_by_role("button", name="Actualizar").click()
        pagina.wait_for_timeout(500)
    expect(pagina.get_by_text("Lisboa")).to_be_visible()


def test_AC_COMP_02_09_sin_confirmar_el_asistente_no_ejecuta_la_accion(pagina, servidor):
    confirmaciones = []
    pagina.on("request", lambda r: confirmaciones.append(r.post_data or "")
              if r.method == "POST" and r.url.endswith("/asistente/accion") else None)
    _abrir(pagina, servidor)
    _enviar_identidad(pagina, _correo(), alta=True)
    _crear_viaje(pagina)
    _gestionar(pagina)
    _alta_reserva(pagina, "Coliseo")
    pagina.get_by_role("button", name="Asistente").click()
    pagina.locator("#asistente-mensaje").fill("reprogramar Coliseo 2026-12-20T10:00:00")
    pagina.get_by_role("button", name="Enviar").click()
    expect(pagina.get_by_text("No se ejecuta hasta que confirmes")).to_be_visible()
    pagina.get_by_role("button", name="Mis viajes").click()
    expect(pagina.locator("#arbol-viajes").get_by_text("Coliseo")).to_be_visible()
    assert not any("confirmar" in cuerpo for cuerpo in confirmaciones)


def test_AC_COMP_02_10_si_el_asistente_degrada_se_muestra_el_menu(pagina, servidor):
    _abrir(pagina, servidor)
    _enviar_identidad(pagina, _correo(), alta=True)
    _crear_viaje(pagina)
    pagina.get_by_role("button", name="Asistente").click()
    pagina.locator("#asistente-mensaje").fill("hola")
    pagina.get_by_role("button", name="Enviar").click()
    expect(pagina.get_by_role("button", name="consultar_estado")).to_be_visible()
    expect(pagina.locator("#aviso")).to_be_hidden()


def test_AC_COMP_02_11_una_grilla_parcial_muestra_quien_respondio(pagina, servidor):
    def parcial(route):
        if urlparse(route.request.url).path == "/cotizaciones":
            route.fulfill(status=200, content_type="application/json", body=json.dumps({
                "origenes": [
                    {"proveedor": "hoteles", "estado": "ok",
                     "precios": [{"descripcion": "noche", "monto": "10", "moneda": "USD"}]},
                    {"proveedor": "aerolineas", "estado": "no_respondio", "precios": []},
                ],
                "completa": False, "copia": False, "en_curso": False,
            }))
        else:
            route.continue_()

    _abrir(pagina, servidor)
    _enviar_identidad(pagina, _correo(), alta=True)
    pagina.route("**/cotizaciones**", parcial)
    pagina.get_by_role("button", name="Cotización").click()
    pagina.locator("#cotizacion-fecha").fill("2026-12-01")
    pagina.locator("#cotizacion-hospedaje").fill("hotel")
    pagina.locator("#cotizacion-compania").fill("aire")
    pagina.get_by_role("button", name="Cotizar").click()
    expect(pagina.get_by_text("hoteles respondió")).to_be_visible()
    expect(pagina.get_by_text("aerolineas no respondió")).to_be_visible()
    expect(pagina.locator("#aviso")).to_be_hidden()


def test_AC_COMP_02_12_los_pedidos_van_solo_a_la_app(pagina, servidor):
    vistos = []
    pagina.on("request", lambda r: vistos.append(r.url))
    _abrir(pagina, servidor)
    _enviar_identidad(pagina, _correo(), alta=True)
    _crear_viaje(pagina)
    pagina.get_by_role("button", name="Cotización").click()
    ajenos = [u for u in vistos if urlparse(u).scheme in ("http", "https") and not u.startswith(servidor)]
    assert ajenos == []


def test_AC_COMP_02_13_una_novedad_aparece_sin_recargar(pagina, servidor):
    entregas = {"n": 0}

    def novedades(route):
        path = urlparse(route.request.url).path
        if route.request.method == "GET" and path.endswith("/novedades"):
            entregas["n"] += 1
            cuerpo = "[]" if entregas["n"] == 1 else json.dumps([{
                "id": "n1", "reserva_id": "r1", "proveedor": "aviso-demo",
                "cambios": {"lugar": "Osaka"}, "recibida_en": "2026-11-23T12:00:00+00:00",
            }])
            route.fulfill(status=200, content_type="application/json", body=cuerpo)
        else:
            route.continue_()

    _abrir(pagina, servidor)
    _enviar_identidad(pagina, _correo(), alta=True)
    _crear_viaje(pagina)
    pagina.clock.install()
    pagina.route("**/*", novedades)
    pagina.get_by_role("button", name="Novedades").click()
    expect(pagina.get_by_role("heading", name="Novedades")).to_be_visible()
    pagina.clock.fast_forward(60000)
    expect(pagina.get_by_text("aviso-demo")).to_be_visible()
