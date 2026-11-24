"""Ayudas de los tests de SPEC-COMP-05."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from trotamundos.identidad.region.regiones import ensamblar_regiones


class Reloj:
    """Reloj controlable: los vencimientos y las ventanas se prueban sin esperar."""

    def __init__(self) -> None:
        self.ahora = datetime(2026, 12, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.ahora

    def avanzar(self, **kw) -> None:
        self.ahora += timedelta(**kw)


def armar_regiones(cfg):
    publicados: list[dict] = []
    reloj = Reloj()
    servicios, red = ensamblar_regiones(cfg, publicados.append, reloj)
    return SimpleNamespace(servicios=servicios, red=red, publicados=publicados, reloj=reloj, cfg=cfg)


def token_de(publicado: dict) -> str:
    """El correo de recuperación trae el código al final del cuerpo."""
    return publicado["propuesta"]["cuerpo"].rsplit(": ", 1)[-1]
