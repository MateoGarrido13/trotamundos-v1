"""Siembra datos de prueba por la API real (con la app corriendo): cuentas, itinerarios, viajes y reservas.

Uso: .venv/bin/python scripts/sembrar_datos.py [URL]      (por defecto http://127.0.0.1:8000)
Es idempotente: las cuentas se reusan (login) y las operaciones llevan claves fijas, así que correrlo
dos veces no duplica nada. Todas las cuentas tienen la contraseña `demo1234`.

Cuentas (región amer):  ana@demo.com (organizadora), luis@demo.com, sofia@demo.com
Itinerarios:
  - Familia (ana organiza; luis y sofia participan): «Verano en Europa» y «Fin de semana en Bariloche»
  - Solo de ana: «Escapada a Lisboa»
"""
import sys

import httpx

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
CLAVE = "demo1234"
REGION = "amer"
http = httpx.Client(base_url=URL, timeout=30)


def sesion(correo: str) -> dict:
    cuerpo = {"correo": correo, "contrasena": CLAVE, "region": REGION}
    r = http.post("/auth/alta", json=cuerpo)
    if r.status_code == 409:
        r = http.post("/auth/login", json=cuerpo)
    r.raise_for_status()
    s = r.json()
    return {"id": s["cuenta_id"], "h": {"Authorization": f"Bearer {s['token_acceso']}"}}


def post(usuario: dict, ruta: str, clave: str, cuerpo: dict) -> dict:
    r = http.post(ruta, json=cuerpo, headers={**usuario["h"], "X-Clave-Operacion": f"seed-{clave}"})
    r.raise_for_status()
    return r.json()


def viaje(usuario, clave, nombre, itinerario=None) -> dict:
    return post(usuario, "/viajes", f"viaje-{clave}", {"nombre": nombre, "itinerario_id": itinerario})


def reserva(usuario, itinerario, viaje_id, clave, tipo, inicio, fin, lugar, codigo):
    post(usuario, f"/itinerarios/{itinerario}/reservas", f"res-{clave}", {
        "viaje_id": viaje_id, "tipo": tipo, "inicio": inicio, "fin": fin, "lugar": lugar,
        "datos": {"codigo": codigo}})


ana, luis, sofia = (sesion(f"{n}@demo.com") for n in ("ana", "luis", "sofia"))

europa = viaje(ana, "europa", "Verano en Europa")
familia = europa["itinerario_id"]
for cuenta, rol in ((luis, "participante"), (sofia, "participante")):
    post(ana, f"/itinerarios/{familia}/miembros", f"miembro-{cuenta['id']}", {"cuenta": cuenta["id"], "rol": rol})
bariloche = viaje(ana, "bariloche", "Fin de semana en Bariloche", familia)
lisboa = viaje(ana, "lisboa", "Escapada a Lisboa")

E, B, L = europa["viaje_id"], bariloche["viaje_id"], lisboa["viaje_id"]
roma = {"nombre": "Hotel Roma Centro", "destino": "Roma", "latitud": 41.9028, "longitud": 12.4964}
madrid = {"nombre": "Madrid", "destino": "Madrid", "latitud": 40.4168, "longitud": -3.7038}
paris = {"nombre": "Hotel Le Marais", "destino": "París", "latitud": 48.8566, "longitud": 2.3522}
bar = {"nombre": "Hotel Llao Llao", "destino": "Bariloche", "latitud": -41.0536, "longitud": -71.5311}

# Europa: vuelo ida, tren, hoteles, auto, actividad, vuelo vuelta (reservas de distintos miembros)
reserva(ana, familia, E, "e-vuelo-ida", "vuelo", "2027-01-10T22:00:00Z", "2027-01-11T14:00:00Z", madrid, "AR1132")
reserva(ana, familia, E, "e-hotel-roma", "hotel", "2027-01-12T14:00:00Z", "2027-01-16T10:00:00Z", roma, "HRC-88231")
reserva(luis, familia, E, "e-tren", "tren", "2027-01-12T08:30:00Z", "2027-01-12T12:45:00Z", "Madrid → Roma", "TR-5521")
reserva(luis, familia, E, "e-auto", "auto", "2027-01-16T11:00:00Z", "2027-01-20T11:00:00Z", "Roma", "AU-77310")
reserva(sofia, familia, E, "e-actividad", "actividad", "2027-01-14T10:00:00Z", "2027-01-14T13:00:00Z",
        {"nombre": "Coliseo", "destino": "Roma", "latitud": 41.8902, "longitud": 12.4922}, "TOUR-12")
reserva(ana, familia, E, "e-hotel-paris", "hotel", "2027-01-20T15:00:00Z", "2027-01-24T10:00:00Z", paris, "HLM-40912")
reserva(ana, familia, E, "e-vuelo-vuelta", "vuelo", "2027-01-24T18:00:00Z", "2027-01-25T07:00:00Z", "París", "AR1133")
# Bariloche (mismo itinerario, otro viaje)
reserva(ana, familia, B, "b-vuelo", "vuelo", "2027-03-05T09:00:00Z", "2027-03-05T11:10:00Z", "Bariloche", "AR1704")
reserva(ana, familia, B, "b-hotel", "hotel", "2027-03-05T14:00:00Z", "2027-03-08T10:00:00Z", bar, "HLL-3321")
reserva(luis, familia, B, "b-bus", "autobus", "2027-03-06T09:00:00Z", "2027-03-06T11:00:00Z", "Circuito Chico", "BUS-910")
# Lisboa (solo ana)
reserva(ana, lisboa["itinerario_id"], L, "l-vuelo", "vuelo", "2027-05-02T21:00:00Z", "2027-05-03T10:30:00Z", "Lisboa", "TP0102")
reserva(ana, lisboa["itinerario_id"], L, "l-hotel", "hotel", "2027-05-03T15:00:00Z", "2027-05-06T11:00:00Z",
        {"nombre": "Hotel Alfama", "destino": "Lisboa", "latitud": 38.7139, "longitud": -9.1334}, "HAL-5520")

print(f"""listo. Entrá en {URL}/web/ (o /movil/) con región {REGION} y contraseña {CLAVE}:
  ana@demo.com   organizadora: Verano en Europa, Fin de semana en Bariloche, Escapada a Lisboa
  luis@demo.com  participante en el itinerario familiar
  sofia@demo.com participante en el itinerario familiar""")
