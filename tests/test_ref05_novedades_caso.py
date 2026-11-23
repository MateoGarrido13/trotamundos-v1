# SPEC: SPEC-REF-05
# ELEMENTO PASO 5: Adaptador de agencia, ingesta y Orquestador (ITERACION_4)
# ADRs: ADR-IT4-010, ADR-IT3-003, ADR-IT3-002
# DRIVERS: REF-05
"""T-REF-05-06: la vuelta de los cambios de estado, por la cola de novedades y la ingesta."""
import pytest
from fastapi.testclient import TestClient

from tests.ref04_util import ITIN, LUIS
from tests.ref05_util import (  # noqa: F401
    AGENCIAS,
    CLAVE_AGENCIA,
    app,
    con_agencia,
    estado_del_caso,
    reserva_de,
)
from trotamundos.broker import Mensaje, NombreCola, ResultadoEntrega
from trotamundos.dominio.agencias import EstadoCaso
from trotamundos.entrada.agencia import ClaveInvalida, ErrorAgencia
from trotamundos.entrada.app import create_app as crear_app_de_entrada

pytestmark = pytest.mark.db


class Sistema:
    def __init__(self, app):
        self.app = app
        self.adaptador = app.state.adaptador_agencia
        self.agencia = self.adaptador.agencias["agencia-a"]
        self.ingesta = app.state.nodos_correo.ingesta

    async def reportar(self, clave="k1"):
        ident = await reserva_de(self.app, clave=f"r-{clave}")
        await con_agencia(self.app)
        r = await self.app.state.casos.reportar(LUIS, ITIN, clave, ident, "Problema")
        await self.app.state.casos.esperar_publicaciones()
        return r.caso["id"]

    async def entregar_a_la_agencia(self):
        assert await self.adaptador.procesar_uno() is ResultadoEntrega.ENTREGADO

    async def avisar(self, id_caso, clave=CLAVE_AGENCIA, agencia="agencia-a"):
        return await self.adaptador.recibir_aviso(agencia, id_caso, clave)

    async def ingerir_todo(self):
        while await self.ingesta.procesar_uno() is not ResultadoEntrega.VACIA:
            pass


@pytest.fixture
def sistema(app):
    return Sistema(app)


async def test_AC_REF_05_05_el_aviso_de_la_agencia_llega_al_viajero_por_novedades(sistema, app):
    caso_id = await sistema.reportar()
    await sistema.entregar_a_la_agencia()
    assert estado_del_caso(app, caso_id) == "en_tramite"  # el Orquestador aún no sabe que se abrió
    sistema.agencia.cambiar_estado(caso_id, EstadoCaso.EN_CURSO)

    assert await sistema.avisar(caso_id) == "publicado"  # el adaptador consultó el estado
    assert sistema.agencia.consultas == 1
    assert app.state.broker.tamano_actual(NombreCola.NOVEDADES) == 1
    await sistema.ingerir_todo()  # la ingesta se lo entrega al Orquestador

    assert estado_del_caso(app, caso_id) == "en_curso"
    assert [(c["id"], c["estado"]) for c in await app.state.casos.consultar(LUIS)] == [(caso_id, "en_curso")]


async def test_el_caso_recorre_todos_los_estados_hasta_resuelto(sistema, app):
    caso_id = await sistema.reportar()
    await sistema.entregar_a_la_agencia()
    for estado in (EstadoCaso.ABIERTO, EstadoCaso.EN_CURSO, EstadoCaso.RESUELTO):
        sistema.agencia.cambiar_estado(caso_id, estado)
        await sistema.avisar(caso_id)
        await sistema.ingerir_todo()
        assert estado_del_caso(app, caso_id) == estado.value


async def test_AC_REF_05_14_clave_invalida_no_consulta_ni_publica(sistema, app):
    caso_id = await sistema.reportar()
    await sistema.entregar_a_la_agencia()
    for clave in ("incorrecta", "", None):
        with pytest.raises(ClaveInvalida):
            await sistema.avisar(caso_id, clave=clave)
    assert sistema.agencia.consultas == 0  # no se consultó nada
    assert app.state.broker.tamano_actual(NombreCola.NOVEDADES) == 0  # ni se publicó


async def test_sin_clave_configurada_ningun_aviso_es_valido(sistema, app):
    sistema.adaptador._cfg = type(sistema.adaptador._cfg)(clave_aviso="")
    with pytest.raises(ClaveInvalida):
        await sistema.avisar("caso-1", clave="")


async def test_AC_REF_05_15_una_novedad_que_retrocede_el_estado_se_ignora(sistema, app):
    caso_id = await sistema.reportar()
    await sistema.entregar_a_la_agencia()
    sistema.agencia.cambiar_estado(caso_id, EstadoCaso.EN_CURSO)
    await sistema.avisar(caso_id)
    await sistema.ingerir_todo()
    assert estado_del_caso(app, caso_id) == "en_curso"

    sistema.agencia.cambiar_estado(caso_id, EstadoCaso.ABIERTO)  # llega «abierto» con el caso «en curso»
    assert await sistema.avisar(caso_id) == "publicado"
    await sistema.ingerir_todo()
    assert estado_del_caso(app, caso_id) == "en_curso"  # se ignora: sigue «en curso»


async def test_una_novedad_repetida_la_ingesta_la_descarta(sistema, app, monkeypatch):
    caso_id = await sistema.reportar()
    await sistema.entregar_a_la_agencia()
    llamadas = []
    original = app.state.casos.aplicar_estado_caso

    async def espia(id_caso, estado):
        llamadas.append((id_caso, estado))
        return await original(id_caso, estado)
    monkeypatch.setattr(app.state.casos, "aplicar_estado_caso", espia)
    sistema.agencia.cambiar_estado(caso_id, EstadoCaso.ABIERTO)
    await sistema.avisar(caso_id)
    await sistema.avisar(caso_id)  # la agencia avisa dos veces el mismo cambio
    await sistema.ingerir_todo()
    assert llamadas == [(caso_id, EstadoCaso.ABIERTO)]  # el Orquestador lo recibió una vez


async def test_un_caso_desconocido_para_la_agencia_no_publica_nada(sistema, app):
    assert await sistema.avisar("caso-que-la-agencia-no-conoce") == "desconocido"
    assert sistema.agencia.consultas == 1
    assert app.state.broker.tamano_actual(NombreCola.NOVEDADES) == 0


async def test_una_agencia_que_no_responde_a_consultarcaso_pierde_el_aviso(sistema, app):
    caso_id = await sistema.reportar()
    await sistema.entregar_a_la_agencia()
    sistema.agencia.caida = True
    with pytest.raises(ErrorAgencia):
        await sistema.avisar(caso_id)
    assert app.state.broker.tamano_actual(NombreCola.NOVEDADES) == 0  # puede avisar de nuevo


async def test_AC_REF_05_04_el_caso_queda_sin_entregar_y_visible_con_opcion_de_reintentar(sistema, app):
    caso_id = await sistema.reportar()
    sistema.agencia.caida = True
    assert await sistema.adaptador.procesar_uno() is ResultadoEntrega.MUERTO
    await sistema.ingerir_todo()
    assert estado_del_caso(app, caso_id) == "sin_entregar"
    assert [(c["id"], c["estado"]) for c in await app.state.casos.consultar(LUIS)] == [(caso_id, "sin_entregar")]
    sistema.agencia.caida = False  # la agencia vuelve y el viajero reintenta
    r = await app.state.casos.reintentar(LUIS, ITIN, caso_id, "reintento")
    assert r.estado == "ok"
    await app.state.casos.esperar_publicaciones()
    await sistema.entregar_a_la_agencia()
    assert list(sistema.agencia.casos) == [caso_id]


async def test_una_novedad_sobre_un_caso_sin_entregar_no_lo_saca_de_ese_estado(sistema, app):
    caso_id = await sistema.reportar()
    sistema.agencia.caida = True
    await sistema.adaptador.procesar_uno()
    await sistema.ingerir_todo()
    sistema.agencia.caida = False
    sistema.agencia.cambiar_estado(caso_id, EstadoCaso.ABIERTO)
    await sistema.avisar(caso_id)
    await sistema.ingerir_todo()
    assert estado_del_caso(app, caso_id) == "sin_entregar"  # solo se sale reintentando


async def test_la_novedad_de_un_caso_que_el_orquestador_no_tiene_se_ignora(app, sistema):
    app.state.broker.publicar(NombreCola.NOVEDADES, Mensaje(
        "caso:desconocido:abierto", {"origen": "caso", "id_caso": "desconocido", "estado": "abierto"}))
    await sistema.ingerir_todo()  # no falla ni queda en mensajes muertos
    assert app.state.broker.mensajes_muertos(NombreCola.NOVEDADES) == []


async def test_un_origen_desconocido_termina_en_mensajes_muertos(app, sistema):
    app.state.broker.publicar(NombreCola.NOVEDADES, Mensaje("x", {"origen": "marte"}))
    assert await sistema.ingesta.procesar_uno() is ResultadoEntrega.MUERTO


# --- el listener (HTTP) -------------------------------------------------------------------
@pytest.fixture
def listener(app, sistema):
    from fastapi import FastAPI  # el gestor de correo no interviene: solo el listener de agencia
    from trotamundos.entrada import api_agencia
    nodo = FastAPI()
    nodo.include_router(api_agencia.crear_router(app.state.adaptador_agencia))
    return TestClient(nodo)


async def test_el_listener_rechaza_la_clave_invalida_sin_consultar(listener, sistema):
    r = listener.post("/agencia/agencia-a/avisos", json={"id_caso": "caso-1"}, headers={"X-Clave-Agencia": "mala"})
    assert r.status_code == 401
    assert listener.post("/agencia/agencia-a/avisos", json={"id_caso": "caso-1"}).status_code == 401
    assert sistema.agencia.consultas == 0


async def test_el_listener_publica_y_responde_los_codigos_del_contrato(listener, sistema, app):
    caso_id = await sistema.reportar()
    await sistema.entregar_a_la_agencia()
    sistema.agencia.cambiar_estado(caso_id, EstadoCaso.RESUELTO)
    cab = {"X-Clave-Agencia": CLAVE_AGENCIA}
    assert listener.post("/agencia/agencia-a/avisos", json={"id_caso": caso_id}, headers=cab).json() == {"resultado": "publicado"}
    assert listener.post("/agencia/agencia-a/avisos", json={"id_caso": "otro"}, headers=cab).json() == {"resultado": "desconocido"}
    assert listener.post("/agencia/no-existe/avisos", json={"id_caso": caso_id}, headers=cab).status_code == 404
    sistema.agencia.caida = True  # la agencia no responde a consultarCaso: 503 y puede avisar de nuevo
    assert listener.post("/agencia/agencia-a/avisos", json={"id_caso": caso_id}, headers=cab).status_code == 503


async def test_el_listener_responde_503_si_la_cola_de_novedades_esta_llena(listener, sistema, app):
    caso_id = await sistema.reportar()
    await sistema.entregar_a_la_agencia()
    for i in range(5):
        app.state.broker.publicar(NombreCola.NOVEDADES, Mensaje(f"relleno-{i}", {}))
    r = listener.post("/agencia/agencia-a/avisos", json={"id_caso": caso_id},
                      headers={"X-Clave-Agencia": CLAVE_AGENCIA})
    assert r.status_code == 503  # la agencia delega: reentrega el aviso
