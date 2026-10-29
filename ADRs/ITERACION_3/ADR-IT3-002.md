# Performance: Bound queue sizes (colas acotadas)

* **Estado:** aceptado
* **Fecha:** 2026-10-28
* **Decisores:** Yaco Recroa

## Contexto y Declaración del Problema
Con el broker de [ADR-IT3-001](ADR-IT3-001.md), un pico de novedades, de correo o de envíos puede llenar las colas más rápido de lo que los consumidores las vacían. Una cola que crece sin límite agota memoria o disco del broker y retrasa todos los mensajes que vienen detrás, comprometiendo el tiempo de actualización. Hay que decidir qué pasa cuando una cola alcanza su capacidad.

## Impulsores de la Decisión (Decision Drivers)
* `QA-PER-01`: la novedad debe verse en 5 minutos como máximo desde la detección.
* `QA-INT-02`: los envíos por canales no deben acumularse indefinidamente.
* `QA-SEG-03*`: la medida del 100 % de reservas de usuarios autorizados no tolera pérdidas silenciosas.
* Los drivers no fijan el tamaño de cada cola: es un parámetro de cada una, a definir con pruebas de carga.

## Opciones Consideradas
* Opción 1: Bound queue sizes: cada cola tiene un tamaño máximo; al llenarse, el productor reintenta con su identificador y se avisa a operaciones.
* Opción 2: Colas sin límite.
* Opción 3: Colas acotadas que descartan los mensajes nuevos o los más antiguos al llenarse (load shedding).

## Resultado de la Decisión
Opción elegida: **"Opción 1: colas acotadas con reintento del productor y aviso a operaciones"**, porque pone un techo a lo que el broker retiene, hace visible la saturación en lugar de ocultarla y no descarta mensajes por decisión propia del broker: el que no pudo encolar reintenta con el mismo identificador ([ADR-IT3-003](ADR-IT3-003.md)).

### Consecuencias Positivas (Beneficios)
* El broker no crece sin límite en un pico; el backlog máximo queda acotado y, con él, el retraso máximo de un mensaje.
* Una cola saturada no arrastra al resto del broker.
* La saturación genera un aviso temprano a operaciones.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Si la cola se desborda, los mensajes se retrasan: puede romperse el límite de 5 minutos de `QA-PER-01`.
* Si los reintentos se agotan, hay pérdida de mensajes, lo que choca con el 100 % de `QA-SEG-03*`.
* El tamaño correcto de cada cola exige pruebas de carga; uno chico produce rechazos innecesarios y uno grande diluye el efecto de la táctica.
* Requiere monitoreo y alertas por cola, y un procedimiento de operación para el aviso.
