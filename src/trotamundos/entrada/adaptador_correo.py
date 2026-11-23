# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Adaptador de correo (ITERACION_3)
# ADRs: ADR-IT3-001, ADR-IT3-002, ADR-IT3-003, ADR-IT3-006
# DRIVERS: QA-SEG-03*, CON-02, REF-02
"""Adaptador de correo (capa anti-corrupción de la API de correo).

Sondeo sin estado (regla 2): lee la ventana completa y publica todo, con su identificador.
No importa `persistencia`: no escribe la Base de viajes."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from trotamundos.broker import Broker, ColaLlena, Mensaje, NombreCola
from trotamundos.config import ConfiguracionCorreo
from trotamundos.entrada.api_correo import ApiCorreo, CorreoCrudo
from trotamundos.entrada.gestor_autorizacion import GestorAutorizacion


@dataclass(frozen=True)
class ResultadoSondeo:
    leyo: bool  # False: no había token vigente y no se leyó
    publicados: int = 0
    cola_llena: bool = False


def identificador_de(correo: CorreoCrudo) -> str:
    """`Message-ID`; si falta, SHA-256 del contenido crudo (ADR-IT3-003)."""
    if correo.message_id:
        return correo.message_id
    return hashlib.sha256(correo.cuerpo.encode()).hexdigest()


class AdaptadorCorreo:
    def __init__(
        self,
        api: ApiCorreo,
        gestor: GestorAutorizacion,
        broker: Broker,
        configuracion: ConfiguracionCorreo | None = None,
    ) -> None:
        self._api = api
        self._gestor = gestor
        self._broker = broker
        self._cfg = configuracion or ConfiguracionCorreo()

    async def sondear(self, titular_id: str, ahora: datetime | None = None) -> ResultadoSondeo:
        """Sondea el buzón. `ErrorApiCorreo` se propaga: falla solo este sondeo."""
        ahora = ahora or datetime.now(UTC)
        token = self._gestor.token_vigente(titular_id, ahora)
        if token is None:
            return ResultadoSondeo(leyo=False)
        desde = ahora - timedelta(days=self._cfg.ventana_sondeo_dias)
        correos = await self._api.leer_mensajes(token, desde)
        publicados = 0
        for correo in correos:
            mensaje = Mensaje(
                identificador_de(correo),
                {"titular_id": titular_id, "remitente": correo.remitente, "cuerpo": correo.cuerpo},
            )
            try:
                self._broker.publicar(NombreCola.CORREO, mensaje)
            except ColaLlena:
                # No publica y no pierde: sin estado, el sondeo siguiente vuelve a leer la ventana.
                return ResultadoSondeo(leyo=True, publicados=publicados, cola_llena=True)
            publicados += 1
        return ResultadoSondeo(leyo=True, publicados=publicados)
