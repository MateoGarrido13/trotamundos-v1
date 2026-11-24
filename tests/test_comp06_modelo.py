# SPEC: SPEC-COMP-06 | PLAN-COMP-06 T-COMP-06-01
from tests.comp06_util import CRITERIOS
from tests.test_arquitectura import _archivos, _imports
from trotamundos.config import Configuracion, ConfiguracionCotizacion
from trotamundos.dominio.cotizacion import EstadoOrigen, Grilla, ProgresoGrilla, ResultadoOrigen


def test_AC_COMP_06_12_cotizacion_no_usa_broker_ni_base():
    """La cotización no importa el Broker, la persistencia ni el conector SQL."""
    prohibidos = ("trotamundos.broker", "trotamundos.persistencia", "psycopg")
    archivos = _archivos("cotizacion")
    assert len(archivos) >= 8
    for archivo in archivos:
        malos = [m for m in _imports(archivo) if any(m == p or m.startswith(p + ".") for p in prohibidos)]
        assert not malos, f"{archivo.name} importa {malos}"


def test_los_parametros_tienen_los_valores_de_la_spec():
    cfg = Configuracion().cotizacion
    assert (cfg.cota_cotizacion_ms, cfg.cota_aerolineas_ms, cfg.cota_hoteles_ms, cfg.cota_arrendadoras_ms) == (
        800, 600, 500, 500)
    assert cfg.vigencia_copia_segundos == 300 and cfg.nodos_cotizacion == 2
    assert all(c < cfg.cota_cotizacion_ms for c in (cfg.cota_aerolineas_ms, cfg.cota_hoteles_ms,
                                                    cfg.cota_arrendadoras_ms))


def test_los_parametros_se_leen_del_entorno(monkeypatch):
    monkeypatch.setenv("TROTA_COTA_COTIZACION_MS", "123")
    import importlib

    from trotamundos import config
    try:
        importlib.reload(config)
        assert config.ConfiguracionCotizacion().cota_cotizacion_ms == 123
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_progreso_marca_los_que_faltan_como_no_respondio():
    p = ProgresoGrilla()
    p.iniciar(("a", "b", "c"))
    p.registrar(ResultadoOrigen("b", EstadoOrigen.OK))
    g = p.a_grilla()
    assert [(o.proveedor, o.estado.value) for o in g.origenes] == [
        ("a", "no_respondio"), ("b", "ok"), ("c", "no_respondio")]
    assert not g.completa and not g.en_curso


def test_sin_ningun_origen_ok_es_en_curso_y_con_todos_ok_es_completa():
    p = ProgresoGrilla()
    p.iniciar(("a", "b"))
    assert p.a_grilla().en_curso
    p.registrar(ResultadoOrigen("a", EstadoOrigen.OK))
    p.registrar(ResultadoOrigen("b", EstadoOrigen.OK))
    assert p.a_grilla().completa and not p.a_grilla().en_curso


def test_grilla_a_dict_tiene_la_forma_del_contrato():
    g = Grilla((ResultadoOrigen("a", EstadoOrigen.OK),), completa=True)
    assert set(g.a_dict()) == {"origenes", "completa", "copia", "en_curso"}
    assert g.a_dict()["origenes"][0] == {"proveedor": "a", "estado": "ok", "precios": []}
    assert CRITERIOS.clave() == ("2027-01-10", "hotel", "familia")
