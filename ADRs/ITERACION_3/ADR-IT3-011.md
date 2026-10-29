# Modificabilidad: Split module / Redistribute responsibilities (partir el Orquestador)

* **Estado:** rechazado
* **Fecha:** 2026-10-28
* **Decisores:** Tomas Fontana

## Contexto y Declaración del Problema
El Orquestador de viajes concentra la cotización con Scatter-Gather, la gestión de viajes, y ahora el modelo de reservas, las novedades, la whitelist y los mensajes en revisión. Se evaluó partirlo en dos servicios (cotización y gestión de viajes).

## Impulsores de la Decisión (Decision Drivers)
* `QA-EVO-01` y `QA-INT-01`: los cambios de la iteración deben absorberse sin tocar la lógica core.
* `QA-PER-02`: la cotización se resuelve en memoria dentro de los 800 ms.
* Simplicidad: no sumar servicios ni interfaces sin un driver que lo exija.

## Opciones Consideradas
* Opción 1: Mantener un único Orquestador de viajes, con el modelo de reservas por dentro.
* Opción 2: Split module: separar cotización y gestión de viajes en dos servicios.

## Resultado de la Decisión
Opción elegida: **"Opción 1: mantener un único Orquestador de viajes"**, y se rechaza partirlo, porque ningún driver de esta iteración lo exige: la ingesta ya queda como pieza propia ([ADR-IT3-010](ADR-IT3-010.md)) y el polimorfismo cubre `QA-EVO-01` ([ADR-IT3-005](ADR-IT3-005.md)). Partirlo sumaría un servicio y una interfaz, y una llamada de red o una sincronización entre dos mitades que hoy se resuelven en memoria.

### Consecuencias Positivas (Beneficios)
* Se evita una interfaz y un servicio más, con su despliegue y monitoreo.
* La cotización conserva su camino en memoria.

### Consecuencias Negativas (Trade-offs / Riesgos)
* El Orquestador sigue acumulando responsabilidades, con riesgo de baja cohesión y de ser un cuello de botella.
* Cotización y gestión de viajes escalan juntas, con el costo de granularidad ya aceptado con N-Tier ([ADR-001](../ITERACION_1/ADR-001.md)).
* Se reabre si el Orquestador se vuelve un cuello de botella (paso 7).
