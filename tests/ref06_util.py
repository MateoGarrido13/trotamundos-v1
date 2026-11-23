"""Ayudas compartidas de los tests de SPEC-REF-06."""
from datetime import UTC, datetime

from trotamundos.analitica.base import conectar
from trotamundos.dominio.eventos import EventoAnalitico
from trotamundos.analitica.proyector import Proyector


def evento(id_, tipo="alta", destino="Roma", tipo_reserva="hotel", dia=(2026, 11, 23)):
    return EventoAnalitico(id=id_, tipo=tipo, tipo_reserva=tipo_reserva, destino=destino, origen="manual",
                           estado="confirmada", ocurrido_en=datetime(*dia, 12, 0, tzinfo=UTC))


def sembrar(cfg, *eventos):
    """Proyecta eventos directamente en la Base analítica (como lo haría el Proyector)."""
    p = Proyector(None, cfg.dsn)
    try:
        for e in eventos:
            p.proyectar(e)
    finally:
        p.cerrar()
