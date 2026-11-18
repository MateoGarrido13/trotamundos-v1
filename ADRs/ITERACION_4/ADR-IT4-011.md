# Seguridad: Revocación de membresía en un itinerario efectiva desde la operación siguiente

* **Estado:** aceptado
* **Fecha:** 2026-10-29
* **Decisores:** Yaco Recroa

## Contexto y Declaración del Problema
[ADR-IT4-007](ADR-IT4-007.md) define las membresías por itinerario (`itinerario`, `cuenta`, `rol`) dentro de la Base de viajes, donde el rol de organizador administra a los miembros del grupo. Cuando un organizador quita a un participante de un viaje compartido, ese participante puede tener el itinerario abierto en pantalla o una copia en caché local de lecturas previas. Hay que decidir cuál es el alcance de la revocación de esa membresía y si el sistema fuerza la invalidación inmediata de las pantallas abiertas.

## Impulsores de la Decisión (Decision Drivers)
* `QA-SEG-02`: el 100 % de las solicitudes de registro o modificación sin permiso deben ser rechazadas y redirigidas a la página de "Error 401", registrando la transacción.
* `QA-PER-02`: no sumar canales de estado persistentes ni consultas adicionales al camino crítico de lectura y cotización.
* Mantener el Orquestador de viajes sin estado de sesión de cliente conectado ([ADR-002](../ITERACION_1/ADR-002.md), [ADR-IT4-004](ADR-IT4-004.md)).

## Opciones Consideradas
* Opción 1: La baja de membresía se persiste de inmediato en la Base de viajes con su asiento de auditoría y rige desde la **operación siguiente** que intente ese usuario: toda lectura o escritura posterior pasa por `verificarPermiso` y es denegada por defecto. No se invalida en tiempo real lo que el cliente ya renderizó en memoria.
* Opción 2: Mantener un canal permanente (WebSocket) desde el Orquestador hacia cada cliente con un itinerario abierto para borrar la pantalla en el instante en que se revoca la membresía.
* Opción 3: Impedir que se quite a un miembro una vez que fue agregado al itinerario compartido.

## Resultado de la Decisión
Opción elegida: **"Opción 1: revocación efectiva desde la operación siguiente"**, porque el estímulo y la medida de `QA-SEG-02` operan por solicitud ("intento de registrar una nueva actividad... en el 100 % de las solicitudes autorizadas son procesadas, no así para aquellos que no posean permisos"). Como el Módulo de control de acceso valida cada operación contra la Base de viajes con denegación por defecto ([ADR-IT4-007](ADR-IT4-007.md)), apenas la baja de membresía confirma su transacción, cualquier intento ulterior de ver o registrar actividades es rechazado y auditado. La opción 2 introduce estado de conexión en los nodos del Orquestador, complicando el balanceo y el failover de `QA-DIS-01` para cubrir un dato que el ex-participante ya vio antes de ser removido. La opción 3 deja al organizador sin forma de corregir un alta errónea en el grupo.

### Consecuencias Positivas (Beneficios)
* Los nodos del Orquestador siguen siendo idénticos y sin estado de cliente conectado.
* Cualquier operación posterior a la revocación es rechazada en el 100 % de los casos y queda registrada en la auditoría.
* No agrega infraestructura de push síncrono hacia los clientes.

### Consecuencias Negativas (Trade-offs / Riesgos)
* El participante removido conserva en su pantalla lo que ya había cargado antes de la baja hasta que recargue la vista o intente operar, momento en el que recibe el rechazo ("Error 401").
* Lo que el participante ya vio o copió mientras tenía permiso legítimo no puede deshacerse técnicamente.
