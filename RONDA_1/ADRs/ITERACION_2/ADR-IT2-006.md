# Reintentar los pedidos a las APIs de proveedores externos ante silencio (Retry)

* **Estado:** rechazado
* **Fecha:** 2026-10-28
* **Decisores:** Yaco Recroa

## Contexto y Declaración del Problema
Cuando una API de proveedor no responde, puede tratarse de un silencio transitorio. Retry es una táctica de disponibilidad que repite el pedido, con un límite de reintentos, esperando que tenga éxito. La iteración 2 la evaluó en el paso 4 para el camino de cotización, en el que el Orquestador de viajes consulta en paralelo a los adaptadores de aerolíneas, hoteles y arrendadoras.

## Impulsores de la Decisión (Decision Drivers)
* `QA-PER-02`: la cotización debe cerrar en 800 ms para el 90 % de las peticiones.
* Las llamadas a las APIs externas son síncronas y su latencia no es controlable.
* La grilla puede entregarse parcial (Graceful degradation) sin dejar de cumplir la función crítica.

## Opciones Consideradas
* Opción 1: Retry con límite de reintentos en cada adaptador.
* Opción 2: Sin Retry; cota de espera por adaptador y degradación a grilla parcial o a la copia en caché.

## Resultado de la Decisión
Opción elegida: **"Opción 2: sin Retry"** (ver ADR-IT2-02 y ADR-IT2-03). La **Opción 1 (Retry) queda rechazada**, porque sumar intentos bloqueantes contra las APIs externas compromete la cota de 800 ms de `QA-PER-02`: un timeout largo se paga en latencia, y uno corto saca de la grilla una API que aún podía responder, perjudicando la disponibilidad de ese origen. Es preferible degradar y devolver lo que se tenga o la copia en caché.

### Consecuencias Positivas (Beneficios)
* La latencia de la cotización queda acotada y predecible.
* Se evita multiplicar la carga sobre proveedores que ya están lentos o con fallas.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Una falla transitoria que un reintento habría resuelto se traduce en una grilla parcial.
* Si más adelante se necesita recuperar orígenes perdidos, podría evaluarse un reintento asíncrono fuera del camino de la cotización.
