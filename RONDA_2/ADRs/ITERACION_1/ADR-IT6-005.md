# Seguridad y Modificabilidad: Acceso directo del Asistente Virtual a la Base de viajes o a la API de la agencia

* **Estado:** rechazado
* **Fecha:** 2026-11-17
* **Decisores:** Tomas Fontana

## Contexto y Declaración del Problema
Al incorporar el Módulo de Asistente Virtual (`REF-07`), se evaluó que el propio módulo se conecte directamente por JDBC a la Base de viajes para consultar y reprogramar reservas y que invoque directamente la API HTTP de la agencia preferida al escalar un caso complejo, evitando pasar por el Orquestador de viajes y por el Broker.

## Impulsores de la Decisión (Decision Drivers)
* `REF-07`: gestionar consultas, reprogramaciones menores y delegación de casos complejos a la agencia preferida.
* `QA-SEG-02`: autorización por itinerario y auditoría en la misma transacción ([ADR-IT4-007](../../../RONDA_1/ADRs/ITERACION_4/ADR-IT4-007.md)).
* `REF-04` y `REF-05`: un único camino de escritura polimórfica ([ADR-IT4-008](../../../RONDA_1/ADRs/ITERACION_4/ADR-IT4-008.md)) y desacoplamiento asíncrono de la agencia por el Broker ([ADR-IT4-010](../../../RONDA_1/ADRs/ITERACION_4/ADR-IT4-010.md), [ADR-IT4-014](../../../RONDA_1/ADRs/ITERACION_4/ADR-IT4-014.md)).

## Opciones Consideradas
* Opción 1: El Módulo de Asistente Virtual delega todas las lecturas, reprogramaciones y aperturas de casos de agencia en el Orquestador de viajes ([ADR-IT6-002](ADR-IT6-002.md), [ADR-IT6-003](ADR-IT6-003.md)).
* Opción 2: Acceso directo del Módulo de Asistente Virtual a la Base de viajes y a la API externa de la agencia preferida.

## Resultado de la Decisión
Opción elegida: **"Opción 1: todo acceso a viajes, reservas y casos de agencia pasa por el Orquestador"**, y se rechaza el acceso directo desde el Asistente Virtual, porque escribir en la Base de viajes por fuera del Orquestador rompería tres invariantes arquitectónicos a la vez: saltearía el Módulo de control de acceso y su auditoría transaccional (`QA-SEG-02`), duplicaría la validación polimórfica de `Reserva` y la emisión de eventos analíticos (`QA-EVO-01`, `REF-06`), y acoplaría el chat a la disponibilidad síncrona de la agencia externa (`REF-05`).

### Consecuencias Positivas (Beneficios)
* Se mantienen intactas todas las relaciones permitidas y fronteras de datos de las iteraciones 1 a 5.
* Ningún cambio en el esquema de la Base de viajes o en el protocolo de una agencia impacta al Módulo de Asistente Virtual.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Toda operación del Asistente requiere una llamada interna al Orquestador de viajes.
* Condición de reapertura: solo si en el futuro se reabriera el *Split module* del Orquestador ([ADR-IT3-011](../../../RONDA_1/ADRs/ITERACION_3/ADR-IT3-011.md)), en cuyo caso el Asistente llamaría al servicio extraído correspondiente y nunca a la base de datos de otro componente.
