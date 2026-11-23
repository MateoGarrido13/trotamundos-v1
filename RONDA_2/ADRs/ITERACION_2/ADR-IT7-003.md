# ADR-IT7-003 — Clasificación en dos niveles y delegación asíncrona de casos complejos al Adaptador de agencia

## Contexto

`REF-07` establece que el Asistente Virtual actúa como primer nivel para problemas menores y delega a la agencia de viajes preferida del usuario únicamente aquellos casos complejos. La frontera entre primer nivel y caso complejo debe ser una decisión de diseño explícita.

## Impulsores

- `REF-07`: Requerimiento funcional avanzado obligatorio de la segunda entrega.
- `QA-SEG-04`: El asistente no responde fuera del propósito de `REF-07`.

## Opciones

| Opción | Descripción |
| --- | --- |
| Opción 1 | Clasificación en dos niveles: primer nivel (consultas de estado/novedades, reprogramaciones o bajas sobre reservas editables) resuelto contra el Orquestador; caso complejo (reembolsos, disputas, tramos con penalidad, proveedor caído o pedido explícito del viajero) delegado invocando la apertura de caso en el Orquestador con el resumen del diálogo, que sale por la cola de casos de ayuda hacia el Adaptador de agencia. |
| Opción 2 | Llamada síncrona directa del Asistente Virtual a la API de la agencia preferida. |

## Decisión

**Opción 1 elegida.** Se clasifica en dos niveles. Lo que se resuelve con las operaciones ya existentes sobre el itinerario es primer nivel; lo que involucra dinero, penalidades de proveedor o un tercero que no responde se delega. El escalamiento pasa por el Orquestador y no directo al Broker, porque el Orquestador es el dueño del estado del caso y valida el permiso sobre el itinerario. Como alternativa, se ofrece el número de contacto de la agencia de viajes preferida del usuario para que pueda contactarla directamente.

## Consecuencias

- Positivo: Cumple `REF-07` y `QA-SEG-04` reutilizando la cola de casos de ayuda y el Adaptador de agencia sin cambios estructurales. Filtra el ruido antes de llegar a la agencia y ofrece el número de contacto de la agencia como alternativa para delegar los casos complejos.
- Negativo: Requiere ofrecer siempre una opción explícita ("derivar a mi agencia") por si el viajero quiere escalar manualmente.

## Relación con otros ADRs

- `ADR-IT6-003`: Escalamiento de casos complejos del Asistente Virtual a la agencia preferida mediante la cola de casos de ayuda y el Adaptador de agencia (definido en ITERACION_1). Este ADR refina la clasificación en dos niveles para `QA-SEG-04`.
- `ADR-IT7-001`: Filtrado de inyección de prompt. El filtrado ocurre antes de la clasificación en dos niveles.
