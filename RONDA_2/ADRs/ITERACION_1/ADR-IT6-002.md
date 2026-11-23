# Seguridad y Modificabilidad: Resolución de primer nivel reutilizando las operaciones autorizadas e idempotentes del Orquestador de viajes

* **Estado:** aceptado
* **Fecha:** 2026-11-17
* **Decisores:** Yaco Recroa

## Contexto y Declaración del Problema
Cuando el viajero pide al Asistente Virtual (`REF-07`) consultar el estado de su viaje, reprogramar una reserva o resolver un problema menor (por ejemplo cambiar horario/fecha o dar de baja una reserva), el bot debe leer o modificar datos de viajes y reservas. En la iteración 4 se decidió que toda lectura o escritura sobre un itinerario pase por el Módulo de control de acceso y auditoría ([ADR-IT4-007](../../../RONDA_1/ADRs/ITERACION_4/ADR-IT4-007.md)) y que toda modificación manual de una reserva use las operaciones idempotentes del Orquestador con clave de operación, validación polimórfica y baja lógica ([ADR-IT4-008](../../../RONDA_1/ADRs/ITERACION_4/ADR-IT4-008.md)). Hay que decidir cómo ejecuta el Asistente Virtual las acciones de primer nivel sin abrir un segundo camino de acceso a los datos ni saltear permisos.

## Impulsores de la Decisión (Decision Drivers)
* `REF-07`: gestionar reprogramaciones, consultas de estado y problemas menores en el primer nivel de soporte.
* `QA-SEG-02`: un participante sin permiso sobre un itinerario compartido no puede modificar ni registrar actividades a través del bot; el 100 % de las decisiones debe validarse y registrarse en la auditoría transaccional.
* `REF-04`: mantener un único camino de validación, clave de idempotencia, marca de `origen` y baja lógica para toda modificación de `Reserva`.

## Opciones Consideradas
* Opción 1: El Módulo de Asistente Virtual **nunca accede a la Base de viajes**. Traduce la intención de primer nivel del usuario en una llamada a las operaciones existentes del Orquestador de viajes (consulta de viaje/novedades, `agregarReserva`, `actualizarReserva(id)`, `eliminarReserva(id)`), propagando la identidad verificada del usuario y una clave de operación asociada al turno de conversación. El Orquestador ejecuta `verificarPermiso`, valida el subtipo de `Reserva`, escribe con commit en dos fases y deja el asiento de auditoría en la misma transacción.
* Opción 2: Que el Módulo de Asistente Virtual se conecte por JDBC directamente a la Base de viajes para leer estados y aplicar reprogramaciones ([ADR-IT6-005](ADR-IT6-005.md)).

## Resultado de la Decisión
Opción elegida: **"Opción 1: invocar al Orquestador de viajes propagando la identidad del actor y clave de operación"**, porque preserva al Orquestador como único dueño de la Base de viajes y garantiza por construcción que nadie pueda usar el chatbot para eludir los permisos de un itinerario compartido (`QA-SEG-02`). Si un participante sin permiso pide al bot reprogramar o agregar una actividad en un viaje grupal, el Módulo de control de acceso del Orquestador lo rechaza y audita exactamente igual que si lo hubiera hecho desde la grilla manual. Además, la clave de operación evita que un reintento del chat aplique dos veces la misma reprogramación.

### Consecuencias Positivas (Beneficios)
* Cero duplicación de reglas de negocio, validación polimórfica de `Reserva`, control de acceso y auditoría.
* Imposibilidad de escalar privilegios en un itinerario compartido a través del chatbot (`QA-SEG-02`).
* Toda reprogramación hecha por el bot emite también el evento analítico hacia la quinta cola del Broker ([ADR-IT5-001](../../../RONDA_1/ADRs/ITERACION_5/ADR-IT5-001.md)).

### Consecuencias Negativas (Trade-offs / Riesgos)
* El Asistente Virtual depende de la disponibilidad del Orquestador de viajes para resolver acciones de primer nivel.
* Antes de ejecutar una acción de escritura (`actualizarReserva` o `eliminarReserva`), el Asistente debe pedir confirmación explícita en el diálogo para no disparar bajas lógicas por una intención mal interpretada.
