# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Parseo aislado (ITERACION_3)
# ADRs: ADR-IT3-007
# DRIVERS: QA-SEG-03*, REF-02
"""T-REF-02-06: Parseo aislado como proceso real del sistema operativo."""
import json
import os
from pathlib import Path

import pytest

from trotamundos.entrada.parseo_aislado.cliente import ClienteParseo

VALIDO = {
    "tipo": "vuelo", "inicio": "2026-12-01T10:00:00", "fin": "2026-12-01T14:00:00",
    "lugar": "Madrid", "codigo": "ABC123",
}


def _msg(cuerpo, ident="<m1@x>"):
    return dict(id_mensaje=ident, titular_id="t1", remitente="a@x.com", cuerpo=cuerpo)


@pytest.fixture
async def parseo():
    cliente = ClienteParseo()
    try:
        yield cliente
    finally:
        await cliente.cerrar()


async def test_parseo_valido_normaliza_y_conserva_identificador(parseo):
    r = await parseo.parsear(**_msg(json.dumps(VALIDO)))
    assert r.id_mensaje == "<m1@x>" and r.titular_id == "t1" and r.remitente == "a@x.com"
    assert r.codigo == "ABC123" and r.lugar == "Madrid" and r.tipo == "vuelo"


async def test_AC_REF_02_04_parseo_descarta_invalidos_y_maliciosos(parseo):
    invalidos = [
        "no es json",
        "[1, 2]",
        json.dumps({**VALIDO, "codigo": None}),
        json.dumps({k: v for k, v in VALIDO.items() if k != "lugar"}),
        json.dumps({**VALIDO, "inicio": "ayer"}),
        json.dumps({**VALIDO, "fin": "2026-11-01T00:00:00"}),  # fin antes de inicio
        json.dumps({**VALIDO, "extra": "campo no previsto"}),
        json.dumps({**VALIDO, "lugar": "Madrid\x00; DROP TABLE reserva"}),  # carácter de control
        json.dumps({**VALIDO, "codigo": "x" * 10_000}),  # campo desmedido
        json.dumps({**VALIDO, "lugar": "A" * 70_000}),  # supera 64 KB
        "[" * 100_000,  # anidamiento profundo
    ]
    for cuerpo in invalidos:
        assert await parseo.parsear(**_msg(cuerpo)) is None, cuerpo[:40]
    # sigue vivo y funcional tras recibir basura
    assert await parseo.parsear(**_msg(json.dumps(VALIDO))) is not None


@pytest.mark.skipif(not Path("/proc/self/environ").exists(), reason="requiere /proc (Linux)")
async def test_AC_REF_02_08_proceso_de_parseo_sin_credenciales_ni_token(parseo, monkeypatch):
    monkeypatch.setenv("TROTA_DSN_VIAJES_PRIMARIA", "postgresql://u:secreto@h/db")
    monkeypatch.setenv("TROTA_DSN_VIAJES_PASIVA", "postgresql://u:secreto@h/db2")
    monkeypatch.setenv("TROTA_CLAVE_TOKENS", "clave-de-cifrado")
    await parseo.iniciar()
    pid = parseo.pid
    assert pid and pid != os.getpid()  # proceso real, distinto del test
    assert Path(f"/proc/{pid}/exe").exists()
    crudo = Path(f"/proc/{pid}/environ").read_bytes()
    variables = [v.decode() for v in crudo.split(b"\0") if v]
    nombres = {v.split("=", 1)[0] for v in variables}
    assert not any(n.startswith("TROTA_DSN_") for n in nombres), nombres
    assert "TROTA_CLAVE_TOKENS" not in nombres
    assert not any("secreto" in v or "clave-de-cifrado" in v for v in variables)
    assert not any("TOKEN" in n.upper() or "PASSWORD" in n.upper() for n in nombres), nombres


async def test_el_cliente_se_recupera_si_el_proceso_muere(parseo):
    await parseo.iniciar()
    parseo._proc.kill()
    await parseo._proc.wait()
    assert await parseo.parsear(**_msg(json.dumps(VALIDO))) is not None  # reinicia solo

