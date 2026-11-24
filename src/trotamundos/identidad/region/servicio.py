# SPEC: SPEC-COMP-05
# ELEMENTO PASO 5: Módulo de registro y autenticación de la región (ITERACION_4)
# ADRs: ADR-IT4-001, ADR-IT4-002, ADR-IT4-003, ADR-IT4-004, ADR-IT4-006
# DRIVERS: QA-ESC-01, QA-SEG-01
"""`IRegistroUsuario` de una región: alta con unicidad acotada, sesión, renovación y recuperación.

Toda escritura corre en las dos bases de la región (2PC), así que las operaciones reciben ya
calculados los identificadores, los tiempos y los tokens: deben dar lo mismo en las dos."""
from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import UTC, datetime, timedelta

import psycopg

from trotamundos.config import ConfiguracionIdentidad
from trotamundos.dominio.identidad import (
    CorreoYaRegistrado,
    CredencialInvalida,
    DatosInvalidos,
    Sesion,
    TokenInvalido,
    TokenRecuperacionInvalido,
)
from trotamundos.identidad import contrasenas
from trotamundos.identidad.tokens import EmisorTokens
from trotamundos.persistencia.base_viajes import BaseViajes

Publicar = Callable[[dict], None]
_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def huella_de(correo: str) -> str:
    """El correo no viaja en claro entre regiones: se consulta por su huella (ADR-IT4-003)."""
    return hashlib.sha256(correo.strip().lower().encode()).hexdigest()


def _huella_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class RedRegiones:
    """Consulta de unicidad a las otras regiones: en paralelo y con cota (ADR-IT4-003)."""

    def __init__(self, cota_ms: int, hilos: int = 32) -> None:
        self._cota = cota_ms / 1000
        self._servicios: dict[str, ServicioRegion] = {}
        self._pool = ThreadPoolExecutor(max_workers=hilos, thread_name_prefix="unicidad")

    def registrar(self, servicios: dict[str, ServicioRegion]) -> None:
        self._servicios = servicios

    def consultar(self, origen: str, huella: str) -> tuple[bool, bool]:
        """(existe en otra región, alguna región no respondió a tiempo)."""
        futuros = [self._pool.submit(s.consultar_unicidad, huella)
                   for r, s in self._servicios.items() if r != origen]
        hechos, pendientes = wait(futuros, timeout=self._cota)
        existe, sin_respuesta = False, bool(pendientes)
        for f in hechos:
            try:
                existe = existe or bool(f.result())
            except Exception:  # noqa: BLE001 - una región caída se trata como sin respuesta
                sin_respuesta = True
        for f in pendientes:
            f.cancel()
        return existe, sin_respuesta

    def cerrar(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
        for servicio in self._servicios.values():
            servicio.cerrar()


class ServicioRegion:
    def __init__(self, region: str, base: BaseViajes, emisor: EmisorTokens, cfg: ConfiguracionIdentidad,
                 red: RedRegiones, publicar: Publicar,
                 reloj: Callable[[], datetime] | None = None) -> None:
        self.region = region
        self._base = base
        self._emisor = emisor
        self._cfg = cfg
        self._red = red
        self._publicar = publicar
        self._reloj = reloj or (lambda: datetime.now(UTC))

    def ahora(self) -> datetime:
        return self._reloj()

    def cerrar(self) -> None:
        """Cierra las conexiones que reutilizan los hilos."""
        cerrar = getattr(self._base, "cerrar_conexiones", None)
        if cerrar:
            cerrar()

    # --- IRegistroUsuario ------------------------------------------------------
    def alta(self, correo: str, contrasena: str) -> Sesion:
        correo = self._validar(correo, contrasena)
        huella = huella_de(correo)
        if self.consultar_unicidad(huella):
            raise CorreoYaRegistrado(correo)
        existe_fuera, pendiente = self._red.consultar(self.region, huella)
        if existe_fuera:
            raise CorreoYaRegistrado(correo)
        cuenta_id = f"{self.region}-{uuid.uuid4().hex[:12]}"
        clave_hash = contrasenas.hashear(contrasena, self._cfg.costo_hash)
        ahora = self.ahora()
        renovacion, fila = self._nuevo_token_renovacion(cuenta_id, ahora)

        def op(conn: psycopg.Connection) -> None:
            conn.execute(
                "INSERT INTO cuenta (id, correo, huella, clave_hash, unicidad_pendiente, creada)"
                " VALUES (%s, %s, %s, %s, %s, %s)", (cuenta_id, correo, huella, clave_hash, pendiente, ahora))
            conn.execute("INSERT INTO token_renovacion (huella, cuenta_id, vence) VALUES (%s, %s, %s)", fila)

        try:
            self._base.escribir(op)
        except psycopg.errors.UniqueViolation as e:  # el mismo correo en paralelo
            raise CorreoYaRegistrado(correo) from e
        return Sesion(cuenta_id, self._emisor.emitir(cuenta_id, ahora), renovacion)

    def login(self, correo: str, contrasena: str) -> Sesion:
        huella = huella_de(correo or "")
        fila = self._base.leer(lambda c: c.execute(
            "SELECT id, clave_hash FROM cuenta WHERE huella = %s", (huella,)).fetchone())
        # Con cuenta inexistente se verifica igual contra un hash de relleno: mismo costo.
        guardado = fila[1] if fila else contrasenas.hashear("relleno", self._cfg.costo_hash)
        correcta = contrasenas.verificar(contrasena or "", guardado)
        if not fila or not correcta:
            raise CredencialInvalida()
        cuenta_id = fila[0]
        ahora = self.ahora()
        renovacion, datos = self._nuevo_token_renovacion(cuenta_id, ahora)
        self._base.escribir(lambda c: c.execute(
            "INSERT INTO token_renovacion (huella, cuenta_id, vence) VALUES (%s, %s, %s)", datos))
        return Sesion(cuenta_id, self._emisor.emitir(cuenta_id, ahora), renovacion)

    def renovar(self, token_renovacion: str) -> str:
        ahora = self.ahora()
        fila = self._base.leer(lambda c: c.execute(
            "SELECT cuenta_id FROM token_renovacion WHERE huella = %s AND NOT revocado AND vence > %s",
            (_huella_token(token_renovacion), ahora)).fetchone())
        if not fila:
            raise TokenInvalido("token de renovación revocado o vencido")
        return self._emisor.emitir(fila[0], ahora)

    def cerrar_sesion(self, token_renovacion: str) -> None:
        """Revoca los tokens de renovación de la cuenta (ADR-IT4-004)."""
        huella = _huella_token(token_renovacion)

        def op(conn: psycopg.Connection) -> None:
            conn.execute(
                "UPDATE token_renovacion SET revocado = true WHERE cuenta_id ="
                " (SELECT cuenta_id FROM token_renovacion WHERE huella = %s)", (huella,))

        self._base.escribir(op)

    # --- unicidad ---------------------------------------------------------------
    def consultar_unicidad(self, huella: str) -> bool:
        """Entre regiones: ¿existe una cuenta con esta huella de correo? (ADR-IT4-003)."""
        return self._base.leer(lambda c: c.execute(
            "SELECT 1 FROM cuenta WHERE huella = %s", (huella,)).fetchone()) is not None

    # --- recuperación (ADR-IT4-005, ADR-IT4-006) ----------------------------------
    def solicitar_recuperacion(self, correo: str) -> None:
        """Devuelve siempre lo mismo, exista o no la cuenta. Un solo pedido vigente por cuenta."""
        huella = huella_de(correo or "")
        fila = self._base.leer(lambda c: c.execute(
            "SELECT id, correo FROM cuenta WHERE huella = %s", (huella,)).fetchone())
        if not fila:
            return
        cuenta_id, correo_registrado = fila
        ahora = self.ahora()
        token = f"{self.region}.{secrets.token_urlsafe(32)}"
        vence = ahora + timedelta(minutes=self._cfg.vida_token_recuperacion_minutos)
        ventana = timedelta(minutes=self._cfg.ventana_aviso_minutos)
        cupo = self._cfg.cupo_recuperacion_por_cuenta

        def op(conn: psycopg.Connection) -> tuple[bool, bool]:
            conn.execute("DELETE FROM intento_recuperacion WHERE cuenta_id = %s AND momento <= %s",
                         (cuenta_id, ahora - ventana))
            conn.execute("INSERT INTO intento_recuperacion (cuenta_id, momento) VALUES (%s, %s)",
                         (cuenta_id, ahora))
            n = conn.execute("SELECT count(*) FROM intento_recuperacion WHERE cuenta_id = %s",
                             (cuenta_id,)).fetchone()[0]
            # Una sola fila por cuenta: solo se pisa si el pedido anterior ya se usó o venció.
            ocupado = conn.execute(
                "INSERT INTO recuperacion (cuenta_id, token_huella, vence, usado) VALUES (%s, %s, %s, false)"
                " ON CONFLICT (cuenta_id) DO UPDATE SET token_huella = EXCLUDED.token_huella,"
                " vence = EXCLUDED.vence, usado = false"
                " WHERE recuperacion.usado OR recuperacion.vence <= %s RETURNING 1",
                (cuenta_id, _huella_token(token), vence, ahora)).fetchone() is None
            avisar = False
            if n > cupo:
                avisar = conn.execute(
                    "INSERT INTO aviso_recuperacion (cuenta_id, desde) VALUES (%s, %s)"
                    " ON CONFLICT (cuenta_id) DO UPDATE SET desde = EXCLUDED.desde"
                    " WHERE aviso_recuperacion.desde <= %s RETURNING 1",
                    (cuenta_id, ahora, ahora - ventana)).fetchone() is not None
            return (not ocupado), avisar

        obtuvo, avisar = self._base.escribir(op)
        if obtuvo:
            self._publicar_aviso(correo_registrado, "Recuperación de contraseña",
                                 f"Para elegir una contraseña nueva usá este código: {token}")
        if avisar:
            self._publicar_aviso(correo_registrado, "Pedidos de recuperación de contraseña",
                                 "Recibimos varios pedidos de recuperación para tu cuenta. "
                                 "Si no fuiste vos, ignorá los correos de recuperación.")

    def completar_recuperacion(self, token: str, contrasena: str) -> None:
        if not contrasena:
            raise DatosInvalidos("contraseña vacía")
        huella = _huella_token(token or "")
        ahora = self.ahora()
        clave_hash = contrasenas.hashear(contrasena, self._cfg.costo_hash)

        def op(conn: psycopg.Connection) -> str | None:
            fila = conn.execute(
                "UPDATE recuperacion SET usado = true WHERE token_huella = %s AND NOT usado AND vence > %s"
                " RETURNING cuenta_id", (huella, ahora)).fetchone()
            if fila is None:
                return None
            conn.execute("UPDATE cuenta SET clave_hash = %s WHERE id = %s", (clave_hash, fila[0]))
            conn.execute("UPDATE token_renovacion SET revocado = true WHERE cuenta_id = %s", (fila[0],))
            return fila[0]

        if self._base.escribir(op) is None:
            raise TokenRecuperacionInvalido()

    # --- internos --------------------------------------------------------------
    def _validar(self, correo: str, contrasena: str) -> str:
        correo = (correo or "").strip()
        if not _CORREO.match(correo):
            raise DatosInvalidos("correo inválido")
        if not contrasena:
            raise DatosInvalidos("contraseña vacía")
        return correo

    def _nuevo_token_renovacion(self, cuenta_id: str, ahora: datetime) -> tuple[str, tuple]:
        token = f"{self.region}.{secrets.token_urlsafe(32)}"
        vence = ahora + timedelta(days=self._cfg.vida_token_renovacion_dias)
        return token, (_huella_token(token), cuenta_id, vence)

    def _publicar_aviso(self, correo: str, asunto: str, cuerpo: str) -> None:
        try:
            self._publicar({"id": uuid.uuid4().hex, "canal": "email", "destinatario": correo,
                            "propuesta": {"asunto": asunto, "cuerpo": cuerpo}})
        except Exception:  # noqa: BLE001 - D6: cola llena u otro fallo no rompen la operación
            import logging
            logging.getLogger(__name__).exception("no se pudo publicar la notificación de identidad")
