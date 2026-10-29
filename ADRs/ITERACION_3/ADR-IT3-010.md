# Despliegue: Servicio de ingesta y adaptadores de entrada en nodos propios

* **Estado:** aceptado
* **Fecha:** 2026-10-28
* **Decisores:** Santiago Otaño

## Contexto y Declaración del Problema
Hay dos tipos de adaptador: los de cotización (aerolíneas, hoteles, arrendadoras), que invoca el Orquestador en memoria mientras el usuario espera, y los de entrada (Booking y correo), que reciben o buscan datos por su cuenta. Junto con ellos aparece el Servicio de ingesta. Hay que decidir dónde se despliegan para que el pico de las 8 am no compita con las cotizaciones.

## Impulsores de la Decisión (Decision Drivers)
* `QA-PER-02`: la cotización conserva sus 800 ms.
* `QA-PER-01`: la ingesta debe sostener el pico y cerrar en 5 minutos.
* Evitar políticas de prioridad entre ingesta y cotización ([ADR-012](../ITERACION_1/ADR-012.md)).

## Opciones Consideradas
* Opción 1: Nodos propios para el Servicio de ingesta, el Adaptador de anuncios (Booking) y el Adaptador de correo; los adaptadores de cotización siguen con el Orquestador.
* Opción 2: Co-desplegar todo con el Orquestador de viajes.
* Opción 3: Un servicio independiente por cada adaptador de entrada.

## Resultado de la Decisión
Opción elegida: **"Opción 1: nodos propios para la ingesta y los adaptadores de entrada"**, porque separa por despliegue lo que compite por recursos: el pico de la ingesta no consume los nodos del Orquestador, y por eso se mantiene el rechazo de Prioritize events. Los adaptadores de cotización no se separan: hacerlo sumaría una llamada de red por cada cotización. El Servicio de ingesta no escribe en la base: entrega al Orquestador, que es dueño de lo que se guarda.

### Consecuencias Positivas (Beneficios)
* Aislamiento de recursos entre ingesta y cotización.
* La ingesta y los adaptadores de entrada escalan de forma independiente.
* Su único contacto con el resto del sistema es el broker (y, para la ingesta, el Orquestador).

### Consecuencias Negativas (Trade-offs / Riesgos)
* Más nodos y más costo operativo, de despliegue y de monitoreo.
* Dos modalidades de despliegue de adaptadores que el equipo debe mantener claras.
* El Orquestador sigue siendo el único punto de escritura, con commit en dos fases, y puede convertirse en un cuello de botella cuando la ingesta lo sature.
* Si se llegaran a compartir nodos, el rechazo de Prioritize events debería reabrirse.
