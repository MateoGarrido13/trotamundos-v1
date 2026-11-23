# SPEC: SPEC-REF-06
# ELEMENTO PASO 5: Orquestador de viajes, eventos de alta, modificación, baja y archivado (ITERACION_5)
# ADRs: ADR-IT5-001, ADR-IT3-002, ADR-IT4-008
# DRIVERS: REF-06, QA-PER-02, QA-DIS-01
"""T-REF-06-03: cada escritura confirmada publica un evento anonimizado en la quinta cola."""
import time
from datetime import UTC, datetime

import pytest

from tests.ref03_util import reserva_norm
from tests.ref04_util import ANA, INTRUSO, ITIN, LUIS, precargar, reserva_externa, solicitud
from trotamundos.app import create_app
from trotamundos.broker import NombreCola
from trotamundos.config import Configuracion, ConfiguracionAnalitica, ConfiguracionBroker
from trotamundos.dominio.eventos import CAMPOS_PERMITIDOS
from trotamundos.dominio.reserva import Origen
from trotamundos.orquestador.archivado import archivar_y_emitir
from trotamundos.orquestador.incorporacion import IncorporadorReservas
from trotamundos.orquestador.novedades import NovedadProveedor

pytestmark = pytest.mark.db


async def sin_espera(_s):
    return None


@pytest.fixture
def app(bases_limpias):
    cfg = Configuracion(
        bases=bases_limpias,
        broker=ConfiguracionBroker(tamano_maximo_cola=5, reintentos=3, backoff_base_segundos=1.0),
        analitica=ConfiguracionAnalitica(tamano_cola_eventos=5, dsn="postgresql://x:x@localhost:1/nada"))
    app = create_app(cfg)
    precargar(app)
    app.state.emisor_eventos._dormir = sin_espera
    return app


async def eventos(app):
    await app.state.emisor_eventos.esperar()
    return [m.cuerpo for m in app.state.broker._colas[NombreCola.EVENTOS_ANALITICOS]]


async def test_AC_REF_06_01_cada_alta_modificacion_baja_y_archivado_publica_un_evento_anonimizado(app):
    r = await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud(lugar="Coliseo"))
    ident = r.reserva["identificador"]
    await app.state.gestion.actualizar(LUIS, ITIN, ident, "k2", {"lugar": "Foro Romano"})
    await app.state.gestion.eliminar(LUIS, ITIN, ident, "k3")
    alta, modificacion, baja = await eventos(app)

    assert (alta["tipo"], alta["tipo_reserva"], alta["destino"], alta["origen"], alta["estado"]) == (
        "alta", "actividad", "Coliseo", "manual", "confirmada")
    assert alta["inicio"] == "2026-12-02T09:00:00" and alta["fin"] == "2026-12-02T12:00:00"
    assert (modificacion["tipo"], modificacion["destino"]) == ("modificacion", "Foro Romano")
    assert (baja["tipo"], baja["destino"], baja["tipo_reserva"]) == ("baja", "Foro Romano", "actividad")
    assert len({e["id"] for e in (alta, modificacion, baja)}) == 3  # un identificador por evento

    # el archivado de un viaje completo publica su propio evento, sin destino ni tipo de reserva
    await app.state.gestion.agregar(LUIS, ITIN, "k4", solicitud(viaje_id="paris", lugar="Louvre"))
    await archivar_y_emitir(app.state.repositorio, datetime(2027, 1, 1, tzinfo=UTC), app.state.emisor_eventos)
    ultimo = (await eventos(app))[-1]
    assert (ultimo["tipo"], ultimo["tipo_reserva"], ultimo["destino"]) == ("archivado", None, None)


async def test_la_reserva_que_entra_por_el_correo_publica_un_alta_con_origen_correo(app):
    incorporador = IncorporadorReservas(app.state.repositorio, app.state.registro_tipos, app.state.emisor_eventos)
    await incorporador.incorporar(reserva_norm(lugar="Lima"))
    await incorporador.incorporar(reserva_norm(lugar="Lima"))  # entrega repetida: no es otra alta
    [alta] = await eventos(app)
    assert (alta["tipo"], alta["origen"], alta["destino"]) == ("alta", "correo", "Lima")


async def test_una_novedad_aplicada_publica_una_modificacion_con_origen_proveedor(app):
    reserva_externa(app, "h1", Origen.PROVEEDOR)
    await app.state.novedades.aplicar(NovedadProveedor(id="n1", reserva_id="h1", cambios={"lugar": "Otro hotel"}))
    await app.state.novedades.aplicar(NovedadProveedor(id="n1", reserva_id="h1", cambios={"lugar": "Otro hotel"}))
    [modificacion] = await eventos(app)
    assert (modificacion["tipo"], modificacion["origen"], modificacion["destino"]) == (
        "modificacion", "proveedor", "Otro hotel")


async def test_una_novedad_retenida_no_publica_nada(app):
    reserva_externa(app, "h1", Origen.PROVEEDOR)
    await app.state.gestion.actualizar(ANA, ITIN, "h1", "k1", {"lugar": "A mano"})
    antes = len(await eventos(app))
    await app.state.novedades.aplicar(NovedadProveedor(id="n1", reserva_id="h1", cambios={"lugar": "Otro"}))
    assert len(await eventos(app)) == antes  # la edición manual tiene precedencia: nada cambió


async def test_una_clave_repetida_no_publica_otro_evento(app):
    await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud())
    await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud())
    assert len(await eventos(app)) == 1


async def test_lo_denegado_o_rechazado_no_publica_nada(app):
    await app.state.gestion.agregar(INTRUSO, ITIN, "k1", solicitud())  # sin permiso
    await app.state.gestion.agregar(LUIS, ITIN, "k2", solicitud(tipo="cohete"))  # tipo inválido
    await app.state.gestion.actualizar(LUIS, ITIN, "no-existe", "k3", {"lugar": "X"})
    assert await eventos(app) == []


async def test_una_escritura_que_falla_no_publica_nada(app):
    def falla():
        raise RuntimeError("falla inyectada")
    app.state.gestion._gancho_fallo = falla
    with pytest.raises(RuntimeError):
        await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud())
    assert await eventos(app) == []  # el evento se publica solo después de confirmar


async def test_AC_REF_06_07_los_eventos_reales_no_contienen_datos_personales(app):
    r = await app.state.gestion.agregar(LUIS, ITIN, "clave-secreta", solicitud(lugar="Coliseo"))
    await app.state.casos.elegir_agencia(LUIS, "agencia-a", True)
    await app.state.casos.reportar(LUIS, ITIN, "k9", r.reserva["identificador"], "Mi pasaporte es 123",
                                   resumen_dialogo="Hablé con el asistente")
    await app.state.casos.esperar_publicaciones()
    for e in await eventos(app):
        assert set(e) == set(CAMPOS_PERMITIDOS)
        texto = str(e)
        for secreto in (LUIS, ANA, ITIN, "res-", "clave-secreta", "pasaporte", "asistente", "viaje", "caso-"):
            assert secreto not in texto, (secreto, e)


async def test_AC_REF_06_08_con_la_cola_llena_la_respuesta_al_viajero_no_se_demora(app):
    from trotamundos.broker import Mensaje
    for i in range(5):
        app.state.broker.publicar(NombreCola.EVENTOS_ANALITICOS, Mensaje(f"relleno-{i}", {}))
    esperas = []

    async def dormir(s):
        esperas.append(s)
        await __import__("asyncio").sleep(0.5)  # cada reintento tarda: la respuesta no puede esperarlos
    app.state.emisor_eventos._dormir = dormir

    inicio = time.perf_counter()
    r = await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud())
    demora = time.perf_counter() - inicio
    assert r.estado == "ok" and demora < 0.5  # no esperó el primer reintento
    app.state.emisor_eventos._dormir = sin_espera
    await app.state.emisor_eventos.esperar()
    [muerto] = app.state.broker.mensajes_muertos(NombreCola.EVENTOS_ANALITICOS)
    assert muerto.cuerpo["tipo"] == "alta"  # agotados los reintentos: mensajes muertos


async def test_AC_REF_06_09_con_la_base_analitica_caida_las_operaciones_del_viajero_se_completan(app):
    """El Orquestador solo habla con el Broker: la Base analítica (aquí, un DSN inalcanzable) no
    interviene en su camino."""
    r = await app.state.gestion.agregar(LUIS, ITIN, "k1", solicitud())
    ident = r.reserva["identificador"]
    assert (await app.state.gestion.actualizar(LUIS, ITIN, ident, "k2", {"lugar": "X"})).estado == "ok"
    assert (await app.state.gestion.eliminar(LUIS, ITIN, ident, "k3")).estado == "ok"
    assert [e["tipo"] for e in await eventos(app)] == ["alta", "modificacion", "baja"]
