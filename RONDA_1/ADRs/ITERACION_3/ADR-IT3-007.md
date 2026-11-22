# Seguridad: Validate input + Separate entities (Parseo aislado)

* **Estado:** aceptado
* **Fecha:** 2026-10-28
* **Decisores:** Yaco Recroa

## Contexto y Declaración del Problema
El contenido de un mensaje de correo es entrada no confiable: puede estar mal formado o ser malicioso. Hay que extraer de él la reserva sin exponer al resto del sistema (en particular la base de datos) si el contenido es hostil o el parser falla.

## Impulsores de la Decisión (Decision Drivers)
* `REF-02`: extraer y normalizar reservas desde mensajes de viaje.
* `QA-SEG-03*`: acceso seguro a los datos del correo del titular.
* Reducir la superficie de ataque del contenido externo.

## Opciones Consideradas
* Opción 1: Parseo aislado: proceso separado, sin acceso a la base, que valida, extrae y normaliza.
* Opción 2: Parsear dentro del Adaptador de correo.
* Opción 3: Parsear dentro del Orquestador de viajes o del Servicio de ingesta.

## Resultado de la Decisión
Opción elegida: **"Opción 1: Parseo aislado en un proceso separado y sin acceso a la base"**, porque contiene el daño: un mensaje hostil solo alcanza a un proceso que no puede leer ni escribir datos. Lo que no valida se descarta; lo válido se entrega normalizado al Filtro de remitentes.

### Consecuencias Positivas (Beneficios)
* Un fallo o ataque a través del contenido de un correo queda confinado.
* Separa responsabilidades: leer el buzón, parsear y persistir son piezas distintas.
* Un único punto donde se valida la entrada del correo.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Un componente más para desplegar, monitorear y escalar, y un salto adicional por el broker.
* Descartar lo que no valida puede perder una reserva legítima con un formato inesperado; conviene registrar las causas de descarte.
* La extracción por formatos de correo es frágil y exige mantenimiento a medida que los proveedores cambian sus plantillas.
