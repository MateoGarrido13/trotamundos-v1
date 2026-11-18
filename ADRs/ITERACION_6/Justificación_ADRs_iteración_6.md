# Trotamundos — Justificación de los ADRs de la iteración 6

*Método ADD · TPE Diseño de Sistemas de Software · 17 de noviembre de 2026*

Para cada ADR de la iteración 6 se indica por qué se eligió, qué se perdió y qué alternativa quedó más cerca de ganar. La base son los 5 ADRs (`ADR-IT6-001` a `ADR-IT6-005`) e [ITERACION_6.md](../../ITERACION_6.md), correspondientes a la incorporación del requerimiento funcional avanzado obligatorio de la segunda entrega (**Opción B — Asistente Virtual / Chatbot**, `REF-07`).

## Asistente Virtual de primer nivel y escalamiento a la agencia (`REF-07`)

### ADR-IT6-001. Módulo de Asistente Virtual en nodos propios, desacoplado de los nodos de cotización

**Por qué.** El pico de uso del Asistente Virtual ocurre exactamente durante disrupciones masivas de viajes (mal clima, cancelaciones en cadena), cuando los viajeros buscan reprogramar o consultar el estado de sus reservas. Si el procesamiento conversacional corriera en los mismos nodos del Orquestador de viajes, ese pico competiría por CPU y memoria con las cotizaciones de 800 ms (`QA-PER-02`). Desplegar el Módulo de Asistente Virtual en nodos propios sin estado detrás del API Gateway repite el patrón probado en la ingesta ([ADR-IT3-010](../ITERACION_3/ADR-IT3-010.md)) y en el registro ([ADR-IT4-002](../ITERACION_4/ADR-IT4-002.md)).

**Qué se paga.** Un grupo más de nodos para desplegar y monitorear, y una llamada HTTP interna desde el Asistente hacia el Orquestador cuando el diálogo ejecuta una consulta o modificación sobre el viaje.

**Qué alternativa quedó más cerca.** Desplegar el Asistente dentro del Orquestador con colas internas de prioridad. Pierde porque la separación por despliegue ya fue la táctica elegida en las iteraciones 3 y 4 para evitar reabrir la priorización de recursos ([ADR-012](../ITERACION_1/ADR-012.md)).

### ADR-IT6-002. Resolución de primer nivel reutilizando las operaciones autorizadas e idempotentes del Orquestador de viajes

**Por qué.** `REF-07` pide que el bot resuelva en primer nivel consultas de estado, reprogramaciones y problemas menores. En lugar de que el bot tenga su propia lógica de persistencia, traduce la intención del usuario en llamadas a las operaciones que el Orquestador ya expone (`agregarReserva`, `actualizarReserva(id)`, `eliminarReserva(id)` y consulta de itinerario/novedades, [ADR-IT4-008](../ITERACION_4/ADR-IT4-008.md)), propagando la identidad verificada del actor y una clave de operación del turno. Así se cumplen automáticamente la validación de permisos y auditoría en la misma transacción de `QA-SEG-02` ([ADR-IT4-007](../ITERACION_4/ADR-IT4-007.md)), la validación polimórfica de `Reserva` (`QA-EVO-01`) y la emisión del evento analítico (`REF-06`).

**Qué se paga.** El Asistente requiere pedir confirmación explícita al usuario antes de disparar una modificación o baja sobre el Orquestador para evitar ediciones accidentales por mala interpretación.

**Qué alternativa quedó más cerca.** Un conjunto de procedimientos almacenados o endpoints especiales para el bot sin clave de operación. Pierde porque un reintento de mensaje en el chat duplicaría cambios y abriría una vía paralela de validación.

### ADR-IT6-003. Escalamiento de casos complejos del Asistente Virtual a la agencia preferida mediante la cola de casos de ayuda e `IAgencia`

**Por qué.** La segunda mitad de `REF-07` pide delegar a la agencia de viajes preferida únicamente aquellos casos complejos. La iteración 4 ya había resuelto `REF-05` con la cuarta cola del Broker (cola de casos de ayuda) y el Adaptador de agencia detrás de `IAgencia` ([ADR-IT4-010](../ITERACION_4/ADR-IT4-010.md)). El Asistente Virtual actúa como filtro inteligente delante de ese canal: resuelve en el acto lo simple contra el Orquestador y, cuando detecta un caso complejo (reembolsos, tramos encadenados con penalidad, proveedor sin respuesta o pedido explícito del viajero), invoca la apertura de caso adjuntando el resumen del diálogo y la reserva afectada.

**Qué se paga.** Si el clasificador interpreta como simple algo que el viajero considera complejo, hace falta ofrecer siempre la acción explícita "derivar a mi agencia" para escalar sin fricción.

**Qué alternativa quedó más cerca.** Encolar directamente desde el Asistente Virtual en el Broker sin pasar por el Orquestador. Pierde porque el Orquestador es el dueño del estado del caso ("en trámite") en la Base de viajes y quien valida que el viajero tenga permiso sobre ese itinerario.

### ADR-IT6-004. Contrato `IMotorConversacional` (ACL) con cota de espera y degradación a menú guiado

**Por qué.** Un motor de lenguaje natural externo o interno puede demorarse o caer. Encapsularlo detrás del contrato `IMotorConversacional` con *Bound execution times* y *Graceful degradation* ([ADR-IT2-001](../ITERACION_2/ADR-IT2-001.md), [ADR-IT2-002](../ITERACION_2/ADR-IT2-002.md)) permite que, si el motor no responde a tiempo, el Asistente degrade a un menú guiado de opciones de primer nivel (consultar estado / reprogramar / derivar a agencia) y el soporte nunca quede fuera de línea (`QA-DIS-01`).

**Qué se paga.** En modo degradado se pierde la entrada en lenguaje libre a cambio de sostener el 100 % de las funciones de `REF-07`.

**Qué alternativa quedó más cerca.** Reintentar contra el motor de lenguaje antes de responder. Pierde por el mismo motivo que en la iteración 2 ([ADR-IT2-006](../ITERACION_2/ADR-IT2-006.md)): el usuario está esperando en una conversación interactiva.

### ADR-IT6-005. Acceso directo del Asistente Virtual a la Base de viajes o a la API de la agencia (rechazado)

Su ventaja habría sido ahorrar el salto interno hacia el Orquestador de viajes. Se rechaza porque rompe la propiedad exclusiva del Orquestador sobre la Base de viajes, permite saltear el Módulo de control de acceso y su auditoría transaccional (`QA-SEG-02`) y reintroduce llamadas síncronas a la agencia preferida ([ADR-IT4-014](../ITERACION_4/ADR-IT4-014.md)).

**Cuándo reabrirlo:** nunca sobre la base de datos de otro componente; si el Orquestador se dividiera en el futuro ([ADR-IT3-011](../ITERACION_3/ADR-IT3-011.md)), el Asistente consumiría la interfaz del servicio resultante.
