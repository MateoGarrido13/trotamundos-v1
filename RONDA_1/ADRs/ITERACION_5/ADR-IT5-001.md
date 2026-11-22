# Performance: Desacoplamiento del camino analítico con quinta cola del Broker, Proyector analítico en nodos propios y Base analítica separada

* **Estado:** aceptado
* **Fecha:** 2026-11-17
* **Decisores:** Mateo Garrido

## Contexto y Declaración del Problema
`REF-06` pide recopilar datos analíticos de los viajes (tendencias, destinos y cancelaciones) para su monetización por el equipo de datos mediante consultas analíticas pesadas, y `QA-PER-04*` exige que esos informes se procesen y generen en menos de 10 segundos en promedio mientras el panel opera con 2 millones de usuarios activos por semana, 15 millones de cuentas y picos de domingo a lunes, de jueves a viernes o de disrupciones de viaje. En la iteración 4 el modelo ya expone el destino en `Reserva.lugar` ([ADR-IT4-009](../ITERACION_4/ADR-IT4-009.md)) y conserva las cancelaciones por baja lógica ([ADR-IT4-008](../ITERACION_4/ADR-IT4-008.md)), pero esos datos viven en la Base de viajes. Ejecutar consultas de agregación masiva sobre la Base de viajes competiría por CPU, memoria y E/S con las escrituras transaccionales 2PC ([ADR-IT2-004](../ITERACION_2/ADR-IT2-004.md)) y con la lectura de viajes del Core durante los picos. Hay que decidir por qué camino viajan los datos hacia el equipo de analítica y dónde se ejecutan sus consultas.

## Impulsores de la Decisión (Decision Drivers)
* `QA-PER-04*`: el informe de tendencias, destinos y cancelaciones se procesa y genera antes de los 10 segundos en promedio bajo carga de pico.
* `REF-06`: ejecución de consultas analíticas pesadas sobre tendencias, destinos y cancelaciones para el equipo de datos.
* `QA-PER-02` y `QA-DIS-01`: las consultas del equipo de datos no pueden degradar los 800 ms de la cotización ni comprometer la disponibilidad ni el failover de la Base de viajes.
* Reutilizar el Broker de colas acotadas ([ADR-IT3-001](../ITERACION_3/ADR-IT3-001.md), [ADR-IT3-002](../ITERACION_3/ADR-IT3-002.md)), Retry con idempotencia ([ADR-IT3-003](../ITERACION_3/ADR-IT3-003.md)) y el aislamiento en nodos propios ([ADR-IT3-010](../ITERACION_3/ADR-IT3-010.md)).

## Opciones Consideradas
* Opción 1: Separar el camino de lectura analítico del transaccional. Cada vez que el Orquestador de viajes confirma una creación, modificación, cancelación (baja lógica) o archivado de viaje/reserva, publica un evento analítico anonimizado (sin datos personales de la cuenta, con identificador de evento, tipo de reserva, `lugar.destino`, fechas y estado) en una **quinta cola acotada del Broker** (cola de eventos analíticos). Un **Proyector analítico**, desplegado en nodos propios junto a la ingesta, consume esa cola con Retry e identificador único y actualiza una **Base analítica** dedicada exclusivamente a las lecturas del **Servicio de consultas analíticas**.
* Opción 2: Ejecutar las consultas analíticas directamente sobre la Base de viajes primaria o sobre su Base pasiva ([ADR-IT5-004](ADR-IT5-004.md)).
* Opción 3: Un proceso de extracción por lotes nocturno (ETL diario) que copie la Base de viajes una vez por día.

## Resultado de la Decisión
Opción elegida: **"Opción 1: quinta cola del Broker, Proyector analítico en nodos propios y Base analítica separada"**, porque aísla física y operativamente la carga analítica del Core transaccional. Durante un pico de disrupción climática (cuando se disparan las cancelaciones y las consultas del equipo de datos al mismo tiempo), el Orquestador solo encola un evento liviano y las consultas pesadas del equipo de datos golpean únicamente al Servicio de consultas analíticas y a la Base analítica. La opción 2 acopla la analítica a la Base de viajes o degrada a su copia de respaldo ([ADR-IT5-004](ADR-IT5-004.md)). La opción 3 deja al equipo de datos ciego durante todo el día frente a una disrupción de viajes en curso y concentra una lectura masiva sobre la Base de viajes en la ventana del lote.

### Consecuencias Positivas (Beneficios)
* Cero impacto de las consultas analíticas pesadas sobre la Base de viajes y sobre los nodos del Orquestador.
* El evento sale anonimizado del Orquestador: la Base analítica no almacena correos ni credenciales de los viajeros.
* Se reutilizan el Broker redundante, las colas acotadas y el Retry idempotente de la iteración 3.
* La caída o saturación de la Base analítica no afecta ninguna operación de los viajeros.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Consistencia eventual en los informes: los eventos tardan desde segundos hasta algunos minutos en reflejarse en la Base analítica según el backlog de la cola. `QA-PER-04*` mide el tiempo de procesamiento del informe (10 s), no la instantaneidad sub-segundo del dato.
* Una base de datos adicional (Base analítica) y un consumidor más (Proyector analítico) para operar y monitorear.
* El Broker pasa de cuatro a cinco colas acotadas ([ADR-IT3-001](../ITERACION_3/ADR-IT3-001.md), [ADR-IT4-010](../ITERACION_4/ADR-IT4-010.md)).
