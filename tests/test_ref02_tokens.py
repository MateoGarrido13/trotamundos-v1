# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Gestor de autorización del correo (ITERACION_3)
# ADRs: ADR-IT3-006
# DRIVERS: QA-SEG-03*
"""T-REF-02-01: cifrado Fernet y repositorio en memoria."""
from datetime import UTC, datetime

import pytest
from cryptography.fernet import Fernet

from trotamundos.entrada.gestor_autorizacion import (
    CifradorTokens,
    RepositorioTokensEnMemoria,
    TokenGuardado,
)


def test_el_token_se_guarda_cifrado_sin_el_texto_en_claro():
    cif = CifradorTokens(Fernet.generate_key())
    repo = RepositorioTokensEnMemoria()
    repo.guardar(TokenGuardado("t1", cif.cifrar("token-secreto-123"), datetime(2026, 1, 1, tzinfo=UTC)))
    guardado = repo.obtener("t1")
    assert b"token-secreto-123" not in guardado.token_cifrado
    assert cif.descifrar(guardado.token_cifrado) == "token-secreto-123"


def test_sin_clave_no_hay_cifrador():
    with pytest.raises(ValueError):
        CifradorTokens("")


def test_repositorio_borra_y_lista():
    repo = RepositorioTokensEnMemoria()
    repo.guardar(TokenGuardado("t1", b"x", datetime(2026, 1, 1, tzinfo=UTC)))
    assert repo.titulares() == ["t1"]
    repo.borrar("t1")
    repo.borrar("t1")
    assert repo.obtener("t1") is None
