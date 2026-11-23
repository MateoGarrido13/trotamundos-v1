# Justificación ADRs — Iteración 7 (Ronda 2)

Esta iteración cierra los dos drivers que quedaron pendientes de ITERACION_1: `QA-PER-05` (respuesta al viajero en como máximo 35 segundos) y `QA-SEG-04` (no obedecer una inyección de prompt y responder solo dentro del propósito de `REF-07`).

## ADR-IT7-001 — Filtrado de inyección de prompt y alcance acotado al propósito de REF-07

**Por qué.** `QA-SEG-04` exige que el asistente no obedezca inyecciones de prompt ni responda fuera del propósito de `REF-07` (reprogramaciones, consultas de estado, problemas menores, delegación de casos complejos). Sin un filtrado previo, el motor de lenguaje natural podría obedecer instrucciones ajenas o generar respuestas fuera de alcance.

**Qué se pagó.** Suma un componente de filtrado adicional. El usuario puede recibir un rechazo si su consulta no encaja estrictamente en el propósito de `REF-07`, pero siempre puede optar por "derivar a mi agencia" para escalar.

**Alternativa más cercana a ganar.** Opción 2 (ningún filtrado, confiar en el motor). Se rechazó porque no garantiza `QA-SEG-04`: un motor de lenguaje natural no es un filtro de seguridad confiable por sí solo.

## ADR-IT7-002 — Cota de ejecución de 35 segundos en IMotorConversacional con degradación a menú guiado

**Por qué.** `QA-PER-05` exige que la respuesta llegue en como máximo 35 segundos. Tareas complejas como reprogramaciones pueden exceder esa cota si el motor de IA tarda. El time-out hacia el proveedor muestra el número de contacto de la agencia de viajes preferida (`QA-DIS-02`) antes de agotar esos 35 segundos ([ADR-IT7-004](ADR-IT7-004.md)).

**Qué se pagó.** Cuando el proveedor no responde, el viajero recibe el número de contacto de la agencia de viajes preferida en lugar de una respuesta conversacional libre.

## ADR-IT7-004 — Time-out y Circuit Breaker hacia los proveedores de modelo de IA

**Por qué.** Esperar los 35 segundos en cada llamada a un proveedor que no responde degrada la latencia del módulo que atiende al viajero y retiene el hilo. Time-out detecta la falla antes de esa cota y entrega el número de contacto de la agencia de viajes preferida (`QA-DIS-02`). Circuit Breaker, tras cinco time-out consecutivos, pasa a Abierto y ese número sale en 0 ms hasta que el proveedor se recupere.

**Qué se pagó.** Con el circuito abierto no hay respuesta generativa de ese proveedor, aunque se haya recuperado un instante antes del próximo cierre.

**Alternativa más cercana a ganar.** Esperar siempre hasta los 35 segundos. Se rechazó porque cada falla paga la cota completa.

**Alternativa más cercana a ganar.** Opción 2 (sin cota, esperar indefinidamente). Se rechazó porque incumple `QA-PER-05`: el viajero podría quedar esperando sin respuesta.

## ADR-IT7-003 — Clasificación en dos niveles y delegación asíncrona de casos complejos al Adaptador de agencia

**Por qué.** `REF-07` establece que el asistente actúa como primer nivel y delega casos complejos a la agencia. La frontera entre ambos debe ser explícita para evitar que el asistente intente resolver problemas que requieren intervención externa.

**Qué se pagó.** Requiere ofrecer siempre una opción explícita ("derivar a mi agencia") por si el viajero quiere escalar manualmente.

**Alternativa más cercana a ganar.** Opción 2 (llamada síncrona directa a la API de la agencia). Se rechazó porque introduce latencia no controlada de un tercero y puede perder el reclamo si la agencia está caída.

## Conclusión

Con estos tres ADR, `QA-PER-05` y `QA-SEG-04` quedan en `Completely`. Junto con `REF-07` y `QA-DIS-02` (Completely en ITERACION_1), todos los drivers de la Ronda 2 están cerrados.
