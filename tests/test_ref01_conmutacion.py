# SPEC: SPEC-REF-01
# ELEMENTO PASO 5: Base primaria y Base pasiva, Reconfiguration (ITERACION_2)
# ADRs: ADR-IT2-005
# DRIVERS: QA-DIS-01
import subprocess
import time

import psycopg
import pytest

from trotamundos.persistencia.base_viajes import BaseViajes, ErrorBaseNoDisponible
from trotamundos.persistencia.conexion import conectar

pytestmark = pytest.mark.db


class Interruptor:
    def __init__(self):
        self.caida = False


def _fabrica(dsn, interruptor):
    def f():
        if interruptor.caida:
            raise psycopg.OperationalError("conexión rechazada (inyectada)")
        return conectar(dsn, autocommit=True)
    return f


def _alta(vid):
    return lambda c: c.execute("INSERT INTO viaje (id, viajero_id) VALUES (%s, 'ana')", (vid,))


def _ids(c):
    return [f[0] for f in c.execute("SELECT id FROM viaje ORDER BY id").fetchall()]


def _montar(cfg, umbral):
    prim, pas = Interruptor(), Interruptor()
    base = BaseViajes(_fabrica(cfg.viajes_primaria, prim), _fabrica(cfg.viajes_pasiva, pas), umbral=umbral)
    return base, prim, pas


def test_AC_REF_01_05_primaria_caida_atiende_la_pasiva(bases_limpias):
    base, prim, _ = _montar(bases_limpias, umbral=2)
    base.escribir(_alta("v1"))
    prim.caida = True
    # primer fallo: todavía no se conmuta, no hay servicio para esa llamada
    with pytest.raises(ErrorBaseNoDisponible):
        base.leer(_ids)
    assert not base.conmutada
    # segundo fallo consecutivo: alcanza el umbral y la pasiva atiende la lectura
    assert base.leer(_ids) == ["v1"]
    assert base.conmutada and base.atiende == "pasiva"
    # la escritura también la atiende la pasiva, sin acuerdo de segunda copia
    base.escribir(_alta("v2"))
    assert base.leer(_ids) == ["v1", "v2"]
    with conectar(bases_limpias.viajes_pasiva) as c:
        assert _ids(c) == ["v1", "v2"]
    # la primaria vieja queda bloqueada: no recibe más escrituras aunque vuelva
    assert base.primaria_no_escribible
    prim.caida = False
    base.escribir(_alta("v3"))
    with conectar(bases_limpias.viajes_primaria) as c:
        assert _ids(c) == ["v1"]


def test_escritura_con_primaria_caida_conmuta_y_escribe_en_la_pasiva(bases_limpias):
    base, prim, _ = _montar(bases_limpias, umbral=1)
    prim.caida = True
    base.escribir(_alta("v1"))
    assert base.conmutada
    with conectar(bases_limpias.viajes_pasiva) as c:
        assert _ids(c) == ["v1"]


def test_un_exito_reinicia_el_contador_de_fallos(bases_limpias):
    base, prim, _ = _montar(bases_limpias, umbral=2)
    prim.caida = True
    with pytest.raises(ErrorBaseNoDisponible):
        base.leer(_ids)
    prim.caida = False
    base.leer(_ids)
    assert base.fallos_consecutivos == 0
    prim.caida = True
    with pytest.raises(ErrorBaseNoDisponible):
        base.leer(_ids)
    assert not base.conmutada


def test_con_ambas_bases_caidas_hay_error_de_servicio_no_disponible(bases_limpias):
    base, prim, pas = _montar(bases_limpias, umbral=1)
    prim.caida = pas.caida = True
    with pytest.raises(ErrorBaseNoDisponible):
        base.leer(_ids)
    with pytest.raises(ErrorBaseNoDisponible):
        base.escribir(_alta("v1"))


def _contenedor_primaria() -> str:
    r = subprocess.run(["docker", "ps", "-aq", "--filter", "publish=5433"],
                       capture_output=True, text=True, check=True)
    return r.stdout.split()[0]


def _esperar_sano(cid: str, dsn: str) -> None:
    for _ in range(60):
        try:
            conectar(dsn).close()
            return
        except psycopg.OperationalError:
            time.sleep(1)
    raise RuntimeError("la primaria no volvió a estar sana")


def test_primaria_detenida_de_verdad_atiende_la_pasiva(bases_limpias):
    cid = _contenedor_primaria()
    base = BaseViajes(lambda: conectar(bases_limpias.viajes_primaria, autocommit=True),
                      lambda: conectar(bases_limpias.viajes_pasiva, autocommit=True), umbral=1)
    base.escribir(_alta("v1"))
    subprocess.run(["docker", "stop", cid], check=True, capture_output=True)
    try:
        assert base.leer(_ids) == ["v1"]
        assert base.atiende == "pasiva"
        base.escribir(_alta("v2"))
        assert base.leer(_ids) == ["v1", "v2"]
    finally:
        subprocess.run(["docker", "start", cid], check=True, capture_output=True)
        _esperar_sano(cid, bases_limpias.viajes_primaria)
