"""Siembra datos de demo en las bases de desarrollo: cuentas, itinerario compartido y un viaje.

Uso: .venv/bin/python scripts/sembrar_demo.py
Es idempotente. Hasta que exista el alta de viajes por API (SPEC-REF-08) es la única forma de
tener un itinerario sobre el cual operar."""
from trotamundos.config import Configuracion
from trotamundos.persistencia.base_viajes import BaseViajes
from trotamundos.persistencia.repositorio_gestion import RepositorioGestion as R

base = BaseViajes.desde_config(Configuracion().bases)


def sembrar(c):
    R.agregar_membresia(c, "familia", "ana", "organizador")
    R.agregar_membresia(c, "familia", "luis", "participante")
    if R.itinerario_del_viaje(c, "viaje-familia") is None:
        R.crear_viaje(c, "viaje-familia", "ana", "familia")


base.escribir(sembrar)
print("listo: itinerario 'familia' (ana organizadora, luis participante), viaje 'viaje-familia'")
