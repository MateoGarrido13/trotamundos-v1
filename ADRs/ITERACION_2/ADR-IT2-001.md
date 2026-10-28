# Aplicar Bound execution times en la Caché de borde (CDN) para cerrar dentro de 800 ms y 1,4 s

* **Estado:** aceptado
* **Fecha:** 2026-10-28
* **Decisores:** Mateo Garrido

## Contexto y Declaración del Problema
La iteración 1 incorporó la Caché de borde (CDN) (táctica *Múltiples copias de datos*) en el camino de Cliente web y Cliente móvil, antes del API Gateway, pero dejó parcial `QA-PER-02` y `QA-PER-03`. La cotización web debe responder en 800 ms para el 90 % de las peticiones y la aplicación móvil debe mostrar el primer contenido en menos de 1,4 s en el 90 % de las sesiones. Ante un *cache miss*, la cotización recorre API Gateway, Balanceador de Carga, Orquestador de viajes y tres APIs externas fuera de nuestro control, por lo que nada garantiza hoy que el tiempo de respuesta se mantenga dentro de las cotas. Hay que decidir qué componente impone el techo de tiempo y con qué valores.

## Impulsores de la Decisión (Decision Drivers)
* `QA-PER-02`: nueva cotización desde la web en 800 ms para el 90 % de las peticiones.
* `QA-PER-03`: primer contenido del móvil en menos de 1,4 s en el 90 % de las sesiones.
* Las APIs de proveedores (SOAP/REST) son externas y su latencia no es controlable.
* La CDN ya está en el camino de ambos clientes y es el único punto que ve el tiempo total de punta a punta.

## Opciones Consideradas
* Opción 1: Bound execution times en la Caché de borde (CDN), con cota de 800 ms para la cotización y de 1,4 s para el primer contenido móvil.
* Opción 2: Bound execution times solo en el Orquestador de viajes, sin cota en el borde.
* Opción 3: Sin cota explícita; confiar en el rendimiento de la infraestructura y en el escalado.

## Resultado de la Decisión
Opción elegida: **"Opción 1: Bound execution times en la Caché de borde (CDN)"**, porque es el único elemento que observa el tiempo total percibido por el cliente (incluyendo API Gateway, Balanceador de Carga, Orquestador de viajes y adaptadores) y puede cortar la espera y responder aunque cualquiera de esos tramos se demore. Una cota solo en el orquestador no cubre la latencia del tramo hacia el borde ni el caso móvil, y no tener cota deja `QA-PER-02` y `QA-PER-03` libradas a terceros.

La cota se abre al recibir el pedido: 800 ms en la cotización (`QA-PER-02`) y 1,4 s en el primer contenido del móvil (`QA-PER-03`). Al vencer la cota se aplica la respuesta por defecto definida en ADR-IT2-02. Las cotas de espera de cada API no son las del goal, sino las de su adaptador (ADR-IT2-03).

### Consecuencias Positivas (Beneficios)
* Se garantiza acotar el tiempo de respuesta percibido, cumpliendo `QA-PER-02` y `QA-PER-03`.
* Una única política de tiempo en el borde sirve a la web y al móvil.
* El retorno tardío del dato fresco sigue actualizando la caché para consultas futuras.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Se sacrifica la exactitud del cómputo: la respuesta por defecto puede estar desactualizada, lo que perjudica la consistencia de los datos mostrados.
* La CDN pasa a concentrar lógica de temporización que debe configurarse y monitorearse (porcentaje de respuestas por defecto, percentil 90 de latencia).
* Cotas fijas de 800 ms y 1,4 s dejan poco margen: requieren validarse con pruebas de carga.
