# Performance: Increase resources

* **Estado:** rechazado
* **Fecha:** 2026-10-28
* **Decisores:** Santiago Otaño

## Contexto y Declaración del Problema
Ante el pico de ingesta (el de las 8 am) se evaluó como respuesta principal sumar recursos (más nodos o más capacidad) para procesar más rápido.

## Impulsores de la Decisión (Decision Drivers)
* `QA-PER-01`: la novedad debe verse en 5 minutos como máximo desde la detección.
* `QA-PER-02`: la cotización no debe verse afectada.
* El problema es el acoplamiento entre productores y consumidores, no solo la capacidad.

## Opciones Consideradas
* Opción 1: Desacoplar con un broker y colas acotadas, con la ingesta en nodos propios ([ADR-IT3-001](ADR-IT3-001.md), [ADR-IT3-002](ADR-IT3-002.md), [ADR-IT3-010](ADR-IT3-010.md)).
* Opción 2: Increase resources como táctica principal para responder a los picos.

## Resultado de la Decisión
Opción elegida: **"Opción 1: desacoplar con broker y colas acotadas"**, y se rechaza Increase resources como táctica principal, porque cuesta dinero y no ataca la causa: sin el desacople, el pico seguiría compitiendo con las cotizaciones por más nodos que se sumaran.

### Consecuencias Positivas (Beneficios)
* El costo no crece con cada pico: la cola absorbe y los consumidores drenan.
* El efecto del pico queda acotado por diseño.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Si el ritmo de consumo no alcanza, el backlog crece hasta el tope de la cola y se retrasan los mensajes, con riesgo para los 5 minutos de `QA-PER-01`.
* Igual hay que dimensionar los consumidores (ingesta y notificaciones); esa capacidad debe validarse con pruebas de carga.
