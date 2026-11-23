"""Parámetros configurables del prototipo.

Los valores por defecto son los de las specs (SPEC-REF-02, «Parámetros Configurables»).
Cada uno se puede sobrescribir por variable de entorno, o pasando una `Configuracion`
explícita (los tests lo hacen para achicar colas y tiempos).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(nombre: str, defecto: str) -> str:
    return os.environ.get(nombre, defecto)


@dataclass(frozen=True)
class ConfiguracionBroker:
    # ADR-IT3-002: tamaño máximo por cola. SPEC-REF-02: 100 (5 en los tests).
    tamano_maximo_cola: int = int(_env("TROTA_COLA_MAX", "100"))
    # ADR-IT3-003: 3 reintentos con espera exponencial de 1 s, 2 s y 4 s.
    reintentos: int = int(_env("TROTA_REINTENTOS", "3"))
    backoff_base_segundos: float = float(_env("TROTA_BACKOFF_BASE", "1.0"))


@dataclass(frozen=True)
class ConfiguracionBases:
    viajes_primaria: str = _env(
        "TROTA_DSN_VIAJES_PRIMARIA",
        "postgresql://trotamundos:trotamundos@localhost:5433/viajes_primaria",
    )
    viajes_pasiva: str = _env(
        "TROTA_DSN_VIAJES_PASIVA",
        "postgresql://trotamundos:trotamundos@localhost:5434/viajes_pasiva",
    )
    # SPEC-REF-01 / ADR-IT2-005: errores de conexión consecutivos que disparan la conmutación.
    # La spec lo deja [sin especificar]; 3 es la propuesta del plan, a confirmar.
    umbral_conmutacion: int = int(_env("TROTA_UMBRAL_CONMUTACION", "3"))


@dataclass(frozen=True)
class ConfiguracionCorreo:
    # SPEC-REF-02, «Parámetros Configurables».
    frecuencia_sondeo_minutos: int = int(_env("TROTA_SONDEO_MINUTOS", "15"))
    ventana_sondeo_dias: int = int(_env("TROTA_VENTANA_DIAS", "7"))
    vigencia_token_minutos: int = int(_env("TROTA_VIGENCIA_TOKEN_MINUTOS", "60"))
    # Simplificación de la spec: la clave de cifrado de tokens sale de una variable de entorno.
    clave_tokens: str = _env("TROTA_CLAVE_TOKENS", "")


@dataclass(frozen=True)
class ConfiguracionRevision:
    # SPEC-REF-03, «Parámetros Configurables».
    retencion_dias: int = int(_env("TROTA_RETENCION_REVISION_DIAS", "30"))
    tope_pendientes: int = int(_env("TROTA_TOPE_REVISION", "50"))
    intervalo_purga_segundos: float = float(_env("TROTA_INTERVALO_PURGA", "3600"))


@dataclass(frozen=True)
class ConfiguracionIngesta:
    # Valores de SPEC-REF-02 que SPEC-REF-03 reutiliza para la ingesta.
    retencion_ids_dias: int = int(_env("TROTA_RETENCION_IDS_DIAS", "7"))
    tasa_por_segundo: float = float(_env("TROTA_TASA_INGESTA", "20"))


@dataclass(frozen=True)
class Configuracion:
    correo: ConfiguracionCorreo = field(default_factory=ConfiguracionCorreo)
    broker: ConfiguracionBroker = field(default_factory=ConfiguracionBroker)
    bases: ConfiguracionBases = field(default_factory=ConfiguracionBases)
    revision: ConfiguracionRevision = field(default_factory=ConfiguracionRevision)
    ingesta: ConfiguracionIngesta = field(default_factory=ConfiguracionIngesta)

    def __post_init__(self) -> None:
        # Ninguna retención puede ser menor que la ventana de sondeo (SPEC-REF-02/03): si lo
        # fuera, un mensaje releído en la ventana podría reaparecer o duplicarse.
        ventana = self.correo.ventana_sondeo_dias
        if self.revision.retencion_dias < ventana:
            raise ValueError(
                f"La retención de Mensajes en revisión ({self.revision.retencion_dias} días) "
                f"no puede ser menor que la ventana de sondeo ({ventana} días)")
        if self.ingesta.retencion_ids_dias < ventana:
            raise ValueError(
                f"La retención de identificadores ({self.ingesta.retencion_ids_dias} días) "
                f"no puede ser menor que la ventana de sondeo ({ventana} días)")
