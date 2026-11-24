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
        "postgresql://trotamundos:trotamundos@localhost:5433/trotamundos_dev",
    )
    viajes_pasiva: str = _env(
        "TROTA_DSN_VIAJES_PASIVA",
        "postgresql://trotamundos:trotamundos@localhost:5434/trotamundos_dev",
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
class ConfiguracionGestion:
    # SPEC-REF-04, «Parámetros Configurables».
    retencion_claves_dias: int = int(_env("TROTA_RETENCION_CLAVES_DIAS", "7"))


def _contactos_por_defecto() -> dict[str, str]:
    """`TROTA_AGENCIAS_CONTACTO="agencia-a=+54 11 4000-0001,agencia-b=+54 11 4000-0002"`."""
    crudo = _env("TROTA_AGENCIAS_CONTACTO", "agencia-a=+54 11 4000-0001,agencia-b=+54 11 4000-0002")
    pares = (p.split("=", 1) for p in crudo.split(",") if "=" in p)
    return {nombre.strip(): numero.strip() for nombre, numero in pares}


@dataclass(frozen=True)
class ConfiguracionAgencias:
    # SPEC-REF-05. Las agencias disponibles se registran en la configuración (simplificación),
    # cada una con su nombre y su número de contacto.
    disponibles: tuple[str, ...] = tuple(
        a.strip() for a in _env("TROTA_AGENCIAS", "agencia-a,agencia-b").split(",") if a.strip())
    contactos: dict[str, str] = field(default_factory=_contactos_por_defecto)
    # Clave compartida con la que la agencia autentica su aviso. Vacía: ningún aviso es válido.
    clave_aviso: str = _env("TROTA_CLAVE_AGENCIA", "")
    # Reintentos del Orquestador al publicar el pedido con la cola llena: 1 s, 2 s y 4 s.
    reintentos_publicacion: int = int(_env("TROTA_REINTENTOS_PUBLICACION", "3"))
    backoff_publicacion_segundos: float = float(_env("TROTA_BACKOFF_PUBLICACION", "1.0"))


@dataclass(frozen=True)
class ConfiguracionAnalitica:
    # SPEC-REF-06, «Parámetros Configurables».
    dsn: str = _env("TROTA_DSN_ANALITICA", "postgresql://trotamundos:trotamundos@localhost:5435/trotamundos_dev")
    # Tamaño máximo de la quinta cola: 1.000 eventos (5 en los tests).
    tamano_cola_eventos: int = int(_env("TROTA_COLA_EVENTOS_MAX", "1000"))
    # Reintentos de la publicación del Orquestador: 1 s, 2 s y 4 s.
    reintentos_publicacion: int = int(_env("TROTA_REINTENTOS_EVENTOS", "3"))
    backoff_publicacion_segundos: float = float(_env("TROTA_BACKOFF_EVENTOS", "1.0"))
    # Cota del informe: 10 segundos.
    cota_informe_segundos: float = float(_env("TROTA_COTA_INFORME", "10"))
    # Cuentas autorizadas del equipo de datos (simplificación de la spec: lista en la configuración).
    cuentas_datos: tuple[str, ...] = tuple(
        c.strip() for c in _env("TROTA_CUENTAS_DATOS", "analista").split(",") if c.strip())


@dataclass(frozen=True)
class ConfiguracionAsistente:
    """SPEC-REF-07, «Parámetros Configurables». No tiene credenciales de ninguna base ni de la
    API de la agencia: el Asistente solo habla con el Orquestador por su interfaz interna."""

    cota_turno_segundos: float = float(_env("TROTA_COTA_ASISTENTE", "35"))
    timeout_motor_segundos: float = float(_env("TROTA_TIMEOUT_MOTOR", "20"))
    umbral_circuito: int = int(_env("TROTA_UMBRAL_CIRCUITO", "5"))
    apertura_circuito_segundos: float = float(_env("TROTA_APERTURA_CIRCUITO", "30"))
    # Reduce proporcionalmente la cota, el time-out y la apertura del circuito, para que las pruebas
    # no esperen los valores reales. La demostración usa 1.
    escala_tiempos: float = float(_env("TROTA_ESCALA_TIEMPOS", "1"))
    vigencia_contexto_minutos: float = float(_env("TROTA_VIGENCIA_CONTEXTO", "30"))
    largo_maximo_mensaje: int = int(_env("TROTA_LARGO_MENSAJE", "500"))
    mensajes_resumen: int = int(_env("TROTA_MENSAJES_RESUMEN", "5"))
    # Simplificación de la spec: la clave que firma el contexto sale de una variable de entorno.
    clave_contexto: str = _env("TROTA_CLAVE_ASISTENTE", "")

    @property
    def cota_turno(self) -> float:
        return self.cota_turno_segundos * self.escala_tiempos

    @property
    def timeout_motor(self) -> float:
        return self.timeout_motor_segundos * self.escala_tiempos

    @property
    def apertura_circuito(self) -> float:
        return self.apertura_circuito_segundos * self.escala_tiempos


REGIONES = ("amer", "emea", "apac")
_PUERTOS_CUENTAS = {"amer": (5436, 5437), "emea": (5438, 5439), "apac": (5440, 5441)}


def _dsn_cuentas() -> dict[str, tuple[str, str]]:
    """Primaria y pasiva de cada región (SPEC-COMP-05, D1): `TROTA_DSN_CUENTAS_<REGIÓN>_<ROL>`."""
    dsn = {}
    for region, (puerto_primaria, puerto_pasiva) in _PUERTOS_CUENTAS.items():
        base = "postgresql://trotamundos:trotamundos@localhost:{}/trotamundos_dev"
        dsn[region] = (
            _env(f"TROTA_DSN_CUENTAS_{region.upper()}_PRIMARIA", base.format(puerto_primaria)),
            _env(f"TROTA_DSN_CUENTAS_{region.upper()}_PASIVA", base.format(puerto_pasiva)))
    return dsn


def _claves_firma() -> dict[str, str]:
    return {r: _env(f"TROTA_CLAVE_FIRMA_{r.upper()}", "") for r in REGIONES}


@dataclass(frozen=True)
class ConfiguracionIdentidad:
    """SPEC-COMP-05, «Parámetros Configurables»."""

    regiones: tuple[str, ...] = REGIONES
    dsn: dict[str, tuple[str, str]] = field(default_factory=_dsn_cuentas)
    # Semilla Ed25519 de cada región (hex de 32 bytes). Vacía: se genera una efímera al arrancar.
    claves_firma: dict[str, str] = field(default_factory=_claves_firma)
    # Secreto interno con el que el Gateway firma la identidad que pasa al Core (D4).
    clave_gateway: str = _env("TROTA_CLAVE_GATEWAY", "")
    vida_token_acceso_minutos: float = float(_env("TROTA_VIDA_TOKEN_ACCESO", "15"))
    vida_token_renovacion_dias: float = float(_env("TROTA_VIDA_TOKEN_RENOVACION", "7"))
    cota_unicidad_ms: int = int(_env("TROTA_COTA_UNICIDAD_MS", "300"))
    cupo_login: int = int(_env("TROTA_CUPO_LOGIN", "10"))
    cupo_recuperacion: int = int(_env("TROTA_CUPO_RECUPERACION", "3"))
    ventana_tasa_segundos: float = float(_env("TROTA_VENTANA_TASA", "60"))
    cupo_recuperacion_por_cuenta: int = int(_env("TROTA_CUPO_RECUPERACION_CUENTA", "3"))
    ventana_aviso_minutos: float = float(_env("TROTA_VENTANA_AVISO", "60"))
    vida_token_recuperacion_minutos: float = float(_env("TROTA_VIDA_TOKEN_RECUPERACION", "30"))
    # Costo de scrypt como potencia de 2 (N = 2**costo_hash). Los tests lo bajan.
    costo_hash: int = int(_env("TROTA_COSTO_HASH", "14"))
    # D5: con True el Core solo acepta identidades que firmó el Gateway. La app real lo activa.
    exigir_gateway: bool = _env("TROTA_EXIGIR_GATEWAY", "0") == "1"
    # Hilos propios de la recuperación (D10).
    hilos_recuperacion: int = int(_env("TROTA_HILOS_RECUPERACION", "4"))
    hilos_unicidad: int = int(_env("TROTA_HILOS_UNICIDAD", "32"))


@dataclass(frozen=True)
class ConfiguracionCotizacion:
    """SPEC-COMP-06, «Parámetros Configurables». Sin credenciales: la cotización no usa bases ni Broker.
    `intervalo_eco_ms` y `max_copias` son del plan (PLAN-COMP-06, D10 y D14)."""

    cota_cotizacion_ms: float = float(_env("TROTA_COTA_COTIZACION_MS", "800"))
    cota_aerolineas_ms: float = float(_env("TROTA_COTA_AEROLINEAS_MS", "600"))
    cota_hoteles_ms: float = float(_env("TROTA_COTA_HOTELES_MS", "500"))
    cota_arrendadoras_ms: float = float(_env("TROTA_COTA_ARRENDADORAS_MS", "500"))
    vigencia_copia_segundos: float = float(_env("TROTA_VIGENCIA_COPIA", "300"))
    nodos_cotizacion: int = int(_env("TROTA_NODOS_COTIZACION", "2"))
    intervalo_eco_ms: float = float(_env("TROTA_INTERVALO_ECO_MS", "1000"))
    max_copias: int = int(_env("TROTA_MAX_COPIAS", "1000"))

    @property
    def cota_cotizacion(self) -> float:
        return self.cota_cotizacion_ms / 1000

    @property
    def intervalo_eco(self) -> float:
        return self.intervalo_eco_ms / 1000


@dataclass(frozen=True)
class ConfiguracionGmail:
    """SPEC-COMP-04, «Parámetros Configurables». Las credenciales salen del entorno y nunca se escriben
    en un log ni en la base (regla 7). Las URL de Google son configurables para apuntar al simulado."""

    client_id: str = _env("TROTA_GMAIL_CLIENT_ID", "")
    client_secret: str = field(default=_env("TROTA_GMAIL_CLIENT_SECRET", ""), repr=False)
    redireccion_oauth: str = _env("TROTA_GMAIL_REDIRECCION", "http://localhost:8000/correo/oauth/callback")
    max_mensajes_por_sondeo: int = int(_env("TROTA_GMAIL_MAX_MENSAJES", "100"))
    cota_llamada_gmail_segundos: float = float(_env("TROTA_GMAIL_COTA", "10"))
    # PLAN-COMP-04, D4: cuánto vale el `state` de un solo uso.
    vigencia_state_segundos: float = float(_env("TROTA_GMAIL_VIGENCIA_STATE", "600"))
    url_autorizacion: str = _env("TROTA_GMAIL_URL_AUTORIZACION", "https://accounts.google.com/o/oauth2/v2/auth")
    url_token: str = _env("TROTA_GMAIL_URL_TOKEN", "https://oauth2.googleapis.com/token")
    url_revocacion: str = _env("TROTA_GMAIL_URL_REVOCACION", "https://oauth2.googleapis.com/revoke")
    url_api: str = _env("TROTA_GMAIL_URL_API", "https://gmail.googleapis.com/gmail/v1")

    @property
    def habilitado(self) -> bool:
        """Sin las dos credenciales la app usa el correo simulado (regla 8)."""
        return bool(self.client_id and self.client_secret)


@dataclass(frozen=True)
class ConfiguracionNotificaciones:
    """SPEC-COMP-08, «Parámetros Configurables». `canales` en `None` son todos los que descubre el
    paquete de canales (un archivo por canal): sumar uno no cambia la configuración (`AC-COMP-08-02`)."""

    canales: tuple[str, ...] | None = (
        tuple(c.strip() for c in _env("TROTA_CANALES", "").split(",") if c.strip()) or None)
    tamano_cola_notificaciones: int = int(_env("TROTA_COLA_NOTIFICACIONES_MAX", "100"))
    # Reintentos del publicador del Orquestador con la cola llena: 1 s, 2 s y 4 s.
    reintentos_publicacion: int = int(_env("TROTA_REINTENTOS_NOTIFICACIONES", "3"))
    backoff_publicacion_segundos: float = float(_env("TROTA_BACKOFF_NOTIFICACIONES", "1.0"))


@dataclass(frozen=True)
class Configuracion:
    correo: ConfiguracionCorreo = field(default_factory=ConfiguracionCorreo)
    broker: ConfiguracionBroker = field(default_factory=ConfiguracionBroker)
    bases: ConfiguracionBases = field(default_factory=ConfiguracionBases)
    revision: ConfiguracionRevision = field(default_factory=ConfiguracionRevision)
    ingesta: ConfiguracionIngesta = field(default_factory=ConfiguracionIngesta)
    gestion: ConfiguracionGestion = field(default_factory=ConfiguracionGestion)
    agencias: ConfiguracionAgencias = field(default_factory=ConfiguracionAgencias)
    analitica: ConfiguracionAnalitica = field(default_factory=ConfiguracionAnalitica)
    asistente: ConfiguracionAsistente = field(default_factory=ConfiguracionAsistente)
    notificaciones: ConfiguracionNotificaciones = field(default_factory=ConfiguracionNotificaciones)
    cotizacion: ConfiguracionCotizacion = field(default_factory=ConfiguracionCotizacion)
    gmail: ConfiguracionGmail = field(default_factory=ConfiguracionGmail)
    identidad: ConfiguracionIdentidad = field(default_factory=ConfiguracionIdentidad)

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
