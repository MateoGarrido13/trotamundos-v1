# SPEC: SPEC-COMP-07
# ELEMENTO PASO 5: Orquestador de viajes, anuncios de Booking (ITERACION_3)
# ADRs: ADR-IT3-003
# DRIVERS: QA-PER-01
"""SQL de la tabla `anuncio`. Cada función recibe la conexión de una transacción ya abierta por
`BaseViajes.escribir` (o de una lectura)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import psycopg

from trotamundos.dominio.puertos_anuncios import Anuncio


@dataclass(frozen=True)
class FilaAnuncio:
    id: str
    titulo: str
    destino: str
    inicio: date
    fin: date
    proveedor: str
    detectado_en: datetime
    recibido_en: datetime


class RepositorioAnuncios:
    @staticmethod
    def insertar(c: psycopg.Connection, a: Anuncio, recibido_en: datetime) -> bool:
        """Idempotente: un anuncio que ya está no se guarda otra vez. `True` si era nuevo."""
        return c.execute(
            "INSERT INTO anuncio (id, titulo, destino, inicio, fin, proveedor, detectado_en, recibido_en)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (a.id, a.titulo, a.destino, a.inicio, a.fin, a.proveedor, a.detectado_en, recibido_en)
        ).rowcount > 0

    @staticmethod
    def recientes(c: psycopg.Connection, desde: datetime, tope: int) -> list[FilaAnuncio]:
        filas = c.execute(
            "SELECT id, titulo, destino, inicio, fin, proveedor, detectado_en, recibido_en FROM anuncio"
            " WHERE recibido_en >= %s ORDER BY recibido_en DESC, id LIMIT %s", (desde, tope)).fetchall()
        return [FilaAnuncio(*f) for f in filas]
