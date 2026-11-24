# SPEC: SPEC-COMP-05
# ELEMENTO PASO 5: Módulo de registro y autenticación en nodos propios por región (ITERACION_4)
# ADRs: ADR-IT4-001, ADR-IT4-002, ADR-IT4-003
# DRIVERS: QA-ESC-01
"""Arma las regiones: una base propia (con su pasiva), un emisor de tokens y un servicio por región."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from trotamundos.config import ConfiguracionIdentidad
from trotamundos.identidad.region.base import base_de_region
from trotamundos.identidad.region.servicio import Publicar, RedRegiones, ServicioRegion
from trotamundos.identidad.tokens import EmisorTokens


def ensamblar_regiones(cfg: ConfiguracionIdentidad, publicar: Publicar,
                       reloj: Callable[[], datetime] | None = None) -> tuple[dict[str, ServicioRegion], RedRegiones]:
    red = RedRegiones(cfg.cota_unicidad_ms, cfg.hilos_unicidad)
    servicios: dict[str, ServicioRegion] = {}
    for region in cfg.regiones:
        primaria, pasiva = cfg.dsn[region]
        emisor = EmisorTokens(region, cfg.claves_firma[region], timedelta(minutes=cfg.vida_token_acceso_minutos))
        servicios[region] = ServicioRegion(
            region, base_de_region(primaria, pasiva), emisor, cfg, red, publicar, reloj)
    red.registrar(servicios)
    return servicios, red
