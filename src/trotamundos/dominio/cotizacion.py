# SPEC: SPEC-COMP-06
# ELEMENTO PASO 5: Orquestador de viajes y adaptadores de cotización (ITERACION_2)
# ADRs: ADR-IT2-002, ADR-IT2-003, ADR-007
# DRIVERS: QA-PER-02, QA-INT-01
"""Modelo interno de la cotización: lo que los adaptadores traducen y la grilla que ve el viajero."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any


class EstadoOrigen(StrEnum):
    OK = "ok"
    NO_RESPONDIO = "no_respondio"


@dataclass(frozen=True)
class Criterios:
    """Fecha, hospedaje y compañía: lo que identifica una grilla (y su copia en la caché)."""

    fecha: date
    hospedaje: str
    compania: str

    def clave(self) -> tuple[str, str, str]:
        return (self.fecha.isoformat(), self.hospedaje, self.compania)


@dataclass(frozen=True)
class Precio:
    descripcion: str
    monto: Decimal
    moneda: str

    def a_dict(self) -> dict[str, str]:
        return {"descripcion": self.descripcion, "monto": str(self.monto), "moneda": self.moneda}


@dataclass(frozen=True)
class ResultadoOrigen:
    proveedor: str
    estado: EstadoOrigen
    precios: tuple[Precio, ...] = ()

    def a_dict(self) -> dict[str, Any]:
        return {"proveedor": self.proveedor, "estado": self.estado.value,
                "precios": [p.a_dict() for p in self.precios]}


@dataclass(frozen=True)
class Grilla:
    """`completa`: todos los orígenes respondieron. `copia`: viene de la caché. `en_curso`: ningún origen
    respondió todavía y no hay nada que mostrar (PLAN-COMP-06, D5)."""

    origenes: tuple[ResultadoOrigen, ...]
    completa: bool
    copia: bool = False
    en_curso: bool = False

    @property
    def tiene_precios(self) -> bool:
        return any(o.estado is EstadoOrigen.OK for o in self.origenes)

    def como_copia(self) -> Grilla:
        return replace(self, copia=True)

    def a_dict(self) -> dict[str, Any]:
        return {"origenes": [o.a_dict() for o in self.origenes], "completa": self.completa,
                "copia": self.copia, "en_curso": self.en_curso}


@dataclass
class ProgresoGrilla:
    """La grilla que el Orquestador va armando. La Caché de borde la lee si la cota vence antes de
    que termine (ADR-IT2-002): entrega lo que ya respondió y marca el resto como `no_respondio`."""

    _esperados: tuple[str, ...] = ()
    _recibidos: dict[str, ResultadoOrigen] = field(default_factory=dict)

    def iniciar(self, nombres: tuple[str, ...]) -> None:
        self._esperados = nombres
        self._recibidos = {}

    def reiniciar(self) -> None:
        self._recibidos = {}

    def registrar(self, resultado: ResultadoOrigen) -> None:
        self._recibidos[resultado.proveedor] = resultado

    def a_grilla(self) -> Grilla:
        nombres = list(self._esperados) + [n for n in self._recibidos if n not in self._esperados]
        origenes = tuple(
            self._recibidos.get(n) or ResultadoOrigen(n, EstadoOrigen.NO_RESPONDIO) for n in sorted(nombres))
        con_precio = sum(1 for o in origenes if o.estado is EstadoOrigen.OK)
        return Grilla(origenes=origenes, completa=bool(origenes) and con_precio == len(origenes),
                      en_curso=con_precio == 0)
