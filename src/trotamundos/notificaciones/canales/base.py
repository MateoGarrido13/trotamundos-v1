# SPEC: SPEC-COMP-08
# ELEMENTO PASO 5: ICanal, canales simulados (ITERACION_3)
# ADRs: ADR-IT3-004
# DRIVERS: QA-INT-02, CON-02
"""Base de los canales simulados y el decorador que los registra.

Cada canal vive en su propio archivo de este paquete y se anuncia con `@canal("nombre")`: sumar un
canal es agregar un archivo, sin tocar la composición, la configuración ni a otro canal (`AC-COMP-08-02`)."""
from __future__ import annotations

import asyncio

from trotamundos.dominio.puertos_notificaciones import ErrorCanal, Propuesta

ATRIBUTO = "_nombre_de_canal"


def canal(nombre: str):
    def marcar(clase):
        setattr(clase, ATRIBUTO, nombre)
        clase.nombre = nombre
        return clase

    return marcar


class CanalSimulado:
    """API de canal simulada (`CON-02`): demora y caída inyectables, y registro de lo enviado. Sin
    credenciales ni acceso a ninguna base."""

    nombre: str = ""

    def __init__(self) -> None:
        self.enviados: list[tuple[str, Propuesta]] = []
        self.demora_segundos = 0.0
        self.caida = False
        self.llamadas = 0  # veces que se invocó `enviar`, con o sin éxito

    async def enviar(self, destinatario: str, propuesta: Propuesta) -> None:
        self.llamadas += 1
        if self.demora_segundos:
            await asyncio.sleep(self.demora_segundos)
        if self.caida:
            raise ErrorCanal(f"el canal {self.nombre} no responde")
        self.enviados.append((destinatario, propuesta))
