# Modificabilidad: Interpret parameters / Shared repositories (tipos de reserva como dato)

* **Estado:** rechazado
* **Fecha:** 2026-10-28
* **Decisores:** Mateo Garrido

## Contexto y Declaración del Problema
Para sumar tipos de reserva sin tocar la agrupación se evaluó describirlos como datos (parámetros o repositorio compartido) que el sistema interpreta en ejecución, en lugar de modelarlos como clases.

## Impulsores de la Decisión (Decision Drivers)
* `QA-EVO-01`: un medio de transporte nuevo en 3 meses de esfuerzo.
* `REF-01`: validación, resumen y fecha de término coherentes por tipo.
* Control estático de tipos para detectar errores antes de ejecutar.

## Opciones Consideradas
* Opción 1: Polymorphism con Registro de tipos por Configuration-time binding ([ADR-IT3-005](ADR-IT3-005.md)).
* Opción 2: Interpret parameters / Shared repositories: los tipos como datos de configuración.

## Resultado de la Decisión
Opción elegida: **"Opción 1: Polymorphism"**, y se rechaza interpretar los tipos como datos, porque se pierde la validación estática y el control por tipo. Polymorphism alcanza para `QA-EVO-01`.

### Consecuencias Positivas (Beneficios)
* Los errores de tipo se detectan al compilar y probar, no en producción.
* Cada tipo tiene un comportamiento explícito y testeable.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Un tipo nuevo exige código y despliegue; no hay alta "en caliente" por configuración.
* El equipo debe tocar código para cada medio de transporte, aunque no toque la agrupación.
