# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Adaptador de correo, API de correo externa (ITERACION_3)
# ADRs: ADR-IT3-003
# DRIVERS: CON-02
"""T-REF-02-03: ApiCorreo y MockApiCorreo."""
from datetime import UTC, datetime

import pytest

from trotamundos.entrada.api_correo import CorreoCrudo, ErrorApiCorreo, MockApiCorreo, TokenInvalido

T0 = datetime(2026, 11, 23, tzinfo=UTC)


async def test_mock_rechaza_tokens_invalidos():
    api = MockApiCorreo()
    with pytest.raises(TokenInvalido):
        await api.leer_mensajes("malo", T0)


async def test_mock_devuelve_solo_la_ventana_del_titular():
    api = MockApiCorreo()
    api.emitir_token("t1", "tok")
    api.agregar_correo("t1", CorreoCrudo("a", "x@y", datetime(2026, 11, 20, tzinfo=UTC)))
    api.agregar_correo("t1", CorreoCrudo("viejo", "x@y", datetime(2026, 1, 1, tzinfo=UTC)))
    api.agregar_correo("t2", CorreoCrudo("otro", "x@y", datetime(2026, 11, 20, tzinfo=UTC)))
    assert [c.cuerpo for c in await api.leer_mensajes("tok", datetime(2026, 11, 16, tzinfo=UTC))] == ["a"]


async def test_mock_falla_y_demora_a_demanda():
    esperas = []

    async def dormir(s):
        esperas.append(s)

    api = MockApiCorreo(dormir=dormir)
    api.emitir_token("t1", "tok")
    api.demora_segundos = 3
    await api.leer_mensajes("tok", T0)
    assert esperas == [3]
    api.caida = True
    with pytest.raises(ErrorApiCorreo):
        await api.leer_mensajes("tok", T0)
