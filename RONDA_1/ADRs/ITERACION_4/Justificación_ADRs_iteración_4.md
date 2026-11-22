# Trotamundos — Justificación de los ADRs de la iteración 4

*Método ADD · TPE Diseño de Sistemas de Software · 29 de octubre de 2026*

Para cada ADR de la iteración 4 se indica por qué se eligió, qué se perdió y qué alternativa quedó más cerca de ganar. La base son los 14 ADRs (`ADR-IT4-001` a `ADR-IT4-014`) e [ITERACION_4.md](../../ITERACION_4.md).

## Identidad regional y escalabilidad del alta (`QA-ESC-01`)

### ADR-IT4-001. Partición geográfica de las cuentas por región de origen (vs. par único, réplicas de lectura y base distribuida síncrona)

**Por qué.** `QA-ESC-01` pide 100.000 altas diarias sostenidas desde tres continentes con confirmación en menos de 2 segundos independientemente del continente de origen y 0 rechazos por saturación o timeout. La iteración 2 había fijado que cada escritura confirma con un commit en dos fases ([ADR-IT2-004](../ITERACION_2/ADR-IT2-004.md)). Como una alta es una escritura, ni las réplicas de lectura ni un único par central evitan el cruce intercontinental. Particionar las cuentas en tres regiones (América, EMEA, APAC), cada una con su par primaria/pasiva local, mantiene el commit en dos fases dentro de la región y multiplica por tres la capacidad de escritura.

**Qué se paga.** Tres despliegues y tres pares de bases para operar, la cuenta queda atada a su región de origen (autenticarse desde otro continente paga ese enlace) y la unicidad global del correo electrónico deja de ser inmediata.

**Qué alternativa quedó más cerca.** Asignar la región por hash del correo (evaluada en [ADR-IT4-003](ADR-IT4-003.md)), porque resuelve la unicidad sin consultas cruzadas, pero pierde porque un viajero puede caer por hash en un continente lejano y vuelve a pagar el enlace transoceánico durante el alta.

### ADR-IT4-002. Módulo de registro y autenticación en nodos propios, con Base de cuentas propia y escalado horizontal elástico

**Por qué.** En la iteración 1 el registro compartía clúster con el Orquestador de viajes y escribía en la misma Base primaria que los viajes. Bajo el pico de lanzamiento de `QA-ESC-01`, las altas competirían por CPU, conexiones y locks de commit en dos fases contra las cotizaciones de 800 ms (`QA-PER-02`). Separar tanto los nodos (con escalado horizontal sin estado) como la base (Base de cuentas separada de la Base de viajes) elimina esa contención por construcción, igual que hizo [ADR-IT3-010](../ITERACION_3/ADR-IT3-010.md) con la ingesta.

**Qué se paga.** Más nodos y más bases para monitorear, y la relación entre una cuenta y sus viajes deja de ser una clave foránea del motor para sostenerse en la aplicación mediante el identificador de cuenta con prefijo de región.

**Qué alternativa quedó más cerca.** Aislar solo los nodos de registro manteniendo una sola base compartida. Pierde porque el cuello de botella real del alta es la escritura con commit en dos fases, no el cómputo de la petición.

### ADR-IT4-003. Enrutamiento por región y unicidad de cuentas entre regiones, acotada y reconciliada

**Por qué.** Al particionar por continente de origen, dos regiones distintas podrían recibir el mismo correo casi al mismo tiempo. Consultar a las otras dos regiones en paralelo por la huella del correo, con una cota de espera (*Scatter-Gather* + *Bound execution times*), detecta los duplicados habituales sin sumar un directorio global replicado. Y si una región no responde dentro de la cota, *Graceful degradation* permite completar el alta marcando "unicidad pendiente" y reconciliar luego con *Retry* asíncrono, cumpliendo el "0 rechazos por timeout" de `QA-ESC-01`.

**Qué se paga.** La unicidad pasa a ser eventual: existe una ventana acotada en la que dos altas simultáneas en distintos continentes con el mismo correo son aceptadas y una de ellas debe ser reconciliada después.

**Qué alternativa quedó más cerca.** Un directorio global replicado de `huella_correo -> región`. Con tres regiones cuesta más mantener la replicación de ese directorio que disparar dos consultas acotadas en paralelo durante el alta.

### ADR-IT4-004. Sesión con token firmado y de vida corta, validado en el API Gateway

**Por qué.** En la iteración 1 el API Gateway validaba la sesión consultando al Módulo de registro en cada pedido. Con las cuentas particionadas en tres continentes, mantener ese esquema metería un salto intercontinental en cada cotización de `QA-PER-02` (800 ms) y haría que la caída de una región impida cotizar a sus usuarios. Emitir un token de acceso firmado de vida corta en la misma respuesta del alta (más un token de renovación revocable en la Base de cuentas) permite que el Gateway valide la firma localmente con las claves públicas regionales, sin llamadas de red, y habilita el inicio de sesión inmediato que pide `QA-ESC-01`.

**Qué se paga.** La revocación de un token de acceso no es instantánea: sigue siendo válido hasta que expira su vida corta. Además hay que distribuir y rotar las claves públicas de las regiones en los nodos del Gateway.

**Qué alternativa quedó más cerca.** Replicar las sesiones activas en todos los bordes. Suma sincronización continua de estado para un problema que la firma criptográfica resuelve sin estado.

### ADR-IT4-012. Base de cuentas distribuida entre regiones con confirmación síncrona (rechazado)

Su ventaja habría sido conservar una única vista global de cuentas sin ventana de unicidad eventual. Se rechaza porque confirmar cada escritura de forma síncrona entre tres continentes reintroduce en el camino crítico del alta la latencia transoceánica que [ADR-IT2-004](../ITERACION_2/ADR-IT2-004.md) ya había descartado, y convierte la caída de una región en una indisponibilidad global de altas.

**Cuándo reabrirlo:** solo si una restricción regulatoria prohibiera cualquier ventana de reconciliación de correo y se relajaran la cota de 2 segundos y la tolerancia a fallos regionales.

---

## Seguridad del login y de los itinerarios compartidos (`QA-SEG-01`, `QA-SEG-02`)

### ADR-IT4-005. Limitación de tasa en el API Gateway y aislamiento del endpoint de recuperación

**Por qué.** `QA-SEG-01` plantea una ráfaga de 50 solicitudes simultáneas de recuperación de contraseña contra un mismo endpoint y exige mantener activo el servicio de login para los usuarios legítimos. Aplicar un cupo por endpoint y origen en el API Gateway frena el volumen en el borde antes de consumir recursos de negocio, y asignar al flujo de recuperación un grupo de recursos separado del login garantiza que, aunque pasen solicitudes dentro del cupo, nunca agoten los hilos ni las conexiones del inicio de sesión.

**Qué se paga.** Un origen compartido (por ejemplo un NAT de aeropuerto o hotel) puede alcanzar el cupo y demorar la recuperación de un viajero legítimo, y los contadores entre copias del Gateway tienen consistencia aproximada.

**Qué alternativa quedó más cerca.** Limitar únicamente dentro del Módulo de registro y autenticación. Pierde porque para cuando el servicio evalúa el límite, la ráfaga ya atravesó el borde y consumió conexiones internas.

### ADR-IT4-006. Recuperación de contraseña con token de un solo uso, respuesta uniforme y aviso al titular

**Por qué.** Como las 50 solicitudes de `QA-SEG-01` son **simultáneas**, un contador de tasa distribuido puede dejar pasar más de una en carrera. La garantía fuerte la da una actualización atómica en la Base de cuentas que admite **un solo pedido de recuperación vigente por cuenta**: de 50 solicitudes concurrentes, a lo sumo una genera token y encola correo. El token es aleatorio, de un solo uso, con vencimiento, se guarda como hash y se envía únicamente al buzón registrado del titular, mientras el endpoint devuelve una respuesta uniforme exista o no la cuenta. Además se publica un único aviso de actividad sospechosa por ventana en la cola de notificaciones ([ADR-IT3-001](../ITERACION_3/ADR-IT3-001.md)).

**Qué se paga.** La respuesta uniforme impide informar en pantalla si el usuario escribió mal su correo, y el envío del token depende de la cola de notificaciones.

**Qué alternativa quedó más cerca.** Exigir un desafío interactivo previo. Suma fricción a todos los viajeros y no reemplaza la condición atómica sobre la base ante peticiones concurrentes.

### ADR-IT4-013. Bloqueo de cuenta tras N intentos de recuperación o inicio de sesión (rechazado)

Es la defensa clásica contra fuerza bruta, pero en `QA-SEG-01` juega a favor del atacante: como el correo electrónico de una persona suele ser conocido, disparar 50 solicitudes de recuperación bloquearía la cuenta del viajero legítimo e incumpliría la medida del escenario ("la disponibilidad del servicio de login para usuarios legítimos se mantiene activo").

**Cuándo reabrirlo:** nunca sobre el login general a partir de pedidos de recuperación sin autenticar; el acotamiento ya lo da admitir un único pedido de recuperación vigente por cuenta ([ADR-IT4-006](ADR-IT4-006.md)).

### ADR-IT4-007. Autorización por itinerario con roles de grupo y auditoría de cada decisión

**Por qué.** `QA-SEG-02` exige validar los permisos de un participante sobre un itinerario compartido antes de registrar una actividad, redirigir a "Error 401" cuando no tiene permiso y "registrar la transacción". Como los viajes y las reservas pertenecen al Orquestador y viven en la Base de viajes, ubicar el Módulo de control de acceso y auditoría dentro del Orquestador permite verificar la membresía (`itinerario`, `cuenta`, `rol`), persistir la actividad y escribir el asiento de auditoría de solo agregado **en la misma transacción 2PC**, con denegación por defecto y sin que la cotización pague esa lectura.

**Qué se paga.** Cada operación sobre un itinerario suma una lectura de membresía y una escritura de auditoría, la tabla de auditoría crece también con los intentos denegados, y el Orquestador suma otra responsabilidad interna.

**Qué alternativa quedó más cerca.** Incluir los roles de cada itinerario dentro del token JWT para autorizar en el API Gateway. Pierde porque los permisos de un grupo cambian dinámicamente y un token de vida corta quedaría desactualizado o crecería con cada viaje compartido del usuario.

### ADR-IT4-011. Revocación de membresía en un itinerario efectiva desde la operación siguiente

**Por qué.** Complementa a [ADR-IT4-007](ADR-IT4-007.md) precisando qué ocurre cuando un organizador quita a un miembro de un itinerario compartido: la baja de la membresía se confirma de inmediato en la Base de viajes y rige desde la siguiente operación que ese usuario intente, sin mantener canales persistentes hacia los clientes para limpiar pantallas ya abiertas.

**Qué se paga.** El miembro removido puede seguir viendo en su dispositivo los datos que ya había descargado antes de la baja hasta que recargue o intente operar, momento en que recibe el rechazo ("Error 401").

**Qué alternativa quedó más cerca.** Abrir un canal WebSocket por itinerario abierto para forzar el cierre inmediato de la vista. Introduce estado de conexión en los nodos del Orquestador sin cambiar el hecho de que el usuario ya tuvo acceso a esa vista mientras era miembro.

---

## Gestión manual, lugar de la reserva y agencia preferida (`REF-04`, `REF-05`)

### ADR-IT4-008. Gestión manual de reservas en el Orquestador, idempotente, con origen y baja lógica

**Por qué.** `REF-04` pide agregar, actualizar y eliminar reservas a mano, y `QA-SEG-02` pide registrar una actividad en un itinerario compartido. Resolver ambas como las mismas operaciones del Orquestador sobre el contrato polimórfico `Reserva` ([ADR-IT3-005](../ITERACION_3/ADR-IT3-005.md)) mantiene un único punto de validación, autorización y escritura transaccional. La clave de operación evita duplicados ante reintentos móviles, `ReservaActividad` se suma al Registro de tipos sin tocar la agrupación, la marca de `origen` da precedencia a la edición manual frente a una novedad automática (dejando la novedad visible en "Novedades"), y la baja lógica conserva las cancelaciones que requiere `REF-06`.

**Qué se paga.** La precedencia manual requiere que el viajero resuelva en "Novedades" si el proveedor cambia luego esa reserva, y la baja lógica más las claves de operación acumulan almacenamiento.

**Qué alternativa quedó más cerca.** Extraer un servicio separado de reservas manuales. Repetiría el *Split module* rechazado en [ADR-IT3-011](../ITERACION_3/ADR-IT3-011.md) y duplicaría las reglas de validación y autorización.

### ADR-IT4-009. Extensión del contrato `Reserva` con el lugar de la reserva

**Por qué.** Tres drivers necesitan saber dónde ocurre una reserva: la carga manual (`REF-04`), las consultas analíticas por destino (`REF-06`) y la vista móvil con GPS (`QA-USA-01`). Incorporar `lugar` (nombre, destino y coordenadas opcionales) al contrato base `Reserva` permite que todos los consumidores lo lean de manera uniforme sin preguntar por el subtipo concreto ni parsear el texto libre del resumen.

**Qué se paga.** Se amplía un contrato crítico ([ADR-IT3-005](../ITERACION_3/ADR-IT3-005.md)), obligando a todas las subclases a exponer `lugar` y a los consumidores a degradar con elegancia cuando las coordenadas no estén presentes.

**Qué alternativa quedó más cerca.** Crear una interfaz lateral `IUbicable`. Pierde porque todos los tipos de reserva del dominio tienen un lugar asociado y separar la interfaz obligaría a comprobar tipos en tiempo de ejecución.

### ADR-IT4-010. Adaptador de agencia detrás de `IAgencia`, con pedidos de ayuda asíncronos

**Por qué.** `REF-05` y `CON-02` piden integrar la agencia de viajes preferida del usuario por API para resolver problemas. Extender `IProveedor` con `IAgencia` (`abrirCaso`, `consultarCaso`), publicar el pedido en una cuarta cola acotada del Broker (cola de casos de ayuda) y consumirlo desde un Adaptador de agencia en nodos propios con *Retry* e identificador único reutiliza íntegro el patrón de la iteración 3 ([ADR-IT3-001](../ITERACION_3/ADR-IT3-001.md) a [ADR-IT3-004](../ITERACION_3/ADR-IT3-004.md), [ADR-IT3-010](../ITERACION_3/ADR-IT3-010.md)) y hace que las respuestas de la agencia regresen por la cola de novedades.

**Qué se paga.** El viajero ve el caso inicialmente "en trámite" en lugar de recibir una respuesta instantánea del tercero, y el Broker pasa de tres a cuatro colas.

**Qué alternativa quedó más cerca.** Modelar la agencia como un `ICanal` de notificaciones. Pierde porque `ICanal` solo envía un mensaje saliente y no modela el ciclo de vida ni el retorno de novedades de un caso de soporte.

### ADR-IT4-014. Llamada síncrona del Orquestador a la agencia preferida dentro del pedido del usuario (rechazado)

Su ventaja sería devolver el identificador o estado de la agencia en el mismo turno HTTP del reporte. Se rechaza porque ata los hilos del Orquestador de viajes a la latencia y disponibilidad de un tercero externo justo durante eventos disruptivos, y hace que una caída temporal de la agencia rechace el pedido del viajero en lugar de retenerlo y reintentarlo por cola.

**Cuándo reabrirlo:** ninguna condición prevista mientras las agencias sean sistemas externos fuera del control de Trotamundos.
