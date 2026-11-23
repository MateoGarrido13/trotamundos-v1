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
    # PLAN-REF-02
    ("entrada/parseo_aislado", "trotamundos.config", "ADR-IT3-007: sin credenciales ni configuración"),
    ("entrada/parseo_aislado", "trotamundos.broker", "ADR-IT3-007: el Parseo no toca el broker"),
    ("entrada/parseo_aislado", "trotamundos.entrada.gestor_autorizacion", "ADR-IT3-007: sin token"),
    ("entrada/api_correo", "trotamundos.persistencia", "solo el Gestor accede a la base"),
    ("entrada/programador_sondeo", "trotamundos.persistencia", "solo el Gestor accede a la base"),
    ("entrada/consumidor_correo", "trotamundos.persistencia", "solo el Gestor accede a la base"),
    ("entrada/app", "trotamundos.orquestador", "ADR-IT3-010: nodos de entrada separados"),
    ("entrada/filtro_remitentes", "trotamundos.persistencia", "el filtro no guarda nada ni escribe la reserva"),
    ("entrada/ingesta", "trotamundos.persistencia", "la ingesta nunca escribe en la base: entrega al Orquestador"),
    ("dominio/puertos_correo", "trotamundos.config", "los puertos solo dependen del dominio"),
    ("persistencia", "trotamundos.orquestador", "la persistencia no depende de la lógica de negocio"),
    ("persistencia", "trotamundos.entrada", "la persistencia no depende de los nodos de entrada"),
    ("orquestador/api_gestion", "trotamundos.entrada", "ADR-IT3-010: el contacto es el Broker"),
    ("entrada/agencia", "trotamundos.persistencia", "el Adaptador no escribe la Base de viajes ni la lee"),
    ("entrada/agencia", "trotamundos.orquestador", "ADR-IT3-010: el contacto es el Broker"),
    ("entrada/api_agencia", "trotamundos.persistencia", "el listener no escribe la Base de viajes ni la lee"),
    ("orquestador/casos", "trotamundos.entrada", "el Orquestador solo conoce los nombres de las agencias"),
    ("dominio/agencias", "trotamundos.config", "el dominio no depende de nadie"),
    ("dominio/puertos_casos", "trotamundos.broker", "los puertos solo dependen del dominio"),
    ("analitica", "trotamundos.orquestador", "el camino analítico no llama a nodos del Orquestador"),
    ("analitica", "trotamundos.persistencia", "el camino analítico no lee la Base de viajes"),
    ("analitica", "trotamundos.entrada", "nodos propios, sin compartir con la entrada"),
    ("analitica", "trotamundos.asistente", "nodos propios"),
    ("orquestador/eventos_analiticos", "trotamundos.analitica", "el Orquestador no escribe la Base analítica"),
    ("orquestador", "trotamundos.analitica", "el Orquestador no escribe la Base analítica"),
    ("dominio/eventos", "trotamundos.config", "el dominio no depende de nadie"),
    ("asistente", "trotamundos.orquestador", "el Asistente solo conoce la interfaz interna del dominio"),
    ("asistente", "trotamundos.persistencia", "el Asistente no lee ni escribe ninguna base"),
    ("asistente", "trotamundos.entrada", "el Asistente no llama a la agencia"),
    ("asistente", "trotamundos.broker", "el Asistente no toca las colas"),
    ("asistente", "trotamundos.composicion", "solo la composición conecta al Asistente"),
    ("orquestador/fachada_asistente", "trotamundos.asistente", "el Orquestador no conoce al Asistente"),
    ("dominio/puertos_asistente", "trotamundos.config", "los puertos solo dependen del dominio"),
    ("dominio/puertos_asistente", "trotamundos.orquestador", "los puertos solo dependen del dominio"),
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


def test_parseo_aislado_solo_usa_pydantic_y_biblioteca_estandar():
    """PLAN-REF-02: esquema.py y proceso.py solo importan pydantic, stdlib y su propio paquete."""
    import sys

    permitidos = {"trotamundos.entrada.parseo_aislado"}
    for nombre in ("esquema", "proceso"):
        archivo = RAIZ / "entrada" / "parseo_aislado" / f"{nombre}.py"
        for m in _imports(archivo):
            raiz = m.split(".")[0]
            ok = raiz in sys.stdlib_module_names or raiz == "pydantic" or any(
                m == p or m.startswith(p + ".") for p in permitidos
            )
            assert ok, f"{archivo.name} importa {m}"


def test_el_modulo_de_control_de_acceso_no_se_consulta_desde_fuera_del_orquestador():
    """SPEC-REF-04: el Módulo de control de acceso está dentro del Orquestador."""
    for archivo in RAIZ.rglob("*.py"):
        relativo = archivo.relative_to(RAIZ)
        if relativo.parts[0] == "orquestador":
            continue
        malos = [m for m in _imports(archivo) if m.startswith("trotamundos.orquestador.control_acceso")]
        assert not malos, f"{relativo} importa {malos}: el control de acceso es interno al Orquestador"
