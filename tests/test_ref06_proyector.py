# SPEC: SPEC-REF-06
# ELEMENTO PASO 5: Proyector analítico (ITERACION_5)
# ADRs: ADR-IT5-002, ADR-IT3-003, ADR-IT3-002
# DRIVERS: REF-06
"""T-REF-06-04: el Proyector guarda, suma y descarta repetidos."""
from datetime import UTC, date, datetime

import pytest

from trotamundos.analitica.base import conectar
from trotamundos.analitica.proyector import Proyector
from trotamundos.broker import Aviso, Broker, Mensaje, NombreCola, ResultadoEntrega
from trotamundos.dominio.eventos import EventoAnalitico

pytestmark = pytest.mark.db
HOY = datetime(2026, 11, 23, 15, 0, tzinfo=UTC)


def evento(id_="e1", tipo="alta", destino="Roma", tipo_reserva="hotel", ocurrido=HOY):
    return EventoAnalitico(id=id_, tipo=tipo, tipo_reserva=tipo_reserva, destino=destino, origen="manual",
                           estado="confirmada", inicio=datetime(2026, 12, 1), fin=datetime(2026, 12, 5),
                           ocurrido_en=ocurrido)


def publicar(broker, *eventos):
    for e in eventos:
        broker.publicar(NombreCola.EVENTOS_ANALITICOS, Mensaje(e.id, e.model_dump(mode="json")))


def contadores(cfg):
    with conectar(cfg.dsn) as c:
        return {(str(f[0]), f[1], f[2], f[3]): f[4] for f in c.execute(
            "SELECT dia, destino, tipo_reserva, tipo_evento, cantidad FROM contador").fetchall()}


def cuantos(cfg, tabla):
    with conectar(cfg.dsn) as c:
        return c.execute(f"SELECT count(*) FROM {tabla}").fetchone()[0]


@pytest.fixture
def proyector(analitica_limpia, cfg_broker):
    async def sin_espera(_s):
        return None
    broker = Broker(cfg_broker, dormir=sin_espera)
    p = Proyector(broker, analitica_limpia.dsn)
    yield broker, p
    p.cerrar()


async def test_AC_REF_06_02_el_proyector_guarda_el_evento_y_actualiza_los_contadores(proyector, analitica_limpia):
    broker, p = proyector
    publicar(broker, evento())
    assert await p.procesar_uno() is ResultadoEntrega.ENTREGADO
    assert await p.procesar_uno() is ResultadoEntrega.VACIA
    assert cuantos(analitica_limpia, "evento") == 1
    assert contadores(analitica_limpia) == {("2026-11-23", "Roma", "hotel", "alta"): 1}
    with conectar(analitica_limpia.dsn) as c:
        fila = c.execute("SELECT tipo, destino, tipo_reserva, origen, estado, dia FROM evento").fetchone()
    assert fila == ("alta", "Roma", "hotel", "manual", "confirmada", date(2026, 11, 23))


async def test_los_contadores_se_acumulan_por_destino_dia_y_tipo_de_reserva(proyector, analitica_limpia):
    broker, p = proyector
    publicar(broker, evento("a"), evento("b"), evento("c", destino="Lima"), evento("d", tipo_reserva="vuelo"),
             evento("e", ocurrido=datetime(2026, 11, 24, 1, 0, tzinfo=UTC)))
    for _ in range(5):
        await p.procesar_uno()
    assert contadores(analitica_limpia) == {
        ("2026-11-23", "Roma", "hotel", "alta"): 2, ("2026-11-23", "Lima", "hotel", "alta"): 1,
        ("2026-11-23", "Roma", "vuelo", "alta"): 1, ("2026-11-24", "Roma", "hotel", "alta"): 1}


async def test_el_dia_es_el_del_evento_en_utc(proyector, analitica_limpia):
    from datetime import timedelta, timezone
    broker, p = proyector
    publicar(broker, evento("x", ocurrido=datetime(2026, 11, 23, 22, 0, tzinfo=timezone(timedelta(hours=-5)))))
    await p.procesar_uno()  # 22:00 en UTC-5 es 03:00 del día siguiente en UTC
    assert list(contadores(analitica_limpia)) == [("2026-11-24", "Roma", "hotel", "alta")]


async def test_AC_REF_06_05_la_baja_logica_suma_a_las_cancelaciones_de_ese_destino_y_dia(proyector, analitica_limpia):
    broker, p = proyector
    publicar(broker, evento("a", tipo="alta"), evento("b", tipo="baja"), evento("c", tipo="baja", destino="Lima"))
    for _ in range(3):
        await p.procesar_uno()
    c = contadores(analitica_limpia)
    assert c[("2026-11-23", "Roma", "hotel", "baja")] == 1 and c[("2026-11-23", "Lima", "hotel", "baja")] == 1


async def test_AC_REF_06_06_un_evento_repetido_no_se_guarda_ni_suma_de_nuevo(proyector, analitica_limpia):
    broker, p = proyector
    publicar(broker, evento("e1"), evento("e1"), evento("e1"))  # el mismo identificador, tres veces
    for _ in range(3):
        assert await p.procesar_uno() is ResultadoEntrega.ENTREGADO  # no es un fallo: se descarta
    assert cuantos(analitica_limpia, "evento") == 1
    assert contadores(analitica_limpia) == {("2026-11-23", "Roma", "hotel", "alta"): 1}
    assert p.proyectar(evento("e1")) is False  # y la proyección lo dice


async def test_AC_REF_06_13_cada_evento_suma_solo_a_su_contador_sin_recalcular_la_reserva(proyector, analitica_limpia):
    broker, p = proyector
    # la misma reserva a lo largo de su vida: alta, modificación y baja. El evento no dice cuál es.
    publicar(broker, evento("a", tipo="alta"), evento("m", tipo="modificacion"), evento("b", tipo="baja"))
    for _ in range(3):
        await p.procesar_uno()
    assert contadores(analitica_limpia) == {
        ("2026-11-23", "Roma", "hotel", "alta"): 1,
        ("2026-11-23", "Roma", "hotel", "modificacion"): 1,
        ("2026-11-23", "Roma", "hotel", "baja"): 1}
    with conectar(analitica_limpia.dsn) as c:
        columnas = {f[0] for f in c.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'evento'").fetchall()}
    assert not columnas & {"reserva_id", "identificador", "viaje_id", "cuenta_id"}  # no sabe de qué reserva es


async def test_el_archivado_se_cuenta_con_destino_y_tipo_vacios(proyector, analitica_limpia):
    broker, p = proyector
    publicar(broker, EventoAnalitico(id="ar", tipo="archivado", ocurrido_en=HOY))
    await p.procesar_uno()
    assert contadores(analitica_limpia) == {("2026-11-23", "", "", "archivado"): 1}


async def test_una_falla_transitoria_de_escritura_se_reintenta_sin_contar_dos_veces(proyector, analitica_limpia):
    broker, p = proyector
    original, llamadas = p.proyectar, []

    def inestable(e):
        llamadas.append(1)
        if len(llamadas) == 1:
            raise OSError("falla transitoria de escritura")
        return original(e)
    p.proyectar = inestable
    publicar(broker, evento())
    assert await p.procesar_uno() is ResultadoEntrega.ENTREGADO  # el Retry del Broker lo reintentó
    assert len(llamadas) == 2
    assert contadores(analitica_limpia) == {("2026-11-23", "Roma", "hotel", "alta"): 1}


async def test_con_la_base_analitica_caida_el_evento_agota_reintentos_y_va_a_mensajes_muertos(cfg_broker):
    avisos: list[Aviso] = []
    esperas: list[float] = []

    async def dormir(s):
        esperas.append(s)
    broker = Broker(cfg_broker, avisar=avisos.append, dormir=dormir)
    p = Proyector(broker, "postgresql://x:x@localhost:1/nada")  # inalcanzable
    publicar(broker, evento())
    assert await p.procesar_uno() is ResultadoEntrega.MUERTO
    assert esperas == [1.0, 2.0, 4.0]
    assert [m.id for m in broker.mensajes_muertos(NombreCola.EVENTOS_ANALITICOS)] == ["e1"]
    assert avisos == [Aviso("mensaje_muerto", NombreCola.EVENTOS_ANALITICOS, "e1")]


async def test_un_mensaje_con_campos_de_mas_se_rechaza_y_no_se_guarda(proyector, analitica_limpia):
    broker, p = proyector
    cuerpo = {**evento().model_dump(mode="json"), "cuenta_id": "ana"}  # un dato personal que no admite
    broker.publicar(NombreCola.EVENTOS_ANALITICOS, Mensaje("x", cuerpo))
    assert await p.procesar_uno() is ResultadoEntrega.MUERTO
    assert cuantos(analitica_limpia, "evento") == 0
