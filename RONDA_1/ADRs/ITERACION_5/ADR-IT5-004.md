# Performance: Ejecución de consultas analíticas directamente sobre la Base de viajes (primaria o pasiva)

* **Estado:** rechazado
* **Fecha:** 2026-11-17
* **Decisores:** Yaco Recroa

## Contexto y Declaración del Problema
Para resolver `REF-06` y `QA-PER-04*` (consultas analíticas de tendencias, destinos y cancelaciones procesadas en menos de 10 segundos) sin agregar una base de datos nueva, se evaluó que el equipo de datos ejecute sus consultas directamente contra la Base de viajes primaria o contra su copia pasiva.

## Impulsores de la Decisión (Decision Drivers)
* `QA-PER-04*`: informe generado en menos de 10 segundos en promedio durante picos de domingo a lunes, jueves a viernes o disrupciones de viaje.
* `QA-PER-02`: mantener los 800 ms en el percentil 90 para 250.000 usuarios concurrentes.
* `QA-DIS-01`: menos de 5 minutos de inactividad mensual, sostenido por el commit en dos fases ([ADR-IT2-004](../ITERACION_2/ADR-IT2-004.md)) y la promoción de la Base pasiva ([ADR-IT2-005](../ITERACION_2/ADR-IT2-005.md)).

## Opciones Consideradas
* Opción 1: Desacoplar el camino analítico mediante la quinta cola del Broker, un Proyector analítico en nodos propios y una Base analítica separada con vistas preagregadas ([ADR-IT5-001](ADR-IT5-001.md), [ADR-IT5-002](ADR-IT5-002.md)).
* Opción 2: Ejecutar las consultas analíticas sobre la Base de viajes primaria.
* Opción 3: Ejecutar las consultas analíticas sobre la Base de viajes pasiva (*Redundant spare*).

## Resultado de la Decisión
Opción elegida: **"Opción 1: Base analítica separada alimentada por cola"**, y se rechaza consultar tanto la Base primaria como la Base pasiva de viajes. Consultar la Base primaria durante un pico de disrupción climática hace que los escaneos analíticos compitan por locks, memoria y disco con las lecturas de itinerarios y con las escrituras que pagan el commit en dos fases (`QA-PER-02`). Consultar la Base pasiva tampoco es inocuo: la pasiva recibe en tiempo real cada transacción en dos fases desde la primaria ([ADR-IT2-004](../ITERACION_2/ADR-IT2-004.md)) y debe estar libre para asumir todo el tráfico transaccional en caso de caída ([ADR-IT2-005](../ITERACION_2/ADR-IT2-005.md)). Una consulta analítica pesada sobre la pasiva retrasaría el acuerdo del 2PC —frenando de rebote a la primaria— o dejaría degradado el nodo de respaldo justo cuando ocurre un fallo.

### Consecuencias Positivas (Beneficios)
* La Base primaria y la Base pasiva de viajes quedan dedicadas al 100 % a la operación transaccional y a la disponibilidad de `QA-DIS-01`.
* El acuerdo del commit en dos fases entre primaria y pasiva no sufre demoras por lecturas analíticas.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Obliga a mantener el Proyector analítico y la Base analítica separada ([ADR-IT5-001](ADR-IT5-001.md)).
* Condición de reapertura: ninguna mientras la Base de viajes utilice commit en dos fases síncrono entre primaria y pasiva.
