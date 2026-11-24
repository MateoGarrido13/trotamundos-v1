# SPEC: SPEC-COMP-05
# ELEMENTO PASO 5: Módulo de registro y autenticación de la región (ITERACION_4)
# ADRs: ADR-IT4-001, ADR-IT4-003, ADR-IT4-004, ADR-IT4-006
# DRIVERS: QA-ESC-01
"""El servicio de cada región contra las seis bases de test."""
import time

import pytest

from tests.comp05_util import armar_regiones, token_de
from trotamundos.dominio.identidad import (
    CorreoYaRegistrado,
    CredencialInvalida,
    TokenInvalido,
    TokenRecuperacionInvalido,
)
from trotamundos.identidad.region.servicio import huella_de
from trotamundos.identidad.tokens import ValidadorTokens, clave_publica_hex

pytestmark = pytest.mark.db


@pytest.fixture
def r(cuentas_limpias):
    sistema = armar_regiones(cuentas_limpias)
    yield sistema
    sistema.red.cerrar()


def validador(cfg):
    return ValidadorTokens({reg: clave_publica_hex(k) for reg, k in cfg.claves_firma.items()})


def test_AC_COMP_05_01_cada_cuenta_vive_en_una_region_con_su_prefijo(r):
    cuentas = {reg: r.servicios[reg].alta(f"{reg}@mail.com", "clave-1").cuenta_id for reg in r.servicios}
    for reg, cuenta_id in cuentas.items():
        assert cuenta_id.startswith(f"{reg}-")
    for reg in r.servicios:
        for otra in r.servicios:
            assert r.servicios[otra].consultar_unicidad(huella_de(f"{reg}@mail.com")) is (otra == reg)


def test_AC_COMP_05_02_el_alta_trae_la_sesion(r):
    sesion = r.servicios["amer"].alta("ana@mail.com", "clave-1")
    assert validador(r.cfg).validar(sesion.token_acceso, r.reloj()) == sesion.cuenta_id
    assert r.servicios["amer"].renovar(sesion.token_renovacion)
    assert sesion.token_renovacion.startswith("amer.")


def test_AC_COMP_05_03_region_lenta_deja_unicidad_pendiente(r):
    def lenta(huella):
        time.sleep(0.8)
        return False
    r.servicios["emea"].consultar_unicidad = lenta
    inicio = time.monotonic()
    sesion = r.servicios["amer"].alta("ana@mail.com", "clave-1")
    assert time.monotonic() - inicio < 0.8  # no espera más que la cota
    assert sesion.cuenta_id.startswith("amer-")
    base = r.servicios["amer"]._base
    pendiente = base.leer(lambda c: c.execute(
        "SELECT unicidad_pendiente FROM cuenta WHERE id = %s", (sesion.cuenta_id,)).fetchone()[0])
    assert pendiente is True


def test_AC_COMP_05_04_correo_de_otra_region_se_rechaza(r):
    r.servicios["amer"].alta("Ana@Mail.com", "clave-1")
    with pytest.raises(CorreoYaRegistrado):
        r.servicios["emea"].alta("ana@mail.com", "clave-2")
    with pytest.raises(CorreoYaRegistrado):  # y en la misma región
        r.servicios["amer"].alta("ana@mail.com", "clave-2")


def test_AC_COMP_05_10_token_de_recuperacion_de_un_solo_uso(r):
    s = r.servicios["amer"]
    s.alta("ana@mail.com", "clave-1")
    s.solicitar_recuperacion("ana@mail.com")
    token = token_de(r.publicados[0])
    assert r.publicados[0]["destinatario"] == "ana@mail.com"
    s.completar_recuperacion(token, "clave-nueva")
    with pytest.raises(TokenRecuperacionInvalido):
        s.completar_recuperacion(token, "otra")
    with pytest.raises(TokenRecuperacionInvalido):
        s.completar_recuperacion("amer.inexistente", "otra")


def test_AC_COMP_05_10_token_vencido_no_sirve(r):
    s = r.servicios["amer"]
    s.alta("ana@mail.com", "clave-1")
    s.solicitar_recuperacion("ana@mail.com")
    r.reloj.avanzar(minutes=31)
    with pytest.raises(TokenRecuperacionInvalido):
        s.completar_recuperacion(token_de(r.publicados[0]), "clave-nueva")


def test_AC_COMP_05_11_recuperar_revoca_los_tokens_de_renovacion(r):
    s = r.servicios["amer"]
    sesion = s.alta("ana@mail.com", "clave-1")
    s.solicitar_recuperacion("ana@mail.com")
    s.completar_recuperacion(token_de(r.publicados[0]), "clave-nueva")
    with pytest.raises(TokenInvalido):
        s.renovar(sesion.token_renovacion)
    with pytest.raises(CredencialInvalida):
        s.login("ana@mail.com", "clave-1")
    assert s.login("ana@mail.com", "clave-nueva").cuenta_id == sesion.cuenta_id


def test_AC_COMP_05_11_cerrar_sesion_revoca_la_renovacion(r):
    s = r.servicios["amer"]
    sesion = s.alta("ana@mail.com", "clave-1")
    s.cerrar_sesion(sesion.token_renovacion)
    with pytest.raises(TokenInvalido):
        s.renovar(sesion.token_renovacion)


def test_AC_COMP_05_12_un_solo_aviso_por_ventana(r):
    s = r.servicios["amer"]
    s.alta("ana@mail.com", "clave-1")
    avisos = lambda: [p for p in r.publicados if p["propuesta"]["asunto"].startswith("Pedidos")]  # noqa: E731
    for _ in range(3):  # dentro del cupo
        s.solicitar_recuperacion("ana@mail.com")
    assert avisos() == []
    for _ in range(4):  # lo supera: un solo aviso
        s.solicitar_recuperacion("ana@mail.com")
    assert len(avisos()) == 1
    # El pedido vigente es uno solo: solo salió un correo con código.
    assert len([p for p in r.publicados if "código" in p["propuesta"]["cuerpo"]]) == 1
    r.reloj.avanzar(minutes=61)  # pasa la ventana y se supera otra vez
    for _ in range(4):
        s.solicitar_recuperacion("ana@mail.com")
    assert len(avisos()) == 2


def test_la_contrasena_no_se_guarda_en_claro(r):
    s = r.servicios["amer"]
    s.alta("ana@mail.com", "clave-secreta")
    guardado = s._base.leer(lambda c: c.execute("SELECT clave_hash FROM cuenta").fetchone()[0])
    assert "clave-secreta" not in guardado and guardado.startswith("scrypt$")


def test_login_con_credenciales_incorrectas(r):
    s = r.servicios["amer"]
    s.alta("ana@mail.com", "clave-1")
    with pytest.raises(CredencialInvalida):
        s.login("ana@mail.com", "mala")
    with pytest.raises(CredencialInvalida):
        s.login("nadie@mail.com", "clave-1")


def test_token_de_renovacion_vence(r):
    s = r.servicios["amer"]
    sesion = s.alta("ana@mail.com", "clave-1")
    r.reloj.avanzar(days=8)
    with pytest.raises(TokenInvalido):
        s.renovar(sesion.token_renovacion)


def test_una_publicacion_fallida_no_rompe_la_recuperacion(cuentas_limpias):
    from trotamundos.identidad.region.regiones import ensamblar_regiones

    def falla(_):
        raise RuntimeError("cola llena")
    servicios, red = ensamblar_regiones(cuentas_limpias, falla)
    try:
        servicios["amer"].alta("ana@mail.com", "clave-1")
        servicios["amer"].solicitar_recuperacion("ana@mail.com")  # no lanza
    finally:
        red.cerrar()
