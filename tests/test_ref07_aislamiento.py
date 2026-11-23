# SPEC: SPEC-REF-07
# ELEMENTO PASO 5: Módulo de Asistente Virtual, nodos propios y sin estado (RONDA_2/ITERACION_1)
# ADRs: ADR-IT6-001
# DRIVERS: REF-07
"""T-REF-07-08: el módulo no tiene credenciales de ninguna base ni de la agencia, y no guarda estado."""
import ast
from dataclasses import fields
from pathlib import Path

import pytest

import trotamundos.asistente as paquete
from tests.ref07_util import CFG, OrquestadorDeMemoria, confirmar
from trotamundos.asistente.asistente import ModuloAsistente
from trotamundos.asistente.motor import MotorSimulado
from trotamundos.config import ConfiguracionAsistente

RAIZ = Path(paquete.__file__).parent
PROHIBIDOS = ("trotamundos.persistencia", "trotamundos.orquestador", "trotamundos.entrada", "trotamundos.broker",
              "trotamundos.analitica", "trotamundos.composicion", "trotamundos.app", "psycopg")


def imports(archivo: Path) -> set[str]:
    mods: set[str] = set()
    for nodo in ast.walk(ast.parse(archivo.read_text())):
        if isinstance(nodo, ast.Import):
            mods.update(a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            mods.add(nodo.module)
    return mods


def test_AC_REF_07_21_el_modulo_no_tiene_credenciales_de_base_ni_de_agencia():
    campos = {f.name for f in fields(ConfiguracionAsistente)}
    assert not {c for c in campos if any(p in c for p in ("dsn", "base", "agencia", "token", "password", "viajes"))}
    assert campos == {"cota_turno_segundos", "timeout_motor_segundos", "umbral_circuito", "apertura_circuito_segundos",
                      "escala_tiempos", "vigencia_contexto_minutos", "largo_maximo_mensaje", "mensajes_resumen",
                      "clave_contexto"}


def test_AC_REF_07_21_ningun_archivo_del_modulo_importa_una_base_ni_al_orquestador_ni_a_la_agencia():
    for archivo in RAIZ.rglob("*.py"):
        malos = [m for m in imports(archivo) if any(m == p or m.startswith(p + ".") for p in PROHIBIDOS)]
        assert not malos, f"{archivo.name} importa {malos}"


async def test_AC_REF_07_21_no_guarda_estado_entre_turnos():
    orq = OrquestadorDeMemoria()
    modulo = ModuloAsistente(MotorSimulado(), orq, CFG)
    atributos = set(vars(modulo))
    # Dos conversaciones intercaladas, con contextos distintos: no se contaminan.
    a = await modulo.turno("luis", "familia", "Quiero eliminar mi vuelo a Lima", None)
    b = await modulo.turno("ana", "familia", "Quiero eliminar mi hotel de Roma", None)
    for _ in range(30):
        await modulo.turno(f"viajero-{_}", "familia", "¿cómo está mi reserva?", None)
    assert set(vars(modulo)) == atributos  # no apareció ningún atributo por conversación
    assert [vars(modulo)[k] for k in vars(modulo) if isinstance(vars(modulo)[k], (dict, list, set))] == []
    await confirmar(modulo, b, "ana")
    await confirmar(modulo, a, "luis")
    assert [(e[2], e[4]) for e in orq.escrituras] == [("ana", "res-1"), ("luis", "res-2")]  # cada uno, lo suyo


async def test_dos_instancias_del_modulo_atienden_la_misma_conversacion():
    """Sin estado: la acción pendiente viaja con el cliente, no vive en un nodo."""
    orq = OrquestadorDeMemoria()
    nodo_1, nodo_2 = (ModuloAsistente(MotorSimulado(), orq, CFG) for _ in range(2))
    p = await nodo_1.turno("luis", "familia", "Quiero eliminar mi vuelo a Lima", None)
    r = await confirmar(nodo_2, p)  # otro nodo, con la misma clave de firma
    assert r.tipo == "resultado" and len(orq.escrituras) == 1


async def test_un_nodo_con_otra_clave_no_acepta_el_contexto():
    orq = OrquestadorDeMemoria()
    a = ModuloAsistente(MotorSimulado(), orq, CFG)
    b = ModuloAsistente(MotorSimulado(), orq, ConfiguracionAsistente(clave_contexto="otra-clave", escala_tiempos=0.02))
    p = await a.turno("luis", "familia", "Quiero eliminar mi vuelo a Lima", None)
    assert (await confirmar(b, p)).motivo == "sin_accion_pendiente" and orq.escrituras == []
