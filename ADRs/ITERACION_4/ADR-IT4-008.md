# Modificabilidad: Gestión manual de reservas en el Orquestador, idempotente, con origen y baja lógica

* **Estado:** aceptado
* **Fecha:** 2026-10-29
* **Decisores:** Mateo Garrido

## Contexto y Declaración del Problema
`REF-04` pide que el cliente agregue, actualice o elimine reservas a mano en el panel. Hasta ahora las reservas entran por las novedades de los proveedores y por el correo, y el modelo de reservas es polimórfico ([ADR-IT3-005](../ITERACION_3/ADR-IT3-005.md)). Hay que decidir dónde y cómo se hace la gestión manual, de modo que no abra un segundo camino de escritura y que los reintentos desde un móvil con red inestable no dupliquen reservas.

## Impulsores de la Decisión (Decision Drivers)
* `REF-04`: agregar, actualizar o eliminar reservas de forma manual.
* `QA-SEG-02`: registrar una actividad en un itinerario compartido es esta misma operación y exige autorización ([ADR-IT4-007](ADR-IT4-007.md)).
* `QA-EVO-01`: un tipo nuevo no debe tocar la agrupación por viaje.
* `REF-01`: lo eliminado sale de la vista principal, pero el historial no se pierde.

## Opciones Consideradas
* Opción 1: Operaciones de agregar, actualizar y eliminar en el Orquestador, sobre `Reserva`. Cada una pasa por el control de acceso, valida con la validación del tipo, lleva una clave de operación generada por el cliente para que un reintento no duplique, escribe con Transactions ([ADR-IT2-004](../ITERACION_2/ADR-IT2-004.md)) y marca el origen (manual, proveedor o correo). Eliminar es una baja lógica. Una actividad se modela como un tipo más, `ReservaActividad`. Una reserva modificada a mano no es sobrescrita por una novedad del proveedor: la novedad queda visible en "Novedades" para que el viajero decida.
* Opción 2: Un servicio propio de reservas manuales (rechazado como Split module en [ADR-IT3-011](../ITERACION_3/ADR-IT3-011.md)).
* Opción 3: Una nota libre sin tipo, fuera del modelo de reservas.
* Opción 4: Edición sin conexión en el cliente, con sincronización posterior.

## Resultado de la Decisión
Opción elegida: **"Opción 1: gestión manual en el Orquestador, sobre el modelo polimórfico"**, porque deja un único camino de escritura y de validación para las reservas, vengan de donde vengan. Los reintentos del móvil no duplican, la baja lógica conserva el historial que necesitan la auditoría y la analítica, y `ReservaActividad` es una clase más registrada en el Registro de tipos, sin cambios en la agrupación. La opción 2 repite el rechazo de la iteración 3. La opción 3 deja las reservas manuales fuera de la agrupación y del archivado de `REF-01`. La opción 4 obliga a resolver conflictos de edición, que ningún driver exige.

### Consecuencias Positivas (Beneficios)
* Un solo camino de escritura y de validación para reservas manuales, de proveedores y del correo.
* Un reintento con la misma clave de operación no duplica la reserva.
* La baja lógica preserva el historial para la auditoría y los informes de cancelaciones.
* `ReservaActividad` muestra que el Registro de tipos admite extensiones sin tocar la agrupación.

### Consecuencias Negativas (Trade-offs / Riesgos)
* La regla de precedencia puede ocultar un cambio real del proveedor hasta que el viajero lo revise. Requiere una interfaz para decidir.
* Hay que guardar las claves de operación y definir cuánto tiempo se conservan.
* La baja lógica acumula datos. La eliminación definitiva, por privacidad, queda por definir.
* Sin edición sin conexión: las altas y cambios manuales exigen red.
* `QA-EVO-01` habla de medios de transporte: `ReservaActividad` ilustra el mecanismo, pero no cuenta como medida.
* El Orquestador acumula otra responsabilidad ([ADR-IT3-011](../ITERACION_3/ADR-IT3-011.md)).
