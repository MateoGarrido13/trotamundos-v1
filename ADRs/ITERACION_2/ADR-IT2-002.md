# Aplicar Graceful degradation: respuesta por defecto desde la caché y grilla parcial en el orquestador

* **Estado:** aceptado
* **Fecha:** 2026-10-28
* **Decisores:** Yaco Recroa

## Contexto y Declaración del Problema
Con la cota de tiempo del ADR-IT2-01, hay que definir qué se entrega cuando la respuesta fresca no llega a tiempo, y qué se entrega cuando una o más APIs externas no responden. Sin una política explícita, vencer la cota significaría un error o una espera indefinida para el viajero, justo en los picos de interrupciones de viaje en que más se usa el sistema.

## Impulsores de la Decisión (Decision Drivers)
* `QA-PER-02` y `QA-PER-03`: cerrar dentro de 800 ms y 1,4 s.
* `QA-DIS-01`: sostener las funciones críticas ante la falla de una API o de un nodo; el sistema debe acumular menos de 5 minutos de inactividad al mes.
* Es preferible una respuesta útil aunque incompleta o antigua a no responder.
* Una API caída no debe bloquear la cotización de las demás.

## Opciones Consideradas
* Opción 1: Graceful degradation en dos niveles: (a) la CDN entrega la copia que ya tiene al vencer la cota; (b) el Orquestador de viajes arma la grilla con los orígenes que respondieron y suelta los que no.
* Opción 2: Devolver error al vencer la cota.
* Opción 3: Extender la cota hasta que respondan todas las APIs.

## Resultado de la Decisión
Opción elegida: **"Opción 1: Graceful degradation en dos niveles"**, porque sostiene la función crítica (devolver una grilla o el primer contenido dentro de la cota) y suelta las no críticas (completitud y frescura), que es el equilibrio que exigen `QA-PER-02`, `QA-PER-03` y `QA-DIS-01`. Devolver error o extender la cota incumple directamente los umbrales de latencia.

Detalle:
* **CDN:** si la cota vence antes de la respuesta fresca, entrega la copia almacenada (grilla de fecha, hospedaje y compañía; o primer contenido móvil). Si la respuesta fresca llega después, actualiza la caché para consultas futuras.
* **Orquestador de viajes:** consolida la grilla con lo que devolvieron los adaptadores; si un adaptador informa que su origen no respondió, la grilla se devuelve parcial.

### Consecuencias Positivas (Beneficios)
* El viajero siempre recibe una respuesta dentro de la cota.
* La falla de un proveedor no tumba la cotización completa.
* Se sostiene la disponibilidad percibida durante picos y disrupciones.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Se perjudica la completitud y la frescura de la respuesta: precios o disponibilidad pueden estar desactualizados.
* Hace falta indicar en la interfaz que el dato puede no ser reciente y definir el tiempo de vida de las copias.
* Introduce un caso más a probar (respuesta por defecto vs. respuesta fresca).
