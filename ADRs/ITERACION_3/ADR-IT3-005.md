# Modificabilidad: Polymorphism y Configuration-time binding en el modelo de reservas

* **Estado:** aceptado
* **Fecha:** 2026-10-28
* **Decisores:** Santiago Otaño

## Contexto y Declaración del Problema
Hoy el Orquestador de viajes agrupa las reservas por viaje (`REF-01`) con un modelo que no distingue tipos de medio de transporte. Sumar uno nuevo (tren, autobús u otro) obligaría a modificar la agrupación, que es la lógica core. Hay que definir cómo se modela la reserva para que un tipo nuevo se agregue sin tocar esa agrupación.

## Impulsores de la Decisión (Decision Drivers)
* `QA-EVO-01`: integrar un medio de transporte que el panel todavía no agrupa en el viaje, en un plazo de 3 meses de esfuerzo de desarrollo.
* `REF-01`: la agrupación por viaje y el archivado deben seguir funcionando para todos los tipos.
* El modelo vive dentro del Orquestador, que no se divide ([ADR-IT3-011](ADR-IT3-011.md)).

## Opciones Consideradas
* Opción 1: Polymorphism: `Reserva` abstracta y un tipo concreto por medio (`ReservaVuelo`, `ReservaHotel`, `ReservaAuto`, `ReservaTren`, `ReservaAutobus`), con un Registro de tipos cargado por configuración al desplegar (Configuration-time binding).
* Opción 2: Una única clase de reserva con un campo de tipo y condicionales en la agrupación.
* Opción 3: Tipos de reserva como dato interpretado en ejecución ([ADR-IT3-013](ADR-IT3-013.md)).

## Resultado de la Decisión
Opción elegida: **"Opción 1: Polymorphism con Registro de tipos por Configuration-time binding"**, porque la agrupación trabaja contra `Reserva` (identificador, viaje, fechas, estado y resumen) y no conoce los tipos concretos. Un medio nuevo es una clase más que extiende `Reserva` y se registra, sin cambios en la agrupación (`QA-EVO-01`).

### Consecuencias Positivas (Beneficios)
* La agrupación por viaje queda cerrada a la modificación y abierta a la extensión.
* Cada tipo encapsula su validación, su resumen y su fecha de término.
* La comprobación de tipos es estática, con control por tipo.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Agrega indirección en ejecución y requiere un diseño previo del contrato `Reserva`.
* Con una medida de 3 meses hay riesgo de sobrediseñar el modelo.
* Como el binding es en tiempo de despliegue, alta de un tipo nuevo exige construir y desplegar.
* `Reserva` pasa a ser un contrato crítico: un cambio en ella impacta a todos los tipos.
* La persistencia de una jerarquía polimórfica en la base (reservas tipadas) añade complejidad de mapeo.
