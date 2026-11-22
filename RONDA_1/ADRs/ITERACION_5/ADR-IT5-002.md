# Performance: Preagregación incremental por destino, tendencia y cancelación con cota de 10 s en el Servicio de consultas analíticas

* **Estado:** aceptado
* **Fecha:** 2026-11-17
* **Decisores:** Santiago Otaño

## Contexto y Declaración del Problema
Separar la Base analítica ([ADR-IT5-001](ADR-IT5-001.md)) evita impactar al Core, pero no garantiza por sí solo que el informe del equipo de datos se procese y genere en menos de 10 segundos en promedio (`QA-PER-04*`) sobre el histórico acumulado de una plataforma con 15 millones de cuentas y 2 millones de usuarios activos semanales. Si cada consulta del equipo de datos recorriera todos los eventos crudos de reservas desde cero, el tiempo de respuesta crecería linealmente con el volumen histórico. Hay que decidir cómo se estructura el dato en la Base analítica y cómo se acota el tiempo de respuesta del informe.

## Impulsores de la Decisión (Decision Drivers)
* `QA-PER-04*`: procesamiento y generación del informe en menos de 10 segundos en promedio bajo operación de 15 millones de cuentas y 2 millones de usuarios activos semanales.
* `REF-06`: el informe consulta tres dimensiones conocidas de antemano: tendencias temporales, destinos (`Reserva.lugar.destino`) y cancelaciones (bajas lógicas y cancelaciones de proveedor).
* Reutilizar *Bound execution times* ([ADR-IT2-001](../ITERACION_2/ADR-IT2-001.md)).

## Opciones Consideradas
* Opción 1: El Proyector analítico, al consumir cada evento de la cola de eventos analíticos, además de guardar el hecho atómico actualiza **tablas/vistas preagregadas incrementales** por destino, ventana temporal (día/semana/mes), tipo de reserva y estado (confirmada vs. cancelada), evitando doble conteo por identificador de evento. El **Servicio de consultas analíticas** resuelve los informes leyendo directamente esas proyecciones preagregadas y aplica una **cota de ejecución de 10 segundos** (*Bound execution times*).
* Opción 2: Guardar únicamente los eventos crudos en la Base analítica y calcular las agregaciones completas en el momento de cada petición del equipo de datos.
* Opción 3: Precalcular un único informe estático fijo cada hora, sin permitir filtrar por rango de fechas ni por destino.

## Resultado de la Decisión
Opción elegida: **"Opción 1: preagregación incremental en el Proyector analítico y lectura con cota de 10 s"**, porque las dimensiones que pide `REF-06` y `QA-PER-04*` (tendencias, destinos y cancelaciones) están definidas en el escenario. Actualizar contadores y series por destino y fecha al ingresar cada evento traslada el costo al camino asíncrono del Proyector y reduce la consulta del equipo de datos a una lectura acotada por rango de fechas y destino, cuyo tiempo depende de la cantidad de destinos y ventanas consultadas y no de los millones de reservas individuales. La opción 2 degrada a medida que crece el histórico y supera los 10 s. La opción 3 impide que el equipo de datos cruce destinos o ventanas a demanda.

### Consecuencias Positivas (Beneficios)
* El tiempo de generación del informe se mantiene muy por debajo de los 10 segundos independientemente de que la plataforma acumule millones de viajes.
* El Proyector actualiza las series de forma idempotente usando el identificador único del evento analítico.
* La cota de 10 segundos en el Servicio de consultas analíticas evita que una consulta mal acotada monopolice la Base analítica.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Mayor trabajo de escritura en el Proyector analítico por cada evento consumido (guardar el evento y actualizar los agregados).
* Si en el futuro el equipo de datos pide agrupar por una dimensión nueva que no estaba preagregada, habrá que recalcular la proyección a partir de los eventos históricos almacenados en la Base analítica.
