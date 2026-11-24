"""Canales de notificación y su descubrimiento (SPEC-COMP-08)."""
from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType

from trotamundos.notificaciones.canales.base import ATRIBUTO, CanalSimulado, canal


def descubrir(paquete: ModuleType | str | None = None) -> dict[str, type]:
    """Importa todos los módulos del paquete y devuelve `{nombre: clase}` de los que se anunciaron con
    `@canal`. Por defecto recorre este paquete; con otro (los tests) recorre ese."""
    if paquete is None:
        paquete = importlib.import_module(__name__)
    elif isinstance(paquete, str):
        paquete = importlib.import_module(paquete)
    encontrados: dict[str, type] = {}
    for info in pkgutil.iter_modules(paquete.__path__):
        modulo = importlib.import_module(f"{paquete.__name__}.{info.name}")
        for objeto in vars(modulo).values():
            nombre = getattr(objeto, ATRIBUTO, None) if isinstance(objeto, type) else None
            if nombre and objeto.__module__ == modulo.__name__:
                encontrados[nombre] = objeto
    return encontrados


__all__ = ["CanalSimulado", "canal", "descubrir"]
