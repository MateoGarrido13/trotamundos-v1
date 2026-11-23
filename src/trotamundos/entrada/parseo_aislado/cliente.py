# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Parseo aislado (cliente del lado del consumidor) (ITERACION_3)
# ADRs: ADR-IT3-007
# DRIVERS: QA-SEG-03*, REF-02
"""Cliente del Parseo aislado: lanza el proceso real con un entorno vacío de credenciales
y se comunica por líneas JSON. Nunca le envía el token."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from trotamundos.dominio.reserva_normalizada import ReservaNormalizada

_SRC = Path(__file__).resolve().parents[3]  # .../src
_LIMITE_LINEA = 1024 * 1024


class ErrorParseo(Exception):
    """El proceso de parseo no arrancó, murió o respondió mal."""


class ClienteParseo:
    def __init__(self, *, timeout_arranque: float = 10.0, timeout_respuesta: float = 10.0) -> None:
        self._proc: asyncio.subprocess.Process | None = None
        self._t_arranque = timeout_arranque
        self._t_respuesta = timeout_respuesta
        self._lock = asyncio.Lock()

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc else None

    async def iniciar(self) -> None:
        if self._proc is not None and self._proc.returncode is None:
            return
        # Entorno vacío de credenciales: solo lo necesario para importar el paquete.
        entorno = {"PYTHONPATH": str(_SRC), "PYTHONUNBUFFERED": "1"}
        self._proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "trotamundos.entrada.parseo_aislado.proceso",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, env=entorno, limit=_LIMITE_LINEA,
        )
        try:
            linea = await asyncio.wait_for(self._proc.stdout.readline(), self._t_arranque)
            if json.loads(linea or b"{}").get("listo") is not True:
                raise ErrorParseo("el parseo no respondió al arrancar")
        except BaseException:
            await self.cerrar()
            raise

    async def parsear(
        self, id_mensaje: str, titular_id: str, remitente: str, cuerpo: str
    ) -> ReservaNormalizada | None:
        """La reserva normalizada, o `None` si el parseo la descartó. Lanza `ErrorParseo`
        si el proceso falla (el Broker reintenta)."""
        async with self._lock:
            await self.iniciar()
            proc = self._proc
            pedido = {"id": id_mensaje, "titular_id": titular_id, "remitente": remitente, "cuerpo": cuerpo}
            try:
                proc.stdin.write((json.dumps(pedido) + "\n").encode())
                await proc.stdin.drain()
                linea = await asyncio.wait_for(proc.stdout.readline(), self._t_respuesta)
                if not linea:
                    raise ErrorParseo("el proceso de parseo terminó")
                respuesta = json.loads(linea)
            except (OSError, ValueError, asyncio.TimeoutError, ErrorParseo) as e:
                await self.cerrar()
                raise ErrorParseo(f"fallo del parseo: {e}") from e
        if respuesta.get("reserva") is None:
            return None
        return ReservaNormalizada.model_validate(respuesta["reserva"])

    async def cerrar(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        if proc.returncode is None:
            try:
                proc.stdin.close()
            except Exception:  # noqa: BLE001
                pass
            try:
                await asyncio.wait_for(proc.wait(), 2)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
