# SPEC: SPEC-REF-06
# ELEMENTO PASO 5: Cola de eventos analíticos, Base analítica (ITERACION_5)
# ADRs: ADR-IT5-001, ADR-IT5-002
# DRIVERS: REF-06, QA-DIS-01
"""T-REF-06-01: el evento anonimizado, el Broker y la Base analítica."""
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from trotamundos.analitica.base import conectar
from trotamundos.broker import Aviso, Broker, Mensaje, NombreCola
from trotamundos.dominio.eventos import CAMPOS_PERMITIDOS, EventoAnalitico

AHORA = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
PROHIBIDOS = {"cuenta", "cuenta_id", "actor", "correo", "email", "nombre", "descripcion",
              "resumen_dialogo", "token", "credenciales", "clave", "reserva_id", "identificador",
              "viaje_id", "itinerario_id", "remitente", "titular_id"}


def evento(**extra) -> EventoAnalitico:
    base = dict(id="e1", tipo="alta", tipo_reserva="hotel", destino="Roma", origen="manual",
                estado="confirmada", inicio=datetime(2026, 12, 1), fin=datetime(2026, 12, 5),
                ocurrido_en=AHORA)
    return EventoAnalitico(**{**base, **extra})


def test_AC_REF_06_07_el_evento_no_contiene_datos_personales():
    for tipo in ("alta", "modificacion", "baja", "archivado"):
        campos = set(evento(tipo=tipo).model_dump())
        assert campos == set(CAMPOS_PERMITIDOS)
        assert not campos & PROHIBIDOS, campos & PROHIBIDOS
    assert CAMPOS_PERMITIDOS == {"id", "tipo", "tipo_reserva", "destino", "inicio", "fin", "origen",
                                 "estado", "ocurrido_en"}


@pytest.mark.parametrize("campo", sorted(PROHIBIDOS))
def test_el_evento_rechaza_cualquier_campo_que_no_este_en_la_lista_cerrada(campo):
    with pytest.raises(ValidationError):
        evento(**{campo: "valor"})


def test_el_evento_de_archivado_no_trae_destino_ni_tipo_de_reserva():
    e = EventoAnalitico(id="e2", tipo="archivado", ocurrido_en=AHORA)
    assert (e.tipo_reserva, e.destino, e.inicio, e.fin, e.origen, e.estado) == (None,) * 6


def test_un_tipo_de_evento_desconocido_se_rechaza():
    with pytest.raises(ValidationError):
        evento(tipo="compra")


def test_el_broker_manda_a_muertos_lo_que_el_publicador_no_pudo_encolar(cfg_broker):
    avisos: list[Aviso] = []
    b = Broker(cfg_broker, avisar=avisos.append)
    b.enviar_a_muertos(NombreCola.EVENTOS_ANALITICOS, Mensaje("e1", {"x": 1}))
    assert [m.id for m in b.mensajes_muertos(NombreCola.EVENTOS_ANALITICOS)] == ["e1"]
    assert avisos == [Aviso("mensaje_muerto", NombreCola.EVENTOS_ANALITICOS, "e1")]


@pytest.mark.db
def test_la_base_analitica_es_una_base_distinta_de_las_de_viajes(analitica_limpia, bases_limpias):
    assert analitica_limpia.dsn not in (bases_limpias.viajes_primaria, bases_limpias.viajes_pasiva)
    with conectar(analitica_limpia.dsn) as c:
        assert c.execute("SELECT current_database()").fetchone()[0] == "analitica"
        tablas = {f[0] for f in c.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'").fetchall()}
    assert tablas == {"evento", "contador"}  # sin cuentas, correos ni credenciales
    with conectar(bases_limpias.viajes_primaria) as c:
        assert c.execute("SELECT to_regclass('public.evento')").fetchone()[0] is None
