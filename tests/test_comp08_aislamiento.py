# SPEC: SPEC-COMP-08 | PLAN-COMP-08 T-COMP-08-04
import asyncio

from tests.comp08_util import armar, drenar, publicar
from trotamundos.broker import NombreCola

COLA = NombreCola.NOTIFICACIONES


async def _latencia_de_email(instagram, *, con_pedidos_de_instagram: bool, escala_espera=0.0) -> tuple[float, float]:
    """(lo que tarda Email, lo que tarda Instagram) cuando los dos consumidores corren a la vez."""
    e = armar(escala_espera=escala_espera)
    instagram(e.canales["instagram"])
    for i in range(3):
        publicar(e.broker, identificador=f"e{i}", canal="email")
        if con_pedidos_de_instagram:
            publicar(e.broker, identificador=f"i{i}", canal="instagram")
    email, ig = await asyncio.gather(drenar(e.servicio, "email"), drenar(e.servicio, "instagram"))
    assert len(e.canales["email"].enviados) == 3
    return email, ig


async def test_AC_COMP_08_04_instagram_caido_no_atrasa_a_email():
    def caido(canal):
        canal.caida = True

    # 0,05 de la espera real: Instagram pasa 0,35 s reintentando cada pedido.
    base, _ = await _latencia_de_email(lambda c: None, con_pedidos_de_instagram=False)
    con_caida, instagram = await _latencia_de_email(caido, con_pedidos_de_instagram=True, escala_espera=0.05)
    assert con_caida - base < 0.1  # Email sale sin demora adicional
    assert instagram > 0.5 and instagram > 5 * con_caida  # mientras Instagram sigue reintentando


async def test_AC_COMP_08_04_los_pedidos_de_instagram_se_reintentan_con_el_mismo_identificador():
    e = armar()
    publicar(e.broker, identificador="i1", canal="instagram")
    e.canales["instagram"].caida = True
    llamadas = []

    async def volver(segundos):
        llamadas.append(segundos)
        if len(llamadas) == 2:
            e.canales["instagram"].caida = False

    e.broker._dormir = volver
    await drenar(e.servicio, "instagram")
    assert llamadas == [1.0, 2.0] and e.canales["instagram"].llamadas == 3
    assert len(e.canales["instagram"].enviados) == 1 and e.broker.mensajes_muertos(COLA) == []


async def test_AC_COMP_08_05_agotados_los_reintentos_va_a_muertos_con_aviso():
    e = armar()
    e.canales["instagram"].caida = True
    publicar(e.broker, identificador="i1", canal="instagram")
    publicar(e.broker, identificador="e1", canal="email")
    await drenar(e.servicio, "instagram")
    await drenar(e.servicio, "email")
    assert e.esperas == [1.0, 2.0, 4.0]  # los tres reintentos con 1, 2 y 4 s
    assert e.canales["instagram"].llamadas == 4  # el intento inicial y tres reintentos
    assert [m.id for m in e.broker.mensajes_muertos(COLA)] == ["i1"]
    assert [(a.tipo, a.id_mensaje) for a in e.avisos] == [("mensaje_muerto", "i1")]
    assert len(e.canales["email"].enviados) == 1  # y lo de Email no se perdió


async def test_AC_COMP_08_10_un_canal_con_demora_no_cambia_la_latencia_de_los_otros():
    def lento(canal):
        canal.demora_segundos = 2.0

    base, _ = await _latencia_de_email(lambda c: None, con_pedidos_de_instagram=False)
    con_demora, instagram = await _latencia_de_email(lento, con_pedidos_de_instagram=True)
    assert abs(con_demora - base) < 0.1
    assert instagram >= 6.0  # tres envíos de 2 s en su propio consumidor
