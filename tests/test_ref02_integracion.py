# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Gestor de autorización del correo (ITERACION_3)
# ADRs: ADR-IT3-006, ADR-IT2-004
# DRIVERS: QA-SEG-03*
"""T-REF-02-09: tokens cifrados en la Base primaria de viajes (con la pasiva en acuerdo) y
revocación de punta a punta contra el itinerario real."""
from datetime import datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from tests.test_ref02_adaptador import T0
from trotamundos.broker import Broker, NombreCola
from trotamundos.config import ConfiguracionBroker, ConfiguracionCorreo
from trotamundos.dominio.registro_tipos import RegistroTipos
from trotamundos.dominio.tipos_reserva import ReservaHotel
from trotamundos.entrada.adaptador_correo import AdaptadorCorreo
from trotamundos.entrada.api_correo import CorreoCrudo, MockApiCorreo
from trotamundos.entrada.gestor_autorizacion import (
    CifradorTokens,
    GestorAutorizacion,
    RepositorioTokensPostgres,
)
from trotamundos.orquestador.arranque import registrar_tipos
from trotamundos.persistencia.base_viajes import BaseViajes
from trotamundos.persistencia.conexion import conectar
from trotamundos.persistencia.repositorio_viajes import RepositorioViajes

pytestmark = pytest.mark.db


@pytest.fixture
def base(bases_limpias):
    return BaseViajes.desde_config(bases_limpias)


@pytest.fixture
def gestor(base):
    return GestorAutorizacion(
        RepositorioTokensPostgres(base), CifradorTokens(Fernet.generate_key()),
        ConfiguracionCorreo(), reloj=lambda: T0)


def test_token_se_guarda_cifrado_en_primaria_y_pasiva(gestor, bases_limpias):
    gestor.autorizar("t1", "token-secreto")
    for dsn in (bases_limpias.viajes_primaria, bases_limpias.viajes_pasiva):
        with conectar(dsn) as c:
            [(cifrado,)] = c.execute("SELECT token_cifrado FROM token_correo").fetchall()
        assert b"token-secreto" not in bytes(cifrado)
    assert gestor.token_vigente("t1") == "token-secreto"
    assert gestor.titulares_autorizados() == ["t1"]


def test_reautorizar_reemplaza_y_vencido_no_es_vigente(gestor):
    gestor.autorizar("t1", "uno")
    gestor.autorizar("t1", "dos")
    assert gestor.token_vigente("t1") == "dos"
    assert gestor.token_vigente("t1", ahora=T0 + timedelta(minutes=61)) is None


async def test_AC_REF_02_06_revocar_deja_de_leer_y_conserva_la_reserva_incorporada(
        gestor, base):
    registro = RegistroTipos()
    registrar_tipos(registro)
    itinerario = RepositorioViajes(base, registro)
    itinerario.insertar_viaje("v1", "t1")
    itinerario.insertar_reserva(ReservaHotel(
        identificador="desde-correo-1", viaje_id="v1", lugar="Lima",
        inicio=datetime(2026, 12, 1), fin=datetime(2026, 12, 5)))

    api = MockApiCorreo()
    api.emitir_token("t1", "tok")
    api.agregar_correo("t1", CorreoCrudo(cuerpo="c", remitente="a@b.c", message_id="<m1@x>",
                                         recibido=T0 - timedelta(days=1)))
    broker = Broker(ConfiguracionBroker(tamano_maximo_cola=5))
    adaptador = AdaptadorCorreo(api, gestor, broker, ConfiguracionCorreo())

    gestor.autorizar("t1", "tok")
    assert (await adaptador.sondear("t1", T0)).publicados == 1
    lecturas = api.lecturas

    gestor.revocar("t1")

    assert not (await adaptador.sondear("t1", T0 + timedelta(minutes=15))).leyo
    assert api.lecturas == lecturas
    assert broker.tamano_actual(NombreCola.CORREO) == 1
    assert gestor.titulares_autorizados() == []
    [viaje] = itinerario.listar_viajes("t1", "activo")
    assert [r.identificador for r in itinerario.reservas_de([viaje.id])] == ["desde-correo-1"]
