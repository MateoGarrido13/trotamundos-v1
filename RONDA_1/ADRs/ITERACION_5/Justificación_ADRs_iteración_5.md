# Trotamundos — Justificación de los ADRs de la iteración 5

*Método ADD · TPE Diseño de Sistemas de Software · 17 de noviembre de 2026*

Para cada ADR de la iteración 5 se indica por qué se eligió, qué se perdió y qué alternativa quedó más cerca de ganar. La base son los 5 ADRs (`ADR-IT5-001` a `ADR-IT5-005`) e [ITERACION_5.md](../../ITERACION_5.md).

## Camino de lectura analítico (`QA-PER-04*`, `REF-06`)

### ADR-IT5-001. Desacoplamiento del camino analítico con quinta cola del Broker, Proyector analítico en nodos propios y Base analítica separada

**Por qué.** `QA-PER-04*` y `REF-06` exigen procesar informes de tendencias, destinos y cancelaciones en menos de 10 segundos en promedio mientras el sistema opera con 15 millones de cuentas, 2 millones de usuarios activos semanales y picos de domingo a lunes, de jueves a viernes o de disrupciones climáticas. En una disrupción climática coinciden el pico de operaciones de los viajeros y el pico de consultas del equipo de datos. Publicar un evento analítico anonimizado en una quinta cola acotada del Broker y proyectarlo desde nodos propios hacia una Base analítica separada evita que una consulta pesada toque la Base de viajes o los nodos del Orquestador.

**Qué se paga.** Consistencia eventual en la Base analítica (del orden de segundos a pocos minutos según el backlog de la cola), un consumidor nuevo (Proyector analítico), una base más para operar y una quinta cola en el Broker.

**Qué alternativa quedó más cerca.** Un proceso ETL por lotes nocturno. Pierde porque deja al equipo de datos sin visibilidad del día en curso durante una disrupción de viajes y concentra una lectura pesada contra la Base de viajes cuando corre el lote.

### ADR-IT5-002. Preagregación incremental por destino, tendencia y cancelación con cota de 10 s en el Servicio de consultas analíticas

**Por qué.** A la escala de 15 millones de cuentas, tener una Base analítica separada no alcanza si cada informe escanea millones de reservas históricas desde cero. Como `REF-06` y `QA-PER-04*` fijan las dimensiones del informe (tendencias temporales, destinos tomados de `Reserva.lugar.destino` y cancelaciones tomadas de la baja lógica), el Proyector analítico actualiza series preagregadas de forma idempotente al consumir cada evento. Así el Servicio de consultas analíticas responde leyendo agregados ya calculados y aplica *Bound execution times* en 10 segundos.

**Qué se paga.** Cada evento escribe tanto el hecho atómico como los agregados, y agregar una dimensión nueva en el futuro requiere reprocesar el histórico de la Base analítica.

**Qué alternativa quedó más cerca.** Vistas materializadas recalculadas periódicamente en la Base analítica. Cumple también los 10 s, pero la actualización incremental por evento reparte el costo de forma uniforme en lugar de concentrarlo en picos de refresco.

### ADR-IT5-004. Ejecución de consultas analíticas directamente sobre la Base de viajes (primaria o pasiva) (rechazado)

Su ventaja sería no sumar ni la quinta cola ni la Base analítica. Se rechaza en sus dos variantes: sobre la Base primaria compite directamente con los 800 ms de `QA-PER-02` y con las escrituras de viajes; sobre la Base pasiva interfiere con el acuerdo síncrono del commit en dos fases ([ADR-IT2-004](../ITERACION_2/ADR-IT2-004.md)) y compromete la capacidad del nodo de respaldo para asumir la carga en menos de 5 minutos al mes ([ADR-IT2-005](../ITERACION_2/ADR-IT2-005.md), `QA-DIS-01`).

**Cuándo reabrirlo:** nunca mientras la Base de viajes sostenga el tráfico transaccional con commit en dos fases síncrono.

---

## Experiencia móvil con capacidad nativa GPS (`QA-USA-01`)

### ADR-IT5-003. Cálculo local de proximidad y ruta con GPS nativo en el Cliente móvil sobre `Reserva.lugar`, con carga diferida y degradación sin coordenadas

**Por qué.** `QA-USA-01` pide aprovechar capacidades nativas como el GPS cuando el viajero consulta su viaje en el móvil durante el viaje. Como la iteración 4 ya incorporó `lugar` (nombre, destino y coordenadas opcionales) al contrato `Reserva` ([ADR-IT4-009](../ITERACION_4/ADR-IT4-009.md)), el Cliente móvil dispone en memoria tanto de las coordenadas de cada reserva como del GPS nativo del dispositivo. Diferir la lectura del GPS hasta después del login preserva intacto el First Contentful Paint de 1,4 s en red 3G (`QA-PER-03`), calcular la distancia y destacar la reserva activa más cercana en el propio teléfono no suma llamadas al backend, y degradar a la vista cronológica cuando faltan coordenadas o permiso de ubicación evita bloqueos de uso.

**Qué se paga.** La precisión depende del GPS del teléfono y de que el viajero conceda el permiso del sistema operativo; sin coordenadas en `Reserva.lugar` solo se muestra nombre y destino textuales.

**Qué alternativa quedó más cerca.** Pedir la posición GPS al abrir la aplicación para precargarla antes del login. Pierde porque el diálogo de permisos y la inicialización del receptor GPS en frío bloquearían o demorarían el primer renderizado del formulario de login que mide `QA-PER-03` (< 1,4 s).

### ADR-IT5-005. Seguimiento continuo de la posición GPS del viajero en el servidor (rechazado)

Su ventaja sería habilitar geocercas o alertas iniciadas desde el backend. Se rechaza porque `QA-USA-01` ocurre cuando el viajero consulta su viaje en el móvil: transmitir de forma continua las coordenadas de 2 millones de usuarios activos semanales agotaría batería y datos en redes móviles lentas (`QA-PER-03`), cargaría innecesariamente al API Gateway y obligaría a resguardar un rastro sensible de ubicación física que ningún driver requiere.

**Cuándo reabrirlo:** solo si se incorporara un escenario de alertas automáticas en segundo plano basadas en ubicación y con consentimiento específico del viajero.
