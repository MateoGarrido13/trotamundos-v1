"""Hace cumplir en el código las restricciones de frontera de las specs
(POLITICAS_SPECS_Y_PLANES §4, mapeo paquetes <-> elementos del Paso 5)."""
import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1] / "src" / "trotamundos"

# (paquete o módulo origen, prefijo prohibido, motivo)
PROHIBIDOS = [
    ("dominio", "trotamundos.orquestador", "el dominio no depende de nadie"),
    ("dominio", "trotamundos.entrada", "el dominio no depende de nadie"),
    ("dominio", "trotamundos.broker", "el dominio no depende de nadie"),
    ("dominio", "trotamundos.persistencia", "el dominio no depende de nadie"),
    ("broker", "trotamundos.orquestador", "el broker es infraestructura neutra"),
    ("broker", "trotamundos.entrada", "el broker es infraestructura neutra"),
    ("broker", "trotamundos.persistencia", "el broker es infraestructura neutra"),
    ("entrada", "trotamundos.orquestador", "ADR-IT3-010: el contacto es el Broker"),
    ("orquestador", "trotamundos.entrada", "ADR-IT3-010: el contacto es el Broker"),
    ("entrada/parseo_aislado", "trotamundos.persistencia", "ADR-IT3-007: sin acceso a la base"),
    ("entrada/adaptador_correo", "trotamundos.persistencia", "el Adaptador no escribe la Base de viajes"),
]


def _imports(archivo: Path) -> set[str]:
    arbol = ast.parse(archivo.read_text())
    mods: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            mods.update(a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            mods.add(nodo.module)
    return mods


def _archivos(origen: str) -> list[Path]:
    ruta = RAIZ / origen
    if ruta.is_dir():
        return list(ruta.rglob("*.py"))
    return [ruta.with_suffix(".py")] if ruta.with_suffix(".py").exists() else []


@pytest.mark.parametrize("origen,prohibido,motivo", PROHIBIDOS)
def test_imports_prohibidos(origen, prohibido, motivo):
    for archivo in _archivos(origen):
        malos = [m for m in _imports(archivo) if m == prohibido or m.startswith(prohibido + ".")]
        assert not malos, f"{archivo.relative_to(RAIZ)} importa {malos}: {motivo}"
