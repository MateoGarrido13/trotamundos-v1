# Interoperabilidad: Escalamiento de casos complejos del Asistente Virtual a la agencia preferida mediante la cola de casos de ayuda e `IAgencia`

* **Estado:** aceptado
* **Fecha:** 2026-11-17
* **Decisores:** Santiago Otaño

## Contexto y Declaración del Problema
`REF-07` establece que el Asistente Virtual actúa como primer nivel para problemas menores y **delega a la agencia de viajes preferida del usuario únicamente aquellos casos complejos**. En la iteración 4 (`REF-05`, [ADR-IT4-010](../../../RONDA_1/ADRs/ITERACION_4/ADR-IT4-010.md)) ya se diseñó la integración con la agencia preferida: el Orquestador registra el caso, lo publica en la cuarta cola del Broker (cola de casos de ayuda) y el Adaptador de agencia (`IAgencia`) lo entrega de forma asíncrona con Retry e identificador único. Hay que definir el criterio de frontera entre primer nivel y caso complejo, y cómo se conecta el Asistente Virtual con ese mecanismo.

## Impulsores de la Decisión (Decision Drivers)
* `REF-07`: delegar a la agencia de viajes preferida únicamente los casos complejos que exceden el primer nivel.
* `REF-05` y `CON-02`: integración por API con la agencia preferida mediante `IAgencia` y la cola de casos de ayuda ([ADR-IT4-010](../../../RONDA_1/ADRs/ITERACION_4/ADR-IT4-010.md)).
* No bloquear al viajero esperando la respuesta de la agencia ([ADR-IT4-014](../../../RONDA_1/ADRs/ITERACION_4/ADR-IT4-014.md)).

## Opciones Consideradas
* Opción 1: Clasificación explícita en dos niveles dentro del Módulo de Asistente Virtual:
  1. **Primer nivel (resuelto sin agencia):** consultas de estado de viajes/reservas/novedades, alta o baja manual de actividades y reprogramaciones simples de fechas/datos sobre reservas editables ([ADR-IT6-002](ADR-IT6-002.md)).
  2. **Caso complejo (delegado a la agencia):** disputas de cobro o reembolso, cancelaciones o reprogramaciones de tramos encadenados con penalidad del proveedor, incidencias donde el proveedor externo no responde o el viajero solicita hablar con su agencia. En ese caso, el Asistente empaqueta el contexto de la conversación (reserva afectada, motivo y transcripción resumida) e invoca la apertura de caso en el Orquestador, que lo publica en la **cola de casos de ayuda** hacia el **Adaptador de agencia (`IAgencia`)**.
* Opción 2: Que el Asistente Virtual llame de forma síncrona y directa a la API de la agencia cuando detecta un caso complejo ([ADR-IT6-005](ADR-IT6-005.md)).
* Opción 3: Derivar todas las conversaciones a la agencia sin resolver nada en el primer nivel.

## Resultado de la Decisión
Opción elegida: **"Opción 1: filtro de primer nivel y delegación asíncrona de casos complejos por el Orquestador y la cola de casos de ayuda hacia `IAgencia`"**, porque cumple literalmente `REF-07` reutilizando de punta a punta la infraestructura asíncrona creada para `REF-05` en la iteración 4. La agencia recibe solo los casos que realmente requieren intervención externa y ya enriquecidos con el resumen del diálogo y la reserva afectada, mientras el viajero recibe confirmación inmediata de que su caso quedó "en trámite" y verá las respuestas en "Novedades". La opción 2 viola el rechazo de llamada síncrona a terceros ([ADR-IT4-014](../../../RONDA_1/ADRs/ITERACION_4/ADR-IT4-014.md)). La opción 3 incumple el rol de primer nivel de `REF-07`.

### Consecuencias Positivas (Beneficios)
* Reutiliza sin modificaciones la cola de casos de ayuda, el contrato `IAgencia` y el retorno por la cola de novedades ([ADR-IT4-010](../../../RONDA_1/ADRs/ITERACION_4/ADR-IT4-010.md)).
* Reduce la carga enviada a la agencia externa al filtrar y resolver en el Orquestador las consultas de estado y reprogramaciones simples.
* Cuando el caso escala, la agencia recibe la reserva identificada y el historial del intento de primer nivel, evitando que el viajero repita su problema.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Si el clasificador cataloga como simple un caso que requería agencia, el viajero necesita un comando o botón explícito ("derivar a mi agencia") siempre disponible para forzar el escalamiento en un paso.
