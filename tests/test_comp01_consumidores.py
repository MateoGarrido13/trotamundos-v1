# SPEC: SPEC-COMP-01
import asyncio

import pytest

from trotamundos.broker import ResultadoEntrega
from trotamundos.consumidores import ConfiguracionConsumidores, Supervisor

RAPIDA = ConfiguracionConsumidores(intervalo_sondeo_cola=0.01, espera_reinicio=(0.01, 0.02), tope_reinicio=0.05)


async def _esperar(condicion, tiempo=2.0):
    for _ in range(int(tiempo / 0.01)):
        if condicion():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("no se cumplió la condición a tiempo")


async def test_AC_COMP_01_03_consumidor_se_reinicia_y_los_otros_siguen():
    llamadas = {"malo": 0, "bueno": 0}

    async def malo():
        llamadas["malo"] += 1
        if llamadas["malo"] <= 2:
            raise RuntimeError("la lectura de la cola falló")
        return ResultadoEntrega.VACIA

    async def bueno():
        llamadas["bueno"] += 1
        return ResultadoEntrega.VACIA

    s = Supervisor(RAPIDA)
    s.registrar("malo", malo)
    s.registrar("bueno", bueno)
    s.iniciar()
    await _esperar(lambda: llamadas["malo"] >= 4)
    assert s.reinicios == {"malo": 2, "bueno": 0}
    assert sorted(s.vivos) == ["bueno", "malo"]
    await s.detener()


async def test_AC_COMP_01_12_cierre_sin_tareas_colgadas():
    async def vacio():
        return ResultadoEntrega.VACIA

    s = Supervisor(RAPIDA)
    for n in ("a", "b", "c", "d", "e"):
        s.registrar(n, vacio)
    s.iniciar()
    assert len(s.vivos) == 5
    antes = {t for t in asyncio.all_tasks() if t.get_name().startswith("consumidor-")}
    await s.detener()
    assert s.vivos == []
    assert all(t.done() for t in antes)


def test_el_supervisor_no_conoce_ni_la_persistencia_ni_el_orquestador():
    """SPEC-COMP-01: `consumidores.py` solo recibe funciones; el único que conecta módulos es `app.py`."""
    import ast
    from pathlib import Path
    arbol = ast.parse((Path(__file__).parents[1] / "src/trotamundos/consumidores.py").read_text())
    importados = {n.module for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom) and n.module}
    assert not any(m.startswith(("trotamundos.persistencia", "trotamundos.orquestador", "trotamundos.entrada",
                                 "trotamundos.analitica", "trotamundos.asistente")) for m in importados)
