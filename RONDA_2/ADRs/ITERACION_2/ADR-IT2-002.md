# ADR-IT2-002 — Cota de ejecución de 35 segundos en IMotorConversacional con degradación a menú guiado

## Contexto

`QA-PER-05` requiere que la respuesta del asistente al viajero llegue en como máximo 35 segundos cuando hay un proveedor de modelo de IA disponible. Sin embargo, tareas complejas como reprogramaciones pueden exceder esa cota si el motor de IA tarda.

## Impulsores

- `QA-PER-05`: Con un proveedor de modelo de IA disponible, la respuesta del asistente al viajero llega en como máximo 35 segundos.
- `REF-07`: El asistente actúa como primer nivel de soporte interactivo.

## Opciones

| Opción | Descripción |
| --- | --- |
| Opción 1 | Cota de ejecución en `IMotorConversacional`. Si el motor supera la cota, degradar a menú guiado de opciones de primer nivel. |
| Opción 2 | Sin cota; esperar indefinidamente a que el motor responda. |

## Decisión

**Opción 1 elegida.** Se aplica una cota de espera en `IMotorConversacional` de como máximo 35 segundos para el viajero. Si el proveedor de modelo no responde, el time-out se agota antes de esa cota, se libera el hilo y el Asistente muestra el número de contacto de la agencia de viajes preferida (`QA-DIS-02`). El Circuit Breaker de [ADR-IT2-004](ADR-IT2-004.md) evita repetir esa espera.

## Consecuencias

- Positivo: Cumple `QA-PER-05`. El viajero siempre recibe una respuesta dentro de los 35 segundos, aunque sea el número de contacto de la agencia de viajes preferida en lugar de una respuesta generativa libre.
- Negativo: Cuando el motor de IA supera la cota, el viajero recibe el número de contacto de la agencia de viajes preferida en lugar de una respuesta conversacional libre.

## Relación con otros ADRs

- `ADR-IT2-001`: Filtrado de inyección de prompt. El filtrado ocurre antes de la cota de espera.
- `ADR-IT1-004`: Contrato `IMotorConversacional` con cota de espera y degradación a menú guiado (definido en ITERACION_1). Este ADR refina la cota específica de 35 segundos para `QA-PER-05`.
