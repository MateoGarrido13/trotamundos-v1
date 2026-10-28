# Fijar la cota de espera en cada Adaptador de API externa y descartar Retry

* **Estado:** aceptado
* **Fecha:** 2026-10-28
* **Decisores:** Ramiro Rossi

## Contexto y Declaración del Problema
En el *cache miss*, el Orquestador de viajes dispara en paralelo (Scatter-Gather) al Adaptador de aerolíneas (API Proveedor 2, SOAP), al Adaptador de hoteles y al Adaptador de arrendadoras, todos con llamadas síncronas hacia APIs fuera de la frontera de Trotamundos. Si una API calla, hay que decidir cuánto esperarla y si conviene reintentar. Los drivers no fijan en milisegundos la cota de espera de cada API; esa cota pertenece al adaptador.

## Impulsores de la Decisión (Decision Drivers)
* `QA-PER-02`: la cotización debe cerrar en 800 ms para el 90 % de las peticiones.
* Los adaptadores son la Capa Anti-Corrupción (ACL) de cada proveedor y el lugar natural para el manejo de fallas de ese origen.
* Las APIs externas no pueden modificarse.
* Una API lenta no debe retrasar la grilla de las demás.

## Opciones Consideradas
* Opción 1: Bound execution times en cada adaptador, sin Retry; si vence la cota, el adaptador informa que el origen no respondió.
* Opción 2: Retry con límite de reintentos ante silencio de la API.
* Opción 3: Esperar la respuesta sin cota propia del adaptador, dependiendo solo de la cota del borde.

## Resultado de la Decisión
Opción elegida: **"Opción 1: cota de espera en cada adaptador, sin Retry"**, porque sumar intentos bloqueantes contra las APIs externas compromete la cota de 800 ms de `QA-PER-02`: un timeout largo se paga en latencia y uno corto saca de la grilla una API que aún podía responder. Es preferible degradar (ADR-IT2-02) y devolver lo disponible o la copia en caché. Sin cota propia (Opción 3), un solo proveedor lento consumiría toda la cota del borde y retrasaría a los demás.

Cada adaptador: traduce el contrato del proveedor al modelo interno (ACL), verifica alcance con Ping/Echo (ADR-IT2-04) y, con eco, pide el precio por la misma llamada síncrona. Sin eco, o vencida su cota, informa a Orquestador de viajes que ese origen no respondió y no continúa con el pedido de precio. El valor en milisegundos de la cota se define por adaptador y debe ser menor que la del goal.

### Consecuencias Positivas (Beneficios)
* Aislamiento de fallas: un proveedor lento o caído solo afecta a su propio origen.
* Latencia acotada y predecible de la cotización.
* Código de manejo de fallas centralizado en cada ACL.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Fallas transitorias de una API que un reintento habría resuelto se traducen en una grilla parcial.
* Hay que calibrar la cota de cada adaptador con mediciones reales de cada proveedor (SOAP vs. REST).
* Se pierde la oportunidad de un reintento en segundo plano; si se necesita, deberá evaluarse en otra iteración.
