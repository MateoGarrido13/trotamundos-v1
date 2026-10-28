# Usar Heartbeat para vigilar las APIs de proveedores externos

* **Estado:** rechazado
* **Fecha:** 2026-10-28
* **Decisores:** Ramiro Rossi

## Contexto y Declaración del Problema
Para sostener la cotización (`QA-PER-02`) y la disponibilidad (`QA-DIS-01`) hace falta saber si las APIs de los proveedores (API Proveedor 2 SOAP, API de hoteles, API de arrendadoras) están operativas. Heartbeat es una táctica de detección de fallas en la que el componente vigilado emite mensajes periódicos a un monitor. La iteración 2 la evaluó en el paso 4 como alternativa a Ping/Echo, que ya había sido incorporada en la iteración 1.

## Impulsores de la Decisión (Decision Drivers)
* `QA-PER-02`: la cotización debe cerrar en 800 ms para el 90 % de las peticiones.
* Las APIs a vigilar son externas y no está a nuestro alcance modificarlas para que emitan latidos.
* La detección debe poder iniciarla Trotamundos sin cooperación del proveedor.

## Opciones Consideradas
* Opción 1: Heartbeat: cada API emite latidos periódicos hacia un monitor de Trotamundos.
* Opción 2: Ping/Echo desde cada adaptador hacia su API.
* Opción 3: Sin detección explícita; inferir la falla por vencimiento de la cota.

## Resultado de la Decisión
Opción elegida: **"Opción 2: Ping/Echo"** (ver ADR-IT2-04). La **Opción 1 (Heartbeat) queda rechazada**, porque el componente que se necesita vigilar es externo al sistema y no puede modificarse para que emita latidos hacia nuestro monitor. Además, la táctica se paga en performance (latencia), que es el atributo más ajustado en esta iteración.

### Consecuencias Positivas (Beneficios)
* No se introduce un monitor de latidos ni dependencia de que los proveedores cooperen.
* Se mantiene un único mecanismo de detección (Ping/Echo), más simple de operar y probar.

### Consecuencias Negativas (Trade-offs / Riesgos)
* No hay vigilancia continua en segundo plano: el estado de una API se conoce recién al consultarla.
* Si en el futuro se integra un proveedor que publique latidos o un endpoint de salud, habrá que reevaluar esta decisión.
