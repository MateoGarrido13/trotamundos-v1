# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Gestor de autorización del correo (ITERACION_3)
# ADRs: ADR-IT3-006
# DRIVERS: QA-SEG-03*, REF-02
"""Gestor de autorización: consentimiento, tokens cifrados con vencimiento y revocación.

Un token vencido cuenta como no vigente y no se renueva solo (regla 6)."""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from trotamundos.config import ConfiguracionCorreo
from trotamundos.entrada.gestor_autorizacion.cifrado import CifradorTokens
from trotamundos.entrada.gestor_autorizacion.repositorio import RepositorioTokens, TokenGuardado


def _ahora_utc() -> datetime:
    return datetime.now(UTC)


class GestorAutorizacion:
    def __init__(
        self,
        repositorio: RepositorioTokens,
        cifrador: CifradorTokens,
        configuracion: ConfiguracionCorreo | None = None,
        *,
        reloj: Callable[[], datetime] = _ahora_utc,
    ) -> None:
        self._repo = repositorio
        self._cifrador = cifrador
        self._cfg = configuracion or ConfiguracionCorreo()
        self._reloj = reloj

    def autorizar(self, titular_id: str, token: str) -> datetime:
        """Guarda el token cifrado con su vencimiento. Devuelve el vencimiento."""
        vence = self._reloj() + timedelta(minutes=self._cfg.vigencia_token_minutos)
        self._repo.guardar(TokenGuardado(titular_id, self._cifrador.cifrar(token), vence))
        return vence

    def revocar(self, titular_id: str) -> None:
        """Borra el token. Sin token no hay lectura. No toca reservas ya incorporadas."""
        self._repo.borrar(titular_id)

    def token_vigente(self, titular_id: str, ahora: datetime | None = None) -> str | None:
        """El token en claro, o `None` si no hay, fue revocado o venció."""
        guardado = self._repo.obtener(titular_id)
        if guardado is None:
            return None
        if (ahora or self._reloj()) >= guardado.vence:
            return None
        return self._cifrador.descifrar(guardado.token_cifrado)

    def titulares_autorizados(self) -> list[str]:
        """Titulares con token guardado (vigente o no; el Adaptador comprueba la vigencia)."""
        return self._repo.titulares()
