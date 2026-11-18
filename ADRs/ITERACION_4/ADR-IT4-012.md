# Escalabilidad: Base de cuentas distribuida entre regiones con confirmación síncrona

* **Estado:** rechazado
* **Fecha:** 2026-10-29
* **Decisores:** Tomas Fontana

## Contexto y Declaración del Problema
Para satisfacer `QA-ESC-01` (100.000 altas diarias desde tres continentes con confirmación en menos de 2 segundos) manteniendo al mismo tiempo una única vista global de cuentas y unicidad inmediata del correo electrónico, se evaluó usar una base de datos distribuida entre las tres regiones que confirme cada escritura de forma síncrona en todas ellas antes de responder al cliente.

## Impulsores de la Decisión (Decision Drivers)
* `QA-ESC-01`: confirmación de cuenta en menos de 2 segundos independientemente del continente de origen, y 0 rechazos por saturación o timeout.
* `QA-DIS-01`: menos de 5 minutos de inactividad mensual; la caída o lentitud de un enlace no debe detener el servicio global.
* Consistencia de lo ya decidido en la iteración 2 ([ADR-IT2-004](../ITERACION_2/ADR-IT2-004.md)).

## Opciones Consideradas
* Opción 1: Partición geográfica de las cuentas por región de origen, con commit en dos fases solo dentro de la región ([ADR-IT4-001](ADR-IT4-001.md)) y verificación de unicidad acotada con reconciliación asíncrona ([ADR-IT4-003](ADR-IT4-003.md)).
* Opción 2: Base de cuentas distribuida entre las tres regiones, con confirmación síncrona global en cada alta.

## Resultado de la Decisión
Opción elegida: **"Opción 1: partición geográfica con confirmación local y unicidad acotada"**, y se rechaza la base distribuida con confirmación síncrona entre regiones, porque un protocolo de consenso o commit en dos fases a través de enlaces intercontinentales ata cada alta al continente más lejano y más lento. [ADR-IT2-004](../ITERACION_2/ADR-IT2-004.md) ya dejó establecido que el commit en dos fases solo es viable dentro de un mismo entorno de baja latencia y no a escala multirregión. Además, con confirmación síncrona global, la caída o partición de red de una región bloquearía las altas de las otras dos, incumpliendo el "0 rechazos por timeout" de `QA-ESC-01`.

### Consecuencias Positivas (Beneficios)
* El camino crítico de escritura del alta queda confinado a la región de origen del viajero.
* La indisponibilidad de una región no frena las altas en los demás continentes.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Se renuncia a la unicidad global inmediata del correo electrónico, que pasa a ser eventual con una ventana acotada de reconciliación ([ADR-IT4-003](ADR-IT4-003.md)).
* Condición de reapertura: si un nuevo requerimiento legal o de negocio prohibiera cualquier ventana temporal de duplicidad de correo y a la vez relajara la cota de 2 segundos y la tolerancia a caídas regionales.
