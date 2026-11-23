# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Adaptador de correo (ITERACION_3)
# ADRs: ADR-IT3-002, ADR-IT3-003, ADR-IT3-006
# DRIVERS: QA-SEG-03*, CON-02
"""T-REF-02-04: AdaptadorCorreo.sondear. Fixtures compartidas con el programador."""
import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from trotamundos.broker import Broker, Mensaje, NombreCola
from trotamundos.config import ConfiguracionBroker, ConfiguracionCorreo
from trotamundos.entrada.adaptador_correo import AdaptadorCorreo
from trotamundos.entrada.api_correo import CorreoCrudo, ErrorApiCorreo, MockApiCorreo
from trotamundos.entrada.gestor_autorizacion import (
    CifradorTokens,
    GestorAutorizacion,
    RepositorioTokensEnMemoria,
)

T0 = datetime(2026, 11, 23, 10, 0, tzinfo=UTC)


class Entorno:
    def __init__(self, cfg_broker: ConfiguracionBroker) -> None:
        self.cfg = ConfiguracionCorreo()
        self.api = MockApiCorreo()
        self.broker = Broker(cfg_broker)
        self.gestor = GestorAutorizacion(
            RepositorioTokensEnMemoria(), CifradorTokens(Fernet.generate_key()), self.cfg,
            reloj=lambda: T0,
        )
        self.adaptador = AdaptadorCorreo(self.api, self.gestor, self.broker, self.cfg)

    def autorizar(self, titular: str = "t1", token: str = "tok") -> None:
        self.api.emitir_token(titular, token)
        self.gestor.autorizar(titular, token)

    def correo(self, cuerpo="c", message_id="<m1@x>", dias_atras=1, titular="t1") -> None:
        self.api.agregar_correo(
            titular, CorreoCrudo(cuerpo, "agencia@x.com", T0 - timedelta(days=dias_atras), message_id)
        )


@pytest.fixture
def entorno(cfg_broker):
    return Entorno(cfg_broker)


async def _vaciar(broker: Broker) -> list[Mensaje]:
    vistos: list[Mensaje] = []

    async def h(m):
        vistos.append(m)

    while await broker.procesar_uno(NombreCola.CORREO, h) != "vacia":
        pass
    return vistos


async def test_AC_REF_02_01_sin_autorizacion_o_revocado_el_adaptador_no_lee(entorno):
    entorno.correo()
    entorno.api.emitir_token("t1", "tok")
    r = await entorno.adaptador.sondear("t1", T0)  # nunca autorizó
    assert not r.leyo and entorno.api.lecturas == 0
    entorno.gestor.autorizar("t1", "tok")
    assert (await entorno.adaptador.sondear("t1", T0)).leyo
    assert entorno.api.lecturas == 1
    entorno.gestor.revocar("t1")  # revocó
    r = await entorno.adaptador.sondear("t1", T0)
    assert not r.leyo and entorno.api.lecturas == 1
    assert entorno.broker.tamano_actual(NombreCola.CORREO) == 1  # nada nuevo


async def test_AC_REF_02_07_token_vencido_no_lee_y_exige_reautorizar(entorno):
    entorno.autorizar()
    entorno.correo()
    despues = T0 + timedelta(minutes=61)
    r = await entorno.adaptador.sondear("t1", despues)
    assert not r.leyo and entorno.api.lecturas == 0
    entorno.gestor.autorizar("t1", "tok")  # vigente desde el reloj T0
    assert (await entorno.adaptador.sondear("t1", T0)).leyo


async def test_AC_REF_02_02_sondeo_publica_con_message_id_o_hash(entorno):
    entorno.autorizar()
    entorno.correo(cuerpo="con id", message_id="<abc@x>")
    entorno.correo(cuerpo="sin id", message_id=None)
    r = await entorno.adaptador.sondear("t1", T0)
    assert r.publicados == 2
    ids = [m.id for m in await _vaciar(entorno.broker)]
    assert ids == ["<abc@x>", hashlib.sha256(b"sin id").hexdigest()]


async def test_AC_REF_02_03_cola_llena_no_publica_no_pierde_y_reintenta_en_el_siguiente_sondeo(entorno):
    entorno.autorizar()
    for i in range(5):
        entorno.broker.publicar(NombreCola.CORREO, Mensaje(f"previo{i}", {}))
    entorno.correo(message_id="<nuevo@x>")
    r = await entorno.adaptador.sondear("t1", T0)
    assert r.cola_llena and r.publicados == 0
    assert entorno.broker.tamano_actual(NombreCola.CORREO) == 5
    await entorno.broker.procesar_uno(NombreCola.CORREO, _noop)  # se libera un lugar
    r = await entorno.adaptador.sondear("t1", T0)
    assert r.publicados == 1 and not r.cola_llena
    assert "<nuevo@x>" in [m.id for m in await _vaciar(entorno.broker)]


async def _noop(_m):
    return None


async def test_api_caida_falla_solo_ese_sondeo(entorno):
    entorno.autorizar()
    entorno.correo()
    entorno.api.caida = True
    with pytest.raises(ErrorApiCorreo):
        await entorno.adaptador.sondear("t1", T0)
    assert entorno.broker.tamano_actual(NombreCola.CORREO) == 0
    entorno.api.caida = False
    assert (await entorno.adaptador.sondear("t1", T0)).publicados == 1


async def test_el_sondeo_respeta_la_ventana(entorno):
    entorno.autorizar()
    entorno.correo(message_id="<viejo@x>", dias_atras=8)
    entorno.correo(message_id="<nuevo@x>", dias_atras=6)
    await entorno.adaptador.sondear("t1", T0)
    assert [m.id for m in await _vaciar(entorno.broker)] == ["<nuevo@x>"]
