# Modificabilidad: Extensión del contrato `Reserva` con el lugar de la reserva

* **Estado:** aceptado
* **Fecha:** 2026-10-29
* **Decisores:** Ramiro Rossi

## Contexto y Declaración del Problema
`Reserva` expone identificador, viaje, fechas, estado y resumen ([ADR-IT3-005](../ITERACION_3/ADR-IT3-005.md)). No dice dónde ocurre la reserva. Tres consumidores nuevos lo necesitan: la analítica, que agrupa por destino (`REF-06`); la app móvil, que calcula distancia y ruta contra la posición del dispositivo (`QA-USA-01`); y la carga manual, donde el viajero indica el lugar (`REF-04`). Hay que decidir cómo se expone.

## Impulsores de la Decisión (Decision Drivers)
* `REF-06`: tendencias, destinos y cancelaciones.
* `QA-USA-01`: una interfaz que aprovecha el GPS necesita las coordenadas de lo que muestra.
* `REF-04`: una reserva manual tiene que poder indicar su lugar.
* `QA-EVO-01`: la agrupación por viaje no cambia.

## Opciones Consideradas
* Opción 1: Agregar a `Reserva` el atributo `lugar` (nombre, destino y coordenadas cuando se conocen). Cada tipo concreto lo completa.
* Opción 2: Una interfaz separada, `IUbicable`, que implementan solo los tipos con lugar.
* Opción 3: No tocar `Reserva` y obtener el lugar fuera del modelo, interpretando el resumen.

## Resultado de la Decisión
Opción elegida: **"Opción 1: `lugar` como parte del contrato `Reserva`"**, porque todos los tipos tienen un lugar (aeropuerto, hotel, punto de retiro, estación, actividad) y los tres consumidores lo leen de la misma forma. Con una interfaz aparte habría que preguntar por el tipo antes de usarla, que es lo que el polimorfismo evita. Interpretar el resumen ata a los consumidores a su formato.

### Consecuencias Positivas (Beneficios)
* Analítica, móvil y carga manual leen el lugar por el mismo contrato.
* Un tipo nuevo declara su lugar al implementar `Reserva`, sin tocar a los consumidores.

### Consecuencias Negativas (Trade-offs / Riesgos)
* `Reserva` es un contrato crítico ([ADR-IT3-005](../ITERACION_3/ADR-IT3-005.md)): agregarle un atributo obliga a actualizar todos los tipos existentes.
* Las coordenadas pueden faltar, sobre todo en reservas manuales o en las que no las traen. Los consumidores tienen que tolerarlo: la vista móvil sin coordenadas se muestra sin distancia ni ruta.
* Obtener coordenadas que no vienen en la reserva (geocodificación) exigiría un servicio externo. No se decide acá. Si hiciera falta, sería un proveedor más detrás de `IProveedor`.
* El lugar de una reserva es información sensible del itinerario: su exposición queda sujeta a la autorización del itinerario ([ADR-IT4-007](ADR-IT4-007.md)).
