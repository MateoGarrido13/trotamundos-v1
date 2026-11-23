# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Parseo aislado (ITERACION_3)
# ADRs: ADR-IT3-007
# DRIVERS: QA-SEG-03*, REF-02
"""Proceso del Parseo aislado. Entrada y salida por líneas JSON (stdin/stdout).

Protocolo: al arrancar escribe {"listo": true}. Por cada línea de entrada
({id, titular_id, remitente, cuerpo}) escribe {"id", "reserva": {...} | null}.
Solo pydantic y la biblioteca estándar."""
from __future__ import annotations

import json
import sys

from trotamundos.entrada.parseo_aislado.esquema import validar


def _responder(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main() -> None:
    _responder({"listo": True})
    for linea in sys.stdin:
        if not linea.strip():
            continue
        try:
            entrada = json.loads(linea)
        except ValueError:
            _responder({"id": None, "reserva": None})
            continue
        ident = entrada.get("id") if isinstance(entrada, dict) else None
        reserva = validar(entrada) if isinstance(entrada, dict) else None
        _responder({"id": ident, "reserva": reserva})


if __name__ == "__main__":
    main()
