# Interoperabilidad: Llamada síncrona del Orquestador a la agencia preferida dentro del pedido del usuario

* **Estado:** rechazado
* **Fecha:** 2026-10-29
* **Decisores:** Santiago Otaño

## Contexto y Declaración del Problema
Para integrar la agencia de viajes preferida del usuario y resolver un problema sobre una reserva (`REF-05`, `CON-02`), se evaluó que el Orquestador de viajes invoque de forma síncrona la API de la agencia dentro de la misma petición HTTP del viajero y le devuelva en el acto el número de caso o la respuesta del tercero.

## Impulsores de la Decisión (Decision Drivers)
* `REF-05`: integración con la agencia de viajes preferida para resolver un problema.
* `CON-02`: integración mediante APIs.
* `QA-PER-02` y `QA-DIS-01`: no acoplar los hilos del Orquestador de viajes ni la disponibilidad del Core a la latencia o las caídas de un sistema externo que Trotamundos no controla.

## Opciones Consideradas
* Opción 1: Publicar el pedido en la cola de casos de ayuda del Broker y entregarlo de forma asíncrona con Retry e identificador único desde el Adaptador de agencia (`IAgencia`) desplegado en nodos propios ([ADR-IT4-010](ADR-IT4-010.md)).
* Opción 2: Llamada síncrona del Orquestador a la API de la agencia dentro del pedido del usuario.

## Resultado de la Decisión
Opción elegida: **"Opción 1: integración asíncrona por cola de casos de ayuda y Adaptador de agencia"**, y se rechaza la llamada síncrona desde el Orquestador, porque la resolución de un problema en una agencia tiene un ciclo de vida que no ocurre en milisegundos y depende de la disponibilidad de un tercero. Invocar a la agencia de forma síncrona retendría hilos de los nodos del Orquestador —los mismos que atienden la cotización de 800 ms (`QA-PER-02`)— y haría que una caída de la agencia rechace el reporte del viajero en lugar de encolarlo con reintento ([ADR-IT3-003](../ITERACION_3/ADR-IT3-003.md)).

### Consecuencias Positivas (Beneficios)
* El Orquestador registra el caso y responde al viajero de inmediato sin depender de la latencia de la agencia.
* Si la API de la agencia está caída durante una disrupción climática (cuando más problemas se reportan), ningún reclamo se pierde: queda en la cola de casos de ayuda y se entrega con Retry idempotente.

### Consecuencias Negativas (Trade-offs / Riesgos)
* El viajero ve inicialmente el estado "en trámite" y recibe la confirmación o las actualizaciones de la agencia de manera diferida en la sección "Novedades".
* Condición de reapertura: ninguna prevista mientras la agencia sea un sistema externo fuera del control operativo de Trotamundos.
