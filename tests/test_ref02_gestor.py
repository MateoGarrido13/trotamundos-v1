# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Gestor de autorización del correo (ITERACION_3)
# ADRs: ADR-IT3-006
# DRIVERS: QA-SEG-03*
"""T-REF-02-02: GestorAutorizacion con reloj inyectado."""
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from trotamundos.config import ConfiguracionCorreo
from trotamundos.entrada.gestor_autorizacion import (
    CifradorTokens,
    GestorAutorizacion,
    RepositorioTokensEnMemoria,
)

T0 = datetime(2026, 11, 23, 10, 0, tzinfo=UTC)


class Reloj:
    def __init__(self) -> None:
        self.ahora = T0

    def __call__(self) -> datetime:
        return self.ahora


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def gestor(reloj):
    return GestorAutorizacion(
        RepositorioTokensEnMemoria(), CifradorTokens(Fernet.generate_key()),
        ConfiguracionCorreo(vigencia_token_minutos=60), reloj=reloj,
    )


def test_AC_REF_02_01_gestor_sin_autorizacion_o_revocado_no_hay_token(gestor):
    assert gestor.token_vigente("t1") is None
    gestor.autorizar("t1", "tok")
    assert gestor.token_vigente("t1") == "tok"
    gestor.revocar("t1")
    assert gestor.token_vigente("t1") is None
    assert gestor.titulares_autorizados() == []


def test_AC_REF_02_07_gestor_token_vencido_no_es_vigente_ni_se_renueva(gestor, reloj):
    gestor.autorizar("t1", "tok")
    reloj.ahora = T0 + timedelta(minutes=59)
    assert gestor.token_vigente("t1") == "tok"
    reloj.ahora = T0 + timedelta(minutes=61)
    assert gestor.token_vigente("t1") is None
    reloj.ahora = T0 + timedelta(minutes=62)
    assert gestor.token_vigente("t1") is None  # no se renovó
    gestor.autorizar("t1", "tok2")  # el titular vuelve a autorizar
    assert gestor.token_vigente("t1") == "tok2"


def test_titulares_autorizados(gestor):
    gestor.autorizar("a", "x")
    gestor.autorizar("b", "y")
    assert sorted(gestor.titulares_autorizados()) == ["a", "b"]
