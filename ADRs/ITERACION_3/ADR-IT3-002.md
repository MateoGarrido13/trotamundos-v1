# Performance: Bound queue sizes (colas acotadas)

* **Estado:** aceptado
* **Fecha:** 2026-10-28
* **Decisores:** Yaco Recroa

## Contexto y Declaración del Problema
Con el broker de [ADR-IT3-001](ADR-IT3-001.md), un pico de novedades, de correo o de envíos puede llenar las colas más rápido de lo que los consumidores las vacían. Una cola que crece sin límite agota memoria o disco del broker y retrasa todos los mensajes que vienen detrás, comprometiendo el tiempo de actualización. Hay que decidir qué pasa cuando una cola alcanza su capacidad.

## Impulsores de la Decisión (Decision Drivers)
* `QA-PER-01`: la novedad debe verse en 5 minutos como máximo desde la detección.
* `QA-INT-02`: los envíos por canales no deben acumularse indefinidamente.
* `QA-SEG-03*`: la medida del 100 % de reservas de usuarios autorizados no tolera pérdidas silenciosas.
* Los drivers no fijan el tamaño de cada cola: es un parámetro de cada una, a definir con pruebas de carga.

## Opciones Consideradas
* Opción 1: Bound queue sizes: cada cola tiene un tamaño máximo; al llenarse, la respuesta depende del tipo de productor (contrapresión para los que sondean, rechazo explícito para los que reciben un aviso push), se avisa a operaciones y lo que agota sus reintentos va a una cola de mensajes muertos.
* Opción 2: Colas sin límite.
* Opción 3: Colas acotadas que descartan los mensajes nuevos o los más antiguos al llenarse (load shedding).

## Resultado de la Decisión
Opción elegida: **"Opción 1: colas acotadas, con la reacción a la saturación definida por tipo de productor"**, porque pone un techo a lo que el broker retiene y hace visible la saturación en lugar de ocultarla: el broker no descarta mensajes por decisión propia.

La reacción no puede ser la misma para los tres productores, y eso es parte de la decisión:

* **Productor que sondea (Adaptador de correo).** Tiene contrapresión gratuita: si la cola de correo está llena no publica y vuelve en el sondeo siguiente. No hay pérdida.
* **Productor que recibe un aviso push (Adaptador de anuncios).** No puede reencolar por su cuenta un aviso que ya consumió, así que responde a Booking una indisponibilidad y delega en él la reentrega ([ADR-IT3-009](ADR-IT3-009.md)). Si Booking no reintenta, la novedad se pierde y queda registrada en el aviso a operaciones.
* **Productor interno (Orquestador de viajes, cola de notificaciones).** Reintenta con el mismo identificador ([ADR-IT3-003](ADR-IT3-003.md)).

El mensaje que agota sus reintentos no se descarta en silencio: va a una cola de mensajes muertos, con aviso a operaciones.

### Consecuencias Positivas (Beneficios)
* El broker no crece sin límite en un pico; el backlog máximo queda acotado y, con él, el retraso máximo de un mensaje.
* Una cola saturada no arrastra al resto del broker.
* La saturación genera un aviso temprano a operaciones.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Si la cola se desborda, los mensajes se retrasan: puede romperse el límite de 5 minutos de `QA-PER-01`.
* La ruta de novedades depende de un tercero: si la cola se llena y Booking no reintenta, la novedad se pierde. Es el precio del push ([ADR-IT3-009](ADR-IT3-009.md)) y no se cubre con reintentos propios.
* Lo que agota sus reintentos queda en la cola de mensajes muertos y no llega al itinerario, lo que acota pero no elimina la tensión con el 100 % de `QA-SEG-03*`; en la ruta del correo la contrapresión del sondeo evita que eso ocurra por saturación.
* La cola de mensajes muertos es una pieza más que hay que vaciar, con su procedimiento de reproceso.
* El tamaño correcto de cada cola exige pruebas de carga; uno chico produce rechazos innecesarios y uno grande diluye el efecto de la táctica.
* Requiere monitoreo y alertas por cola, y un procedimiento de operación para el aviso.
