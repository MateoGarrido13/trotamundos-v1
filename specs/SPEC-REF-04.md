# SPEC-REF-04. Gestión manual

* **Estado:** aprobada
* **Fecha:** 2026-11-23
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `REF-04`, `QA-SEG-02` |
| **ADRs** | `ADR-IT4-008`, `ADR-IT4-009`, `ADR-IT4-007` |
| **Elemento del paso 5** | [RONDA_1/ITERACION_4.md](../RONDA_1/ITERACION_4.md) Operaciones manuales de reserva, Módulo de control de acceso y auditoría, contrato `Reserva` |
| **Incremento (Slice)** | Slice 4 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

Los clientes deben poder agregar, actualizar o eliminar sus reservas existentes de forma manual dentro del panel.

Esas tres operaciones viven en el Orquestador de viajes, sobre el modelo polimórfico de [SPEC-REF-01](SPEC-REF-01.md). Registrar una actividad en un itinerario compartido es esta misma escritura, con autorización.

## Drivers que guían el cómo

* **`QA-SEG-02`:** antes de persistir, el sistema valida el permiso del usuario sobre ese itinerario. Con permiso, persiste la actividad, actualiza la vista para los demás miembros y registra la transacción. Sin permiso, no escribe la actividad y el cliente presenta la página «Error 401». La medida del listado pide que el 100 % de las solicitudes autorizadas se procesen, y que quienes no tengan permiso vean esa página. *(Origen: [RONDA_1/ITERACION_4.md](../RONDA_1/ITERACION_4.md): `REF-04` y `QA-SEG-02` son la misma operación de escritura)*

## Conceptos de diseño aceptados

* **Gestión manual en el Orquestador** (`ADR-IT4-008`): un único camino de escritura y de validación sobre el modelo polimórfico. Cada operación lleva una clave de operación generada por el cliente. Eliminar es una baja lógica. Una reserva editada a mano no la sobrescribe una novedad del proveedor: la novedad queda visible en «Novedades» para que el viajero decida. `ReservaActividad` es una clase más del Registro de tipos.
* **`lugar` en el contrato `Reserva`** (`ADR-IT4-009`): `lugar` forma parte del contrato `Reserva`. El viajero puede indicarlo en la carga manual. Analítica y demás consumidores lo leen del mismo contrato.
* **Autorización por itinerario y auditoría** (`ADR-IT4-007`): el Módulo de control de acceso está dentro del Orquestador. Cada operación declara el permiso que exige. Sin membresía y permiso explícitos, no hay operación. La auditoría de la decisión, permitida o denegada, se escribe en la misma transacción. El Orquestador responde acceso denegado y el cliente presenta la página «Error 401».

## Relaciones Permitidas

* **Recibe llamadas / mensajes de:** el balanceador, con la identidad del actor ya verificada por el gateway, para `agregarReserva`, `actualizarReserva(id)`, `eliminarReserva(id)` y la consulta de la vista del itinerario.
* **Invoca / publica hacia:** el Módulo de control de acceso, por la consulta interna `verificarPermiso(cuenta, itinerario, permisoRequerido)`. La Base de viajes, para la reserva, la membresía y el asiento de auditoría, en la misma transacción.
* **Restricciones de frontera:** la cotización no pasa por el control de acceso ni por la auditoría. El módulo de control de acceso no se consulta desde fuera del Orquestador. El cliente con GPS (`QA-USA-01`) no forma parte de esta spec.

## Roles y permisos

El ADR deja la matriz de roles y permisos para el diseño detallado. Esta spec la fija así. Los roles son organizador y participante. Los permisos que una operación puede declarar son ver, registrar, modificar y administrar miembros. Eliminar exige el permiso modificar.

| Permiso | Organizador | Participante |
| :--- | :--- | :--- |
| Ver | Sí | Sí |
| Registrar | Sí | Sí |
| Modificar (actualizar y eliminar) | Cualquier reserva del itinerario | Solo las reservas que él mismo creó |
| Administrar miembros | Sí | No |

* Cada reserva guarda `creadoPor`, la cuenta que la creó. Una reserva creada con `agregarReserva` lleva la cuenta del actor. Una reserva que vino de un proveedor o del correo no tiene `creadoPor`, y solo el organizador puede modificarla.
* Un itinerario individual tiene una sola membresía: la del viajero, como organizador.
* Una cuenta sin membresía en el itinerario no tiene ningún permiso.

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen (ADR / Iteración) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `verificarPermiso(cuenta, itinerario, permisoRequerido)` | Interna al Orquestador | Cuenta, itinerario y permiso que la operación declara | Concedido, denegado, o concedido solo sobre las reservas propias. En ese último caso el Orquestador compara `creadoPor` con la cuenta | Denegación por defecto | `ADR-IT4-007` |
| `agregarReserva` | Síncrono, desde el balanceador | Identidad del actor, clave de operación, reserva con `origen` manual y `lugar` | Reserva persistida con `creadoPor` del actor, o acceso denegado | Sin permiso no se escribe. La misma clave no duplica. Tipo no registrado o campos inválidos: rechazo sin escribir la reserva | `ADR-IT4-008`, `ADR-IT4-009` |
| `actualizarReserva(id)` | Síncrono, desde el balanceador | Identidad del actor, clave de operación, id y cambios | Reserva actualizada, o acceso denegado | Igual que el alta. Reserva inexistente, de otro itinerario o ya dada de baja: rechazo sin efecto | `ADR-IT4-008` |
| `eliminarReserva(id)` | Síncrono, desde el balanceador | Identidad del actor, clave de operación e id | Baja lógica, o acceso denegado | No es borrado físico. Reserva inexistente, de otro itinerario o ya dada de baja: rechazo sin efecto | `ADR-IT4-008` |
| Vista del itinerario | Síncrono, desde el balanceador | Identidad del actor e itinerario | Las reservas del itinerario que siguen vigentes, agrupadas por viaje | Sin permiso de ver: acceso denegado | `ADR-IT4-007`, `QA-SEG-02` |

**Orden de validación.** Primero el permiso, para no revelar si una reserva existe a quien no puede verla. Después la clave de operación. Después la existencia y el estado de la reserva. Al final, la validación del tipo.

**Acceso denegado.** La respuesta por la red lleva el código 403. La página que el cliente presenta es «Error 401», como nombra el escenario.

## Reglas de Comportamiento

1. **Un solo camino:** agregar, actualizar y eliminar, vengan de la gestión manual, pasan por el Orquestador, por la validación del tipo y por el control de acceso. *(Origen: `ADR-IT4-008`, `ADR-IT4-007`)*
2. **Idempotencia:** un reintento con la misma clave de operación no duplica la reserva. Si la misma clave llega con un contenido distinto, se devuelve el resultado de la primera operación y no se aplica la segunda. *(Origen: `ADR-IT4-008`)*
3. **Baja lógica:** eliminar marca la baja y conserva el historial. Una reserva dada de baja no se puede actualizar ni eliminar de nuevo. *(Origen: `ADR-IT4-008`)*
4. **Precedencia:** si una novedad del proveedor llega sobre una reserva editada a mano, no la pisa. La novedad queda en «Novedades». *(Origen: `ADR-IT4-008`)*
5. **Auditoría atómica:** con permiso, la reserva y el asiento de auditoría se escriben en la misma transacción. Si la escritura falla, no queda ni la reserva ni el asiento de éxito. Sin permiso, no se escribe la reserva y sí queda el asiento de la denegación. Una operación rechazada por la validación también deja su asiento. *(Origen: `ADR-IT4-007`)*
6. **Alcance del participante:** el participante modifica o elimina solo las reservas que él creó. Sobre las demás, el acceso se deniega y queda el asiento. El organizador modifica cualquiera. *(Origen: `ADR-IT4-007`)*
7. **Lugar:** la reserva manual puede traer `lugar`. Si no trae coordenadas, el contrato igual las tolera. *(Origen: `ADR-IT4-009`)*
8. **Vista para los demás miembros:** la reserva queda persistida en el itinerario, así que la próxima vista de cualquier miembro con permiso de ver la incluye. *(Origen: `QA-SEG-02`)*
9. **Itinerario:** es el contenedor de los viajes y el nivel al que se otorgan los permisos. El itinerario individual de un viajero se identifica con su propia cuenta. *(Origen: `ADR-IT4-007`)*
10. **Dónde va una reserva manual:** el pedido trae el itinerario y el viaje. Si el viaje no existe se crea dentro de ese itinerario; si pertenece a otro itinerario, se rechaza por campos inválidos. *(Origen: `ADR-IT4-008`)*
11. **Una sola transacción:** el permiso se lee, y la reserva, el asiento de auditoría y el resultado de la clave se escriben, dentro de una única escritura con el commit en dos fases. *(Origen: `ADR-IT4-007`, `ADR-IT4-008`)*
12. **Auditoría de los rechazos:** también dejan asiento los rechazos por reserva inexistente, de otro itinerario o en baja; no modifican ninguna reserva. En las consultas solo se audita la denegación, no cada vista permitida. *(Origen: `ADR-IT4-007`)*
13. **Reservas en baja:** no aparecen en la vista, ni en el archivo, ni cuentan para decidir que un viaje está completo ([SPEC-REF-01](SPEC-REF-01.md)). *(Origen: `ADR-IT4-008`)*
14. **Qué se actualiza:** `inicio`, `fin`, `lugar`, `estado` y los campos propios del tipo. El tipo, el viaje, el identificador, el origen y el creador no cambian. Una actualización marca la reserva como editada a mano, aunque la haga el organizador sobre una reserva de un proveedor o del correo. *(Origen: `ADR-IT4-008`)*
15. **Claves de operación:** la clave es por cuenta. Solo se memoriza el resultado de una operación aceptada; un rechazo no memoriza su clave, así que se puede corregir y reenviar con la misma. *(Origen: `ADR-IT4-008`)*
16. **Novedades:** una novedad repetida se descarta. Una novedad que no se puede aplicar sola, o que llega sobre una reserva editada a mano o dada de baja, queda pendiente en «Novedades». Si la reserva no fue editada, la novedad se aplica sin marcarla como editada. *(Origen: `ADR-IT4-008`)*
17. **Respuestas:** 403 acceso denegado, 404 reserva inexistente o de otro itinerario, 409 reserva en baja, 422 tipo no registrado o campos inválidos (o falta la identidad o la clave). Una clave repetida devuelve el estado y el cuerpo de la primera operación. *(Origen: `ADR-IT4-007`)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-REF-04-01` | El actor tiene permiso para registrar en ese itinerario | Llama a `agregarReserva` con clave de operación, `origen` manual y, si lo indica, `lugar` | La reserva queda persistida con `creadoPor` del actor, agrupable por viaje, y el asiento de auditoría queda en la misma transacción | `REF-04`, `QA-SEG-02`, `ADR-IT4-008`, `ADR-IT4-007` | Test automático |
| `AC-REF-04-02` | La misma clave de operación ya creó esa reserva | El cliente reintenta `agregarReserva` | No aparece una segunda reserva | `REF-04`, `ADR-IT4-008` | Test automático |
| `AC-REF-04-03` | Existe una reserva manual | El actor con permiso llama a `eliminarReserva(id)` | La reserva queda en baja lógica y sigue disponible para el historial | `REF-04`, `ADR-IT4-008` | Test automático |
| `AC-REF-04-04` | Una reserva fue editada a mano y el proveedor publica una novedad de esa reserva | La novedad llega al Orquestador | La edición manual permanece y la novedad queda visible en «Novedades» | `REF-04`, `ADR-IT4-008` | Test automático |
| `AC-REF-04-05` | Una cuenta autenticada no tiene membresía en ese itinerario | Intenta registrar una actividad | No se persiste la actividad, queda el asiento de la denegación, la respuesta lleva el código 403 y el cliente presenta la página «Error 401» | `QA-SEG-02`, `ADR-IT4-007` | Test automático para la respuesta, demostración para la página |
| `AC-REF-04-06` | El actor tiene permiso y registra una actividad (`ReservaActividad`) | La operación termina y otro miembro con permiso de ver pide la vista del itinerario | El otro miembro ve la actividad | `QA-SEG-02` | Test automático |
| `AC-REF-04-07` | Un participante creó una reserva | La actualiza o la elimina | La operación se acepta y deja su asiento de auditoría | `ADR-IT4-007` | Test automático |
| `AC-REF-04-08` | Una reserva fue creada por otro miembro, o vino de un proveedor o del correo | Un participante intenta actualizarla o eliminarla | El acceso se deniega, la reserva no cambia y queda el asiento de la denegación | `QA-SEG-02`, `ADR-IT4-007` | Test automático |
| `AC-REF-04-09` | Una reserva fue creada por un participante, o vino de un proveedor | El organizador la actualiza o la elimina | La operación se acepta | `ADR-IT4-007` | Test automático |
| `AC-REF-04-10` | La misma clave de operación ya se aplicó | Llega con un contenido distinto | Se devuelve el resultado de la primera operación y no se aplica la segunda | `ADR-IT4-008` | Test automático |
| `AC-REF-04-11` | Una reserva está en baja lógica | Un actor con permiso la actualiza o la elimina | La operación se rechaza sin efecto | `ADR-IT4-008` | Test automático |
| `AC-REF-04-12` | Un actor con permiso pide actualizar o eliminar una reserva que no existe, o que es de otro itinerario | Llama a la operación | Se rechaza sin efecto. Si el actor no tiene permiso en ese itinerario, la respuesta es el acceso denegado y no revela si la reserva existe | `ADR-IT4-007`, `ADR-IT4-008` | Test automático |
| `AC-REF-04-13` | El actor tiene permiso | Llama a `agregarReserva` con un tipo no registrado o con campos inválidos | Se rechaza sin escribir la reserva y queda el asiento de la operación rechazada | `ADR-IT4-008`, `ADR-IT4-007` | Test automático |
| `AC-REF-04-14` | El actor tiene permiso y la escritura de la reserva falla | La transacción se cancela | No queda ni la reserva ni el asiento de éxito | `ADR-IT4-007` | Test automático |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| Retención de las claves de operación | 7 días, configurable | Cuánto tiempo se guardan para reconocer un reintento | `ADR-IT4-008` |
| Eliminación definitiva de una baja lógica | No se hace en el prototipo | Si una reserva dada de baja puede borrarse del almacenamiento. Queda pendiente por privacidad, como reconoce el ADR | `ADR-IT4-008` |
| Código de estado que viaja por la red cuando falta permiso | 403. La página que ve el cliente sigue siendo «Error 401» | El valor HTTP del acceso denegado | `ADR-IT4-007` |
| Retención de la auditoría | Sin vencimiento en el prototipo | Cuánto tiempo se conservan los asientos, incluidos los de denegación | `ADR-IT4-007` |
| Intervalo de la purga de claves de operación | 3600 s, el mismo de la purga de Mensajes en revisión | Cada cuánto se eliminan las claves que cumplieron la retención | `ADR-IT4-008` |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| Las membresías (itinerario, cuenta, rol) se precargan como datos de prueba. No hay operaciones para crear itinerarios compartidos ni para altas y bajas de miembros. | `QA-SEG-02`, `ADR-IT4-007` | El escenario parte de «permisos de grupo previamente configurados». El Módulo de control de acceso valida membresía y rol igual. |
| Los demás miembros ven la actualización en su próxima consulta. No hay aviso en tiempo real. | `QA-SEG-02` | La actividad queda persistida en el itinerario compartido, y es lo que el paso 5 exige. |
| Un viajero no tiene membresía en su itinerario individual hasta que se la precarga | `ADR-IT4-007` | Es la misma simplificación de las membresías precargadas. Las reservas que llegan por el correo o por el panel de REF-01 no dependen de ella |
| De las novedades solo existe el lado del Orquestador: la forma mínima de la novedad (identificador, reserva, cambios, proveedor) y la regla de precedencia | `ADR-IT4-008` | La ingesta de Booking (`QA-PER-01`) no tiene spec en esta tanda. La precedencia de la edición manual es lo que se verifica |
| La página «Error 401» no se implementa: se verifica la respuesta 403 con su cuerpo `{"error": "acceso_denegado"}` | `ADR-IT4-007` | El cliente web todavía no existe. El criterio ya marca la página como demostración |

## Fuera de Alcance

* Geolocalización del cliente móvil (`QA-USA-01`, `ADR-IT5-003`).
* Cotización y su ausencia de control de acceso: esta spec no la redefine.
* El alta de cuenta y el token de sesión. Esta spec recibe la identidad ya verificada.
* Analítica de las cancelaciones: la baja lógica le deja el dato a [SPEC-REF-06](SPEC-REF-06.md).
* Crear itinerarios compartidos y administrar miembros. El permiso «administrar miembros» queda en la matriz, sin una operación que lo use.
* Aviso en tiempo real a los demás miembros.
* La interfaz para decidir qué hacer con una novedad que no pisó una edición manual.
* Eliminación definitiva de una baja lógica, por privacidad.
* Edición sin conexión.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-22 | Versión inicial (`borrador`) | Creación a partir de `REF-04` y de los ADR aceptados que la iteración le asocia |
| 2026-11-23 | Decisiones de revisión | Matriz de roles y permisos con alcance propio del participante (`creadoPor`); membresías precargadas; vista actualizada en la próxima consulta; código 403 con página «Error 401»; valores de parámetros; orden de validación y errores de las operaciones; criterios de aceptación nuevos |
| 2026-11-23 | Decisiones de implementación fijadas (`PLAN-REF-04`) | Itinerario como contenedor de viajes con el individual identificado por la cuenta; destino de una reserva manual; una sola transacción con permiso, clave, reserva y auditoría; auditoría de los rechazos; reservas en baja fuera de la vista y del cierre del viaje; qué se actualiza; claves por cuenta y rechazos sin memorizar; novedades mínimas con precedencia; códigos 403, 404, 409 y 422 |
