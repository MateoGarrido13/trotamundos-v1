# Seguridad: Autorización por itinerario con roles de grupo y auditoría de cada decisión

* **Estado:** aceptado
* **Fecha:** 2026-10-29
* **Decisores:** Yaco Recroa

## Contexto y Declaración del Problema
`QA-SEG-02` describe a un participante autenticado de un viaje grupal que intenta registrar una actividad (por ejemplo la reserva de una excursión) en el itinerario compartido. El sistema debe validar sus permisos sobre ese itinerario, persistir la actividad, actualizar la vista de los demás miembros y registrar la transacción. Quien no tiene permiso es redirigido a una página de "Error 401". Los permisos de grupo están configurados de antemano. Hay que decidir dónde se autoriza, con qué modelo y cómo queda el rastro.

## Impulsores de la Decisión (Decision Drivers)
* `QA-SEG-02`: el 100 % de las solicitudes autorizadas se procesa y las demás se deniegan.
* `REF-04`: registrar una actividad es la misma operación que agregar una reserva a mano ([ADR-IT4-008](ADR-IT4-008.md)).
* `QA-PER-02`: la cotización no puede pagar una autorización que no necesita.
* El Orquestador de viajes no se divide ([ADR-IT3-011](../ITERACION_3/ADR-IT3-011.md)).

## Opciones Consideradas
* Opción 1: Un Módulo de control de acceso dentro del Orquestador. Guarda las membresías (itinerario, cuenta, rol) en la Base de viajes. Cada operación declara el permiso que exige (por ejemplo ver, registrar, modificar, administrar miembros) y se autoriza antes de ejecutarse, con denegación por defecto. Los roles iniciales son organizador y participante. Cada decisión, permitida o denegada, se registra en una auditoría de solo agregado, dentro de la misma transacción de la operación.
* Opción 2: Roles globales dentro del token de sesión.
* Opción 3: Autorizar en el API Gateway.
* Opción 4: Un motor de políticas externo, de atributos.

## Resultado de la Decisión
Opción elegida: **"Opción 1: Módulo de control de acceso en el Orquestador, con roles por itinerario y auditoría"**, porque la membresía de un itinerario es un dato del Orquestador, que es el dueño de lo que se guarda en la Base de viajes. Autorizar ahí permite validar contra el itinerario específico y hacerlo en la misma transacción que la escritura: no se persiste una actividad sin permiso y no hay actividad sin rastro. El Gateway ya autenticó al actor ([ADR-IT4-004](ADR-IT4-004.md)). Un rol global en el token no sabe a qué itinerario pertenece el actor y queda desactualizado al cambiar el grupo. El Gateway tendría que consultar el Core por cada pedido. Un motor externo es más de lo que el escenario necesita. El escenario nombra la página "Error 401" y el diseño la respeta: el Orquestador responde acceso denegado y el cliente la presenta.

### Consecuencias Positivas (Beneficios)
* Denegación por defecto: sin membresía y permiso explícitos, no hay operación.
* Autorización, escritura y auditoría son atómicas.
* No hay una llamada de red extra ni un componente nuevo.
* El escenario es testeable con una matriz de casos (rol por operación).

### Consecuencias Negativas (Trade-offs / Riesgos)
* Cada operación sobre un itinerario suma una lectura de membresía y una escritura de auditoría. La cotización no las paga.
* HTTP reserva el 401 para la falta de autenticación y el 403 para la falta de permiso. Se respeta el texto del escenario y queda pendiente decidir el código que viaja por la red.
* La matriz de roles y permisos se fija en el diseño detallado: los drivers solo nombran al participante.
* La auditoría crece sin límite y también registra los intentos denegados, que aumentan bajo ataque: su retención está por definir.
* Quitar a un miembro vale desde la siguiente operación, no sobre lo que ya tiene en pantalla o en su copia local ([ADR-IT4-014](ADR-IT4-014.md)).
* El Orquestador acumula una responsabilidad más. [ADR-IT3-011](../ITERACION_3/ADR-IT3-011.md) prevé reabrir la división si se vuelve un cuello de botella.
