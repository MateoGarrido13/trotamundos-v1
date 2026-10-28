# Sincronizar Base primaria y Base pasiva con Transactions (commit en dos fases), priorizando consistencia sobre latencia

* **Estado:** aceptado
* **Fecha:** 2026-10-28
* **Decisores:** Santiago Otaño

## Contexto y Declaración del Problema
La iteración 1 dejó propuesta una Base pasiva como *Redundant spare* de la Base primaria, con *State resynchronization* para mantenerlas sincronizadas, pero el modo de intercambio quedó sin especificar (en la vista de la iteración 1 el conector TCP aparece como replicación binaria continua asíncrona). Hay que decidir cómo se confirman las escrituras entre las dos copias: si cae la primaria, la pasiva debe tener exactamente el mismo estado, porque el sistema agrupa reservas de viajeros que son el "único punto de verdad" de sus arreglos de viaje.

## Impulsores de la Decisión (Decision Drivers)
* `QA-DIS-01`: ante la caída de un nodo, el trade-off del goal prioriza la consistencia por sobre la performance en latencia.
* Disponibilidad: menos de 5 minutos de inactividad no planificada al mes.
* Los datos de reservas no deben perderse ni quedar divergentes tras una conmutación.

## Opciones Consideradas
* Opción 1: Transactions: commit en dos fases (2PC) entre Base primaria y Base pasiva sobre TCP; la escritura se retiene hasta que ambas acuerdan.
* Opción 2: Replicación asíncrona continua (confirma en la primaria y replica después).
* Opción 3: Replicación semisíncrona o por quórum.

## Resultado de la Decisión
Opción elegida: **"Opción 1: Transactions (commit en dos fases)"**, porque garantiza que la copia pasiva (*Redundant spare*) esté exactamente igual que la primaria en cada escritura confirmada (*State resynchronization* resuelta mediante la transacción), cumpliendo la prioridad de consistencia de `QA-DIS-01`. La replicación asíncrona permitiría perder escrituras ya confirmadas al conmutar.

Detalle: Orquestador de viajes escribe en Base primaria por JDBC; Base primaria no confirma éxito hasta que Base pasiva acuerda. Esto reemplaza lo que la iteración 1 describía como replicación asíncrona en el conector TCP entre ambas bases; la vista de componentes y conectores debe actualizarse.

### Consecuencias Positivas (Beneficios)
* Consistencia fuerte entre copias: sin pérdida de escrituras confirmadas ante una falla de la primaria.
* La Base pasiva queda lista para ser promovida (ADR-IT2-06).
* Semántica atómica, consistente, aislada y durable para las escrituras de viajes.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Se paga fuertemente en latencia de escritura: la escritura se retiene hasta que ambas copias acuerdan.
* Si la Base pasiva no responde, la primaria no puede confirmar escrituras (riesgo de bloqueo), lo que afecta la disponibilidad; hay que definir timeouts y política ante pasiva caída.
* El 2PC no escala a muchas réplicas ni a multirregión sin penalidad de latencia; revisar al abordar escalabilidad (`QA-ESC-01`) e internacionalización.
* La lectura/cotización (`QA-PER-02`) no depende de este camino, pero las escrituras de viajes sí.
