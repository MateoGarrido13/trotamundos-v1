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
* Opción 1: Nodos propios ("nodos de entrada") para el Servicio de ingesta, el Adaptador de anuncios (Booking), el Adaptador de correo, el Parseo aislado y el Gestor de autorización del correo; los adaptadores de cotización siguen con el Orquestador.
* Opción 2: Co-desplegar todo con el Orquestador de viajes.
* Opción 3: Un servicio independiente por cada adaptador de entrada.

## Resultado de la Decisión
Opción elegida: **"Opción 1: nodos propios para la ingesta y los adaptadores de entrada"**, porque separa por despliegue lo que compite por recursos: el pico de la ingesta no corre en los nodos del Orquestador. Los adaptadores de cotización no se separan: hacerlo sumaría una llamada de red por cada cotización. El Servicio de ingesta no escribe en la base: entrega al Orquestador, que es dueño de lo que se guarda.

El reparto completo de esos nodos es: el Parseo aislado corre ahí como proceso separado, sin token y sin acceso a la base ([ADR-IT3-007](ADR-IT3-007.md)); el Gestor de autorización del correo también, junto al Adaptador de correo, porque le pasa el token por llamada en memoria ([ADR-IT3-006](ADR-IT3-006.md)).

El aislamiento que da el despliegue es parcial y conviene no exagerarlo: la ingesta entrega al Orquestador, que comparte nodos con la cotización. Por eso la decisión incluye un **límite de tasa de entrega de la ingesta al Orquestador**, para que el pico de las 8 am no consuma los nodos que atienden los 800 ms de `QA-PER-02`. Es ese límite, y no solo la separación de nodos, lo que sostiene el rechazo de Prioritize events.

### Consecuencias Positivas (Beneficios)
* Aislamiento de recursos entre ingesta y cotización.
* La ingesta y los adaptadores de entrada escalan de forma independiente.
* Su contacto con el resto del sistema es el broker, con dos excepciones explícitas: el Servicio de ingesta entrega al Orquestador de viajes, y el Gestor de autorización lee y escribe los tokens cifrados en la base.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Más nodos y más costo operativo, de despliegue y de monitoreo.
* Dos modalidades de despliegue de adaptadores que el equipo debe mantener claras.
* El Gestor de autorización es la única pieza de los nodos de entrada con acceso a la base, y lo que guarda son tokens: esos nodos, expuestos a entrada externa, pasan a tener una ruta a datos sensibles. Se acota a la tabla de tokens y se apoya en el cifrado de [ADR-IT3-006](ADR-IT3-006.md).
* El límite de tasa protege a la cotización pero alarga la ingesta: con el límite activo, el backlog se drena más despacio y corre contra los 5 minutos de `QA-PER-01`.
* El Orquestador sigue siendo el único punto de escritura, con commit en dos fases, y puede convertirse en un cuello de botella cuando la ingesta lo sature.
* Si se llegaran a compartir nodos, el rechazo de Prioritize events debería reabrirse.
