# Disponibilidad: Retry con identificador único en la ruta asíncrona (reapertura)

* **Estado:** aceptado
* **Fecha:** 2026-10-28
* **Decisores:** Mateo Garrido

## Contexto y Declaración del Problema
En la iteración 2 se rechazó Retry porque los reintentos bloqueantes contra las APIs externas comprometían la cota de 800 ms de `QA-PER-02`. En la iteración 3 el contexto cambia: las novedades, el correo y las notificaciones viajan por una ruta asíncrona, sin un usuario esperando. En esa ruta los fallos transitorios (un proveedor que no responde, un canal caído, una cola llena, el traspaso del broker) son frecuentes y no deben perder mensajes, pero un reintento sin control puede duplicar reservas.

## Impulsores de la Decisión (Decision Drivers)
* `QA-PER-01`: no perder novedades y reflejarlas en 5 minutos.
* `REF-02` y `QA-SEG-03*`: las reservas del correo de usuarios autorizados no se pierden (100 %).
* `QA-INT-02`: los envíos por canal toleran fallos transitorios del canal.
* No duplicar reservas ni envíos.
* Los drivers no fijan la cantidad de reintentos: es propiedad de cada componente.

## Opciones Consideradas
* Opción 1: Retry acotado, con identificador único por mensaje e idempotencia en el consumidor, solo en la ruta asíncrona.
* Opción 2: Mantener el rechazo de la iteración 2 también en la ruta asíncrona (sin reintentos).
* Opción 3: Retry sin identificador único.

## Resultado de la Decisión
Opción elegida: **"Opción 1: Retry acotado con identificador único e idempotencia, solo en la ruta asíncrona"**, porque el motivo del rechazo de la iteración 2 (la cota de 800 ms con un usuario esperando) no aplica a esta ruta. Cada mensaje lleva un identificador único; el Servicio de ingesta y el Servicio de notificaciones descartan los duplicados. Esto compensa los mensajes que Bound queue sizes ([ADR-IT3-002](ADR-IT3-002.md)) pueda rechazar y los que queden en vuelo durante la Reconfiguration del broker. El rechazo de la iteración 2 sigue vigente para la ruta síncrona de cotización.

El identificador lo asigna **quien publica**, no el broker: el Adaptador de anuncios para cada novedad de Booking, el Adaptador de correo para cada mensaje del buzón (el `Message-ID` del correo, o un hash de su contenido si falta) y el Orquestador de viajes para cada pedido de envío. En la rama del correo ese identificador viaja con la reserva por el Parseo aislado ([ADR-IT3-007](ADR-IT3-007.md)) y el Filtro de remitentes ([ADR-IT3-008](ADR-IT3-008.md)) hasta la ingesta, que es la que descarta duplicados.

El alcance tiene un límite que conviene dejar escrito: el productor push no reintenta. El Adaptador de anuncios recibe un aviso que no puede reencolar, así que ante una cola llena responde una indisponibilidad y la reentrega queda a cargo de Booking ([ADR-IT3-002](ADR-IT3-002.md), [ADR-IT3-009](ADR-IT3-009.md)). Retry cubre la entrega **desde** las colas hacia adentro, no la llegada del aviso externo.

### Consecuencias Positivas (Beneficios)
* Se cubren los fallos transitorios de proveedores, canales y del broker sin intervención manual.
* Con identificador e idempotencia, un reintento no duplica reservas ni envíos.
* Cierra la cadena Use an intermediary + Bound queue sizes + Retry: la acotación de las colas deja de significar pérdida directa.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Los reintentos suman tiempo a la ruta y corren contra los 5 minutos de `QA-PER-01`; un backoff largo puede dejar a una novedad fuera de la medida.
* Cada reintento que llega a escribir pasa por el commit en dos fases de la iteración 2, con su costo en latencia.
* Hay que guardar los identificadores ya procesados (estado en la ingesta y en notificaciones) y definir cuánto tiempo se conservan.
* Una caída prolongada de un proveedor puede generar tormentas de reintentos si no se limita su cantidad y su frecuencia.
* Coexisten dos políticas (sin Retry en la ruta síncrona, con Retry en la asíncrona), que hay que documentar para no mezclarlas.
* Retry no alcanza al borde de entrada push: un aviso de Booking que llega con la cola llena o con el listener caído depende del reintento del proveedor, no del nuestro.
* El identificador del correo depende del `Message-ID` del proveedor; si un proveedor lo reescribe, el hash de contenido es el respaldo y puede confundir dos mensajes casi idénticos.
