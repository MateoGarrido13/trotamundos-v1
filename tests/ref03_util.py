"""Ayudas compartidas de los tests de SPEC-REF-03."""
from datetime import UTC, datetime

from trotamundos.dominio.reserva_normalizada import ReservaNormalizada

AHORA = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


def reserva_norm(id_mensaje="<m1@x>", titular="t1", remitente="agencia@x.com", tipo="hotel",
                 lugar="Roma", codigo="H-1") -> ReservaNormalizada:
    return ReservaNormalizada(
        id_mensaje=id_mensaje, titular_id=titular, remitente=remitente, tipo=tipo,
        inicio=datetime(2026, 12, 1, 10), fin=datetime(2026, 12, 5, 10), lugar=lugar, codigo=codigo)
