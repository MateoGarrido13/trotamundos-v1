# Detectar fallas de las APIs externas con Ping/Echo y descartar Heartbeat

* **Estado:** aceptado
* **Fecha:** 2026-10-28
* **Decisores:** Tomas Fontana

## Contexto y Declaración del Problema
Para tomar decisiones de degradación (ADR-IT2-02, ADR-IT2-03) el sistema necesita saber si cada API de proveedor está disponible antes de pedirle el precio. La iteración 1 incorporó Ping/Echo en los adaptadores, y la iteración 2 dejó abierta la evaluación de Heartbeat como táctica alternativa de detección de fallas. Es necesario decidir el mecanismo de detección definitivo.

## Impulsores de la Decisión (Decision Drivers)
* `QA-PER-02`: la detección no puede consumir tiempo significativo de los 800 ms.
* Los componentes a vigilar (API Proveedor 2 SOAP, API de hoteles, API de arrendadoras) son externos y no están a nuestro alcance modificarlos.
* La detección debe poder iniciarla Trotamundos, sin cooperación del proveedor.

## Opciones Consideradas
* Opción 1: Ping/Echo desde cada adaptador hacia su API.
* Opción 2: Heartbeat: el componente vigilado emite mensajes periódicos a un monitor.
* Opción 3: Sin detección explícita; inferir la falla únicamente por vencimiento de la cota.

## Resultado de la Decisión
Opción elegida: **"Opción 1: Ping/Echo"**, porque la iniciativa parte del adaptador, que es nuestro. Heartbeat exige que el componente vigilado emita latidos, y las APIs de proveedores externos no pueden modificarse para hacerlo. Además, Heartbeat se paga en latencia. Con Ping/Echo, si hay eco el adaptador pide el precio; si no, informa de inmediato que el origen no respondió y no consume la cota en una llamada de precio que fallaría.

Heartbeat queda **rechazado** para las APIs externas. Podría reconsiderarse para componentes propios.

### Consecuencias Positivas (Beneficios)
* No depende de ninguna modificación en sistemas de terceros.
* Detección temprana de orígenes caídos, que alimenta la grilla parcial.
* Se mantiene la coherencia con la táctica ya incorporada en la iteración 1.

### Consecuencias Negativas (Trade-offs / Riesgos)
* El ping agrega un mensaje síncrono por llamada, que suma latencia al camino de cotización.
* Un eco positivo no garantiza que la consulta de precio subsiguiente responda a tiempo (sigue haciendo falta la cota del ADR-IT2-03).
* Incrementa el tráfico hacia los proveedores; verificar que no incumple sus límites de uso.
