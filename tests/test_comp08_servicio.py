# SPEC: SPEC-COMP-08 | PLAN-COMP-08 T-COMP-08-03
from tests.comp08_util import armar, publicar
from trotamundos.broker import NombreCola, ResultadoEntrega
from trotamundos.dominio.puertos_notificaciones import Propuesta

COLA = NombreCola.NOTIFICACIONES


async def test_AC_COMP_08_01_un_pedido_por_email_invoca_enviar_una_vez():
    e = armar()
    publicar(e.broker, identificador="n1", canal="email", destinatario="ana@mail.com", asunto="Asunto", cuerpo="Cuerpo")
    assert await e.servicio.procesar_canal("email") is ResultadoEntrega.ENTREGADO
    assert e.canales["email"].llamadas == 1
    assert e.canales["email"].enviados == [("ana@mail.com", Propuesta("Asunto", "Cuerpo"))]  # el contenido, intacto
    assert await e.servicio.procesar_canal("email") is ResultadoEntrega.VACIA


async def test_AC_COMP_08_03_un_pedido_por_instagram_no_toca_email_ni_whatsapp():
    e = armar()
    publicar(e.broker, identificador="n1", canal="instagram", destinatario="@ana")
    # El consumidor de Email no ve el pedido de Instagram.
    assert await e.servicio.procesar_canal("email") is ResultadoEntrega.VACIA
    assert await e.servicio.procesar_canal("whatsapp") is ResultadoEntrega.VACIA
    assert await e.servicio.procesar_canal("instagram") is ResultadoEntrega.ENTREGADO
    assert {n: c.llamadas for n, c in e.canales.items()} == {"email": 0, "whatsapp": 0, "instagram": 1}
    assert e.canales["instagram"].enviados[0][0] == "@ana"


async def test_cada_canal_toma_solo_lo_suyo_aunque_lleguen_mezclados():
    e = armar()
    for i, canal in enumerate(("email", "instagram", "whatsapp", "email")):
        publicar(e.broker, identificador=f"n{i}", canal=canal)
    for nombre in ("whatsapp", "instagram", "email", "email"):
        assert await e.servicio.procesar_canal(nombre) is ResultadoEntrega.ENTREGADO
    assert {n: len(c.enviados) for n, c in e.canales.items()} == {"email": 2, "whatsapp": 1, "instagram": 1}
    assert e.broker.tamano_actual(COLA) == 0


async def test_AC_COMP_08_06_el_mismo_pedido_dos_veces_se_envia_una_sola_vez():
    e = armar()
    publicar(e.broker, identificador="n1")
    publicar(e.broker, identificador="n1")  # el Broker lo entrega dos veces
    await e.servicio.procesar_canal("email")
    await e.servicio.procesar_canal("email")
    assert e.canales["email"].llamadas == 1 and len(e.canales["email"].enviados) == 1
    assert e.broker.mensajes_muertos(COLA) == []


async def test_un_envio_que_fallo_no_se_marca_como_enviado_y_el_reintento_lo_entrega():
    e = armar()
    publicar(e.broker, identificador="n1")
    e.canales["email"].caida = True

    async def volver_a_la_vida(_segundos):
        e.canales["email"].caida = False

    e.broker._dormir = volver_a_la_vida  # tras la primera falla el canal se recupera
    assert await e.servicio.procesar_canal("email") is ResultadoEntrega.ENTREGADO
    assert e.canales["email"].llamadas == 2 and len(e.canales["email"].enviados) == 1


async def test_AC_COMP_08_08_canal_no_registrado_va_a_muertos_con_aviso():
    e = armar()
    publicar(e.broker, identificador="n1", canal="telegram")
    publicar(e.broker, identificador="n2", canal="email")
    assert await e.servicio.procesar_sin_canal() is ResultadoEntrega.ENTREGADO  # lo saca de la cola
    assert [m.id for m in e.broker.mensajes_muertos(COLA)] == ["n1"]
    assert [(a.tipo, a.id_mensaje) for a in e.avisos] == [("mensaje_muerto", "n1")]
    assert e.esperas == []  # sin reintentos: no tiene sentido reintentar un canal que no existe
    assert await e.servicio.procesar_sin_canal() is ResultadoEntrega.VACIA  # el de Email no es suyo
    assert e.broker.tamano_actual(COLA) == 1


async def test_un_pedido_sin_canal_o_mal_formado_va_a_muertos():
    e = armar()
    for m in ({"id": "n1", "destinatario": "a"}, "no es un diccionario"):
        from trotamundos.broker import Mensaje

        e.broker.publicar(COLA, Mensaje("x" + str(len(str(m))), m))
    await e.servicio.procesar_sin_canal()
    await e.servicio.procesar_sin_canal()
    assert len(e.broker.mensajes_muertos(COLA)) == 2
    # Con canal pero sin destinatario o propuesta: no se reintenta, va a muertos.
    e.broker.publicar(COLA, Mensaje("n9", {"canal": "email", "id": "n9"}))
    assert await e.servicio.procesar_canal("email") is ResultadoEntrega.ENTREGADO
    assert e.canales["email"].llamadas == 0 and len(e.broker.mensajes_muertos(COLA)) == 3


def test_hay_un_consumidor_por_canal_y_uno_para_los_pedidos_sin_canal():
    e = armar()
    assert set(e.servicio.consumidores()) == {
        "notificaciones:email", "notificaciones:whatsapp", "notificaciones:instagram", "notificaciones:sin_canal"}
