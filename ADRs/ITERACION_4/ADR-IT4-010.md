# Interoperabilidad: Adaptador de agencia detrás de `IAgencia`, con pedidos de ayuda asíncronos

* **Estado:** aceptado
* **Fecha:** 2026-10-29
* **Decisores:** Santiago Otaño

## Contexto y Declaración del Problema
`REF-05` pide integrar el sistema con la agencia de viajes preferida del usuario para resolver un problema rápidamente, y `CON-02` fija que las integraciones son por APIs. Las iteraciones 1 y 3 resolvieron cómo se integran los proveedores: una Capa Anti-Corrupción por contraparte ([ADR-007](../ITERACION_1/ADR-007.md)) detrás del contrato común `IProveedor` ([ADR-IT3-004](../ITERACION_3/ADR-IT3-004.md)). Una agencia es otra contraparte externa, cuyo pedido no tiene un usuario esperando una respuesta en milisegundos y cuyo estado cambia con el tiempo. Hay que decidir cómo se integra y cómo viaja el pedido.

## Impulsores de la Decisión (Decision Drivers)
* `REF-05`: integración con la agencia preferida para resolver un problema.
* `CON-02`: la integración con terceros es por APIs.
* Un pedido de ayuda no se pierde aunque la agencia no responda (se reutiliza [ADR-IT3-003](../ITERACION_3/ADR-IT3-003.md)).
* Una agencia nueva se suma sin tocar el Core, como un hotel nuevo ([ADR-IT3-004](../ITERACION_3/ADR-IT3-004.md)).

## Opciones Consideradas
* Opción 1: `IAgencia`, que extiende `IProveedor` con `abrirCaso(caso)` y `consultarCaso(idCaso)`. Un adaptador por agencia, en nodos propios junto a la ingesta ([ADR-IT3-010](../ITERACION_3/ADR-IT3-010.md)). El Orquestador guarda el caso y la agencia preferida del viajero y publica el pedido en una nueva cola de casos de ayuda del Broker. El adaptador lo entrega con Retry e identificador único. Las novedades del caso que informe la agencia entran por la cola de novedades y la ingesta, como cualquier otra novedad.
* Opción 2: Llamada síncrona del Orquestador a la agencia dentro del pedido del usuario ([ADR-IT4-018](ADR-IT4-018.md)).
* Opción 3: Redirigir al usuario al portal de la agencia, sin integración.
* Opción 4: Modelar la agencia como un `ICanal` de salida.

## Resultado de la Decisión
Opción elegida: **"Opción 1: Adaptador de agencia detrás de `IAgencia`, con pedidos asíncronos por el Broker"**, porque reutiliza lo decidido para los proveedores y para la ruta asíncrona: la ACL aísla el contrato de cada agencia, el Broker desacopla al viajero de la disponibilidad de un tercero y el Retry con identificador evita perder o duplicar el pedido. La opción 3 no es una integración y no cumple `REF-05` ni `CON-02`. La opción 4 fuerza a un canal de envío a manejar un ciclo de vida (caso abierto, en curso, resuelto) que `ICanal` no tiene. El Broker pasa de tres a cinco colas con esta decisión y la de [ADR-IT4-011](ADR-IT4-011.md): esto amplía [ADR-IT3-001](../ITERACION_3/ADR-IT3-001.md) y cada cola nueva queda acotada y con Retry ([ADR-IT3-002](../ITERACION_3/ADR-IT3-002.md), [ADR-IT3-003](../ITERACION_3/ADR-IT3-003.md)).

### Consecuencias Positivas (Beneficios)
* Una agencia nueva es un adaptador más, en un único módulo, sin tocar al Orquestador.
* El viajero no espera a un tercero: ve el caso "en trámite" y las novedades llegan por "Novedades".
* El pedido sobrevive a una agencia caída gracias a Retry idempotente.

### Consecuencias Negativas (Trade-offs / Riesgos)
* El viajero no recibe una confirmación inmediata de la agencia, solo de que el pedido quedó registrado.
* Cómo informa la agencia sus cambios (aviso a un listener o consulta periódica) depende de la agencia y no se decide acá.
* Hay que definir el estado del caso cuando se agotan los reintentos: la regla de partida es dejarlo "sin entregar", visible en "Novedades" con opción de reintentar.
* La reserva afectada y la descripción del problema viajan a un tercero: requiere el consentimiento del viajero al elegir su agencia.
* `IAgencia` suma superficie al contrato `IProveedor`, ya crítico.
* Dos colas nuevas en el mismo Broker aumentan lo que hay que monitorear y dimensionar.
