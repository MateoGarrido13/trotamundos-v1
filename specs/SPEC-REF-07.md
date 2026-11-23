# SPEC-REF-07. Asistente virtual (Chatbot)

* **Estado:** aprobada
* **Fecha:** 2026-11-23
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `REF-07`, `QA-DIS-02`, `QA-PER-05`, `QA-SEG-04`, `QA-SEG-02` |
| **ADRs** | [ADR-IT6-001](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-001.md), [ADR-IT6-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-002.md), [ADR-IT6-003](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-003.md), [ADR-IT6-004](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-004.md), [ADR-IT7-001](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-001.md), [ADR-IT7-002](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-002.md), [ADR-IT7-003](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-003.md), [ADR-IT7-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-004.md) |
| **Elemento del paso 5** | [RONDA_2/ITERACION_1.md](../RONDA_2/ITERACION_1.md) Módulo de Asistente Virtual e `IMotorConversacional`; [RONDA_2/ITERACION_2.md](../RONDA_2/ITERACION_2.md) filtrado de inyección, cota de 35 segundos, time-out y Circuit Breaker |
| **Incremento (Slice)** | Slice 5 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

Implementar un bot conversacional integrado que actúe como primer nivel de soporte interactivo para gestionar reprogramaciones, consultas de estado y problemas menores, delegando a la agencia de viajes preferida del usuario únicamente aquellos casos complejos.

Las escrituras de primer nivel usan las operaciones de [SPEC-REF-04](SPEC-REF-04.md). La delegación usa la cola y `IAgencia` de [SPEC-REF-05](SPEC-REF-05.md).

## Drivers que guían el cómo

* **`QA-PER-05`:** con un proveedor de modelo de IA disponible, la respuesta al viajero llega en como máximo 35 segundos. *(Origen: [RONDA_2/LISTADO_DRIVERS_RONDA_2.md](../RONDA_2/LISTADO_DRIVERS_RONDA_2.md))*
* **`QA-DIS-02`:** si ningún proveedor de modelo de IA está disponible, el asistente muestra el número de contacto de la agencia de viajes preferida del usuario. En el 100 % de las consultas en esa condición, el viajero recibe ese número. *(Origen: [RONDA_2/LISTADO_DRIVERS_RONDA_2.md](../RONDA_2/LISTADO_DRIVERS_RONDA_2.md))*
* **`QA-SEG-04`:** ante una inyección de prompt, o un pedido distinto de una reprogramación, una consulta de estado, un problema menor o la delegación de un caso complejo, el asistente no obedece la instrucción y no responde fuera del propósito de `REF-07`. Como alternativa, ofrece el número de contacto de la agencia de viajes preferida. En el 100 % de esos intentos la respuesta permanece dentro de ese alcance. *(Origen: [RONDA_2/LISTADO_DRIVERS_RONDA_2.md](../RONDA_2/LISTADO_DRIVERS_RONDA_2.md))*
* **`QA-SEG-02`:** una escritura de primer nivel pasa por el permiso y la auditoría del Orquestador. Sin permiso, el rechazo es el mismo que en la gestión manual. *(Origen: [ADR-IT6-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-002.md); el contrato está en [SPEC-REF-04](SPEC-REF-04.md))*

## Conceptos de diseño aceptados

* **Módulo en nodos propios, sin estado, detrás del API Gateway** ([ADR-IT6-001](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-001.md)): el Módulo de Asistente Virtual corre en nodos propios, sin estado, detrás del API Gateway, separado de los nodos que resuelven la cotización. Llega al Orquestador por su interfaz interna.
* **Invocación al Orquestador con identidad y clave de operación** ([ADR-IT6-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-002.md)): el primer nivel llama a las operaciones del Orquestador propagando la identidad del actor y una clave de operación. El control de acceso y la auditoría son los de esa operación. Una misma clave no aplica dos veces la reprogramación. Toda escritura exige antes una confirmación explícita del viajero.
* **Delegación asíncrona por la cola de casos de ayuda** ([ADR-IT6-003](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-003.md)): un caso complejo se delega invocando la apertura de caso en el Orquestador, con el resumen del diálogo y la reserva afectada. El pedido sale por la cola de casos de ayuda hacia `IAgencia`. El viajero ve el caso «en trámite» y las respuestas en «Novedades».
* **`IMotorConversacional` con cota y degradación a menú** ([ADR-IT6-004](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-004.md)): `interpretar(mensaje, contexto)` abstrae el motor. Si la cota vence, el asistente degrada a opciones guiadas de primer nivel, sin Retry bloqueante.
* **Filtrado de inyección de prompt** ([ADR-IT7-001](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-001.md)): un módulo intercepta, antes de `IMotorConversacional`, cualquier mensaje que intente instrucciones distintas de reprogramaciones, consultas de estado, problemas menores o delegación a la agencia. La respuesta permanece dentro de `REF-07` y ofrece el número de contacto de la agencia preferida.
* **Cota de 35 segundos** ([ADR-IT7-002](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-002.md)): la espera de `IMotorConversacional` no pasa de 35 segundos para el viajero. Si el proveedor no responde, el viajero recibe el número de contacto de la agencia preferida dentro de esa cota.
* **Clasificación en dos niveles** ([ADR-IT7-003](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-003.md)): primer nivel es lo que se resuelve con las operaciones ya existentes sobre el itinerario (consultas de estado o novedades, reprogramaciones o bajas sobre reservas editables). Caso complejo es lo que involucra dinero, penalidades de proveedor o un tercero que no responde: reembolsos, disputas, tramos con penalidad, proveedor caído o pedido explícito del viajero. El escalamiento pasa por el Orquestador.
* **Time-out y Circuit Breaker** ([ADR-IT7-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-004.md)): el time-out hacia el proveedor de modelo se agota antes de los 35 segundos, libera el hilo y muestra el número de contacto. A la quinta vez consecutiva, el Circuit Breaker pasa a abierto, corta las llamadas a ese proveedor y la respuesta por defecto sale sin demora, hasta que el proveedor se recupere.

## Relaciones Permitidas

* **Recibe llamadas / mensajes de:** Cliente web y Cliente móvil, por el API Gateway, con la identidad ya verificada.
* **Invoca / publica hacia:** `IMotorConversacional.interpretar(mensaje, contexto)`, después del filtro de inyección. El Orquestador, con las operaciones de [SPEC-REF-04](SPEC-REF-04.md) para el primer nivel, con la apertura de caso de [SPEC-REF-05](SPEC-REF-05.md) para el caso complejo, y con la consulta de la agencia preferida para obtener su número.
* **Restricciones de frontera:** el Asistente no lee ni escribe la Base de viajes ni ninguna otra base, y no guarda estado entre turnos. No llama a la API de la agencia. No hay Retry bloqueante contra el motor dentro del turno del viajero. El filtro corre antes de `IMotorConversacional`.

## Contexto de la conversación

El módulo no guarda nada entre turnos. Lo que hace falta recordar viaja en un **contexto firmado** que el módulo entrega al cliente y el cliente devuelve en cada turno.

* El contexto lleva la acción pendiente de confirmación, si hay una, con su clave de operación, y los últimos mensajes aceptados por el filtro. Lleva una fecha de vencimiento.
* El módulo lo firma con una clave tomada de una variable de entorno. Si la firma no coincide, o el contexto venció, se descarta: no se ejecuta ninguna acción pendiente y la conversación empieza de nuevo.
* La clave de operación de una acción se genera cuando el asistente la propone y viaja en la acción pendiente. Así, reintentar la confirmación usa la misma clave y no aplica la escritura dos veces.

## Intenciones y acciones

`interpretar` devuelve una **intención tipada** de un conjunto cerrado. Cualquier otra respuesta del motor se trata como `fueraDeAlcance`.

| Intención | Qué dispara |
| :--- | :--- |
| `consultarEstado` | Consulta de estado o novedades de una reserva o viaje |
| `agregarReserva` | Alta de una reserva o actividad, con confirmación |
| `reprogramar` | `actualizarReserva(id)` con los cambios, con confirmación |
| `eliminarReserva` | `eliminarReserva(id)`, con confirmación |
| `casoComplejo` | Apertura de caso en el Orquestador, con confirmación |
| `fueraDeAlcance` | Rechazo dentro de `REF-07` con el número de la agencia |

Un **problema menor** es el que se resuelve con una de las operaciones de primer nivel (consulta, alta, reprogramación o baja). Lo que no encaja ahí es un caso complejo.

Una acción con efecto (escritura sobre una reserva o apertura de un caso) pide siempre la **confirmación** del viajero. La confirmación llega como acción estructurada (botón Confirmar o Cancelar del cliente) y no pasa por el motor.

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen (ADR / Iteración) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Turno de chat | Síncrono, cliente por el API Gateway | Mensaje de texto libre, identidad verificada y contexto firmado | Respuesta de primer nivel, propuesta de acción con pedido de confirmación, menú guiado, número de la agencia, o caso «en trámite», y el contexto firmado nuevo | 35 segundos como máximo para todo el turno. Contexto con firma inválida o vencido: se descarta y la conversación empieza de nuevo | `QA-PER-05`, [ADR-IT7-002](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-002.md) |
| Acción guiada | Síncrono, cliente por el API Gateway. No usa el motor | Identidad, contexto firmado y una acción estructurada: consultar estado, reprogramar (reserva y cambios), derivar a la agencia (reserva y motivo), confirmar o cancelar | El resultado de esa acción, o la propuesta que espera confirmación | El texto libre que traiga la acción, como el motivo de una derivación, pasa por el filtro. Confirmar sin acción pendiente: rechazo sin efecto | [ADR-IT6-004](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-004.md) |
| Filtro de inyección | Interno, antes del motor | Mensaje del viajero | Mensaje aceptado hacia `interpretar`, o rechazo dentro de `REF-07` con el número de la agencia y el menú guiado | Rechaza el mensaje que supera el largo máximo, trae caracteres de control, o coincide con un patrón de inyección: pedidos de ignorar instrucciones, mostrar o cambiar las instrucciones internas, adoptar otro rol, o marcas que imitan mensajes del sistema | [ADR-IT7-001](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-001.md) |
| `interpretar(mensaje, contexto)` | Síncrono, hacia el adaptador del motor, sin Retry | Mensaje ya filtrado y contexto | Intención tipada de un conjunto cerrado | Time-out de 20 segundos como máximo y nunca más que lo que reste de los 35 segundos del turno | [ADR-IT6-004](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-004.md), [ADR-IT7-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-004.md) |
| Escritura de primer nivel | Hacia el Orquestador, igual que la gestión manual | Identidad del actor, clave de operación, y la operación `agregarReserva`, `actualizarReserva(id)` o `eliminarReserva(id)` | El resultado de [SPEC-REF-04](SPEC-REF-04.md), después de la confirmación del viajero | Sin permiso, la misma denegación y auditoría de esa spec. El asistente informa la denegación y ofrece derivar a la agencia | [ADR-IT6-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-002.md) |
| Apertura de caso complejo | Hacia el Orquestador | Identidad, clave de operación, resumen del diálogo y reserva afectada, después de la confirmación del viajero | Caso «en trámite» por [SPEC-REF-05](SPEC-REF-05.md) | La agencia no se llama desde el Asistente. Si el viajero no tiene agencia preferida o no dio su consentimiento, el Orquestador rechaza y el asistente propone elegirla | [ADR-IT6-003](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-003.md), [ADR-IT7-003](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-003.md) |
| Consulta de la agencia preferida | Síncrono, hacia el Orquestador | Identidad del actor | Nombre y número de contacto de su agencia preferida, o la falta de agencia | La agencia vive en la configuración de [SPEC-REF-05](SPEC-REF-05.md), con su número. El Asistente no lo guarda | `QA-DIS-02`, [ADR-IT6-001](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-001.md) |

**Resumen del diálogo.** Lo arma el Asistente sin usar el motor: motivo, reserva afectada y los últimos 5 mensajes del viajero. Los mensajes que el filtro rechazó no entran. Así, derivar a la agencia funciona también cuando el motor no responde.

**Menú guiado.** Ofrece consultar estado, reprogramar y derivar a la agencia. Se muestra junto con el número de la agencia siempre que el asistente no puede usar el motor: por time-out, con el circuito abierto o ante un rechazo del filtro.

## Circuit Breaker

El circuito se cuenta por proveedor de modelo y tiene tres estados.

| Estado | Comportamiento | Cómo se sale |
| :--- | :--- | :--- |
| **Cerrado** | Las consultas llegan al proveedor | A los 5 time-out consecutivos pasa a abierto. Un turno exitoso reinicia la cuenta a cero |
| **Abierto** | No se llama al proveedor. La respuesta con el número y el menú sale de inmediato | Tras 30 segundos pasa a semi-abierto |
| **Semi-abierto** | Deja pasar una sola llamada de prueba | Si el proveedor responde, vuelve a cerrado. Si no, vuelve a abierto |

## Reglas de Comportamiento

1. **Primer nivel:** consultas de estado o novedades, y reprogramaciones o bajas sobre reservas editables, se resuelven con las operaciones del Orquestador. Una reserva es editable si el Orquestador permite modificarla según [SPEC-REF-04](SPEC-REF-04.md): el Asistente no lo decide por su cuenta. *(Origen: [RONDA_2/ITERACION_1.md](../RONDA_2/ITERACION_1.md), [ADR-IT7-003](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-003.md))*
2. **Confirmación:** una acción con efecto se propone y espera la confirmación del viajero. Sin confirmación no se ejecuta. *(Origen: [ADR-IT6-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-002.md))*
3. **Caso complejo:** reembolsos, disputas, tramos con penalidad, proveedor caído o un pedido explícito de escalar se delegan por el Orquestador hacia la cola de casos de ayuda, con el resumen y la reserva afectada. *(Origen: [ADR-IT7-003](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-003.md))*
4. **Permisos:** la identidad y la clave de operación viajan en la llamada. Sin permiso, el Orquestador rechaza y audita como en la gestión manual. *(Origen: [ADR-IT6-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-002.md))*
5. **Reserva ambigua:** si la intención no identifica una única reserva, el asistente muestra las candidatas para que el viajero elija y no adivina. *(Origen: [ADR-IT6-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-002.md))*
6. **Inyección y fuera de propósito:** el filtro corre antes del motor. Una intención `fueraDeAlcance`, o cualquier intención fuera del conjunto cerrado, recibe el mismo rechazo. La respuesta no sale del propósito de `REF-07` y ofrece el número de la agencia preferida y el menú. *(Origen: [ADR-IT7-001](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-001.md))*
7. **Tiempo:** el viajero recibe una respuesta en como máximo 35 segundos. Si el motor no responde, esa respuesta es el número de contacto de la agencia preferida junto con el menú guiado. *(Origen: [ADR-IT7-002](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-002.md), [ADR-IT6-004](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-004.md))*
8. **Proveedor caído:** el time-out se agota antes de los 35 segundos. Al quinto time-out consecutivo el Circuit Breaker queda abierto y el número de la agencia sale de inmediato, sin llamar al proveedor, hasta que se recupere. *(Origen: [ADR-IT7-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-004.md))*
9. **Sin agencia preferida:** si el viajero no eligió agencia, el asistente lo dice y propone elegirla. No muestra un número que no sea el de su agencia. *(Origen: `QA-DIS-02`)*
10. **Sin estado:** el módulo no guarda nada entre turnos. La acción pendiente y los últimos mensajes viajan en el contexto firmado. *(Origen: [ADR-IT6-001](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-001.md))*
11. **Acciones guiadas sin motor:** consultar estado, reprogramar, derivar, confirmar y cancelar funcionan sin llamar al motor. *(Origen: [ADR-IT6-004](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-004.md))*
12. **Cota con degradación:** un turno entero corre dentro de la cota de 35 segundos. El motor recibe el menor valor entre el time-out de 20 segundos y lo que reste de la cota. Un turno que supera la cota, un time-out, una caída del proveedor y un circuito abierto terminan igual: el número de la agencia preferida y el menú guiado. *(Origen: [ADR-IT7-002](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-002.md), [ADR-IT7-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-004.md))*
13. **Qué cuenta el circuito:** los fallos del proveedor (time-out o caída). Los rechazos del filtro y las intenciones fuera de alcance no son fallos. Un turno en el que el motor responde, aunque la intención sea `fueraDeAlcance`, reinicia la cuenta. *(Origen: [ADR-IT7-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-004.md))*
14. **Contexto atado a la cuenta:** el contexto firmado lleva la cuenta y el itinerario; uno firmado para otra cuenta u otro itinerario se descarta, así una cuenta no confirma la acción propuesta a otra. Cada turno renueva la vigencia de 30 minutos. *(Origen: [ADR-IT6-001](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-001.md))*
15. **Itinerario:** el cliente indica el itinerario en cada pedido; el Asistente no guarda cuál es. *(Origen: [ADR-IT6-001](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-001.md))*
16. **Reserva identificada:** la referencia que devuelve el motor es un identificador o un texto (lugar o tipo); el Asistente la compara con las reservas vigentes del itinerario y solo sigue si coincide exactamente una. Sin referencia, o con ninguna o varias coincidencias, muestra hasta 10 candidatas. *(Origen: [ADR-IT6-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-002.md))*
17. **Alta por el asistente:** hacen falta el lugar y la fecha de inicio (el fin, si falta, es el inicio); sin ellos el asistente los pide y no propone nada. Sin viaje indicado, la reserva va al viaje `viaje-<itinerario>`, que el Orquestador crea si no existe. *(Origen: [SPEC-REF-04](SPEC-REF-04.md))*
18. **Falla del Orquestador al confirmar:** la acción sigue pendiente con su misma clave de operación y el viajero puede reintentar la confirmación sin que se aplique dos veces. *(Origen: [ADR-IT6-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-002.md))*
19. **Denegación y rechazo al confirmar:** sin permiso, el asistente informa la denegación, ofrece derivar a la agencia y el Orquestador ya dejó su asiento. Un rechazo de validación se informa con su motivo. Si el viajero no tiene agencia o no dio su consentimiento, el asistente propone elegirla. *(Origen: [ADR-IT6-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-002.md))*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-REF-07-01` | Hay un proveedor de modelo disponible y el viajero pide reprogramar una reserva | Envía el mensaje y después confirma | El Asistente propone la acción, y al confirmar llama a `actualizarReserva` en el Orquestador con la identidad y la clave de operación. La respuesta de cada turno llega en como máximo 35 segundos | `REF-07`, `QA-PER-05`, [ADR-IT6-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-002.md) | Test automático |
| `AC-REF-07-02` | La misma clave de operación ya aplicó esa reprogramación | La confirmación se reintenta | El Orquestador no aplica la reprogramación por segunda vez | [ADR-IT6-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-002.md) | Test automático |
| `AC-REF-07-03` | El actor no tiene permiso sobre el itinerario | Pide por el asistente registrar o reprogramar y confirma | No se escribe la reserva, la denegación queda auditada como en [SPEC-REF-04](SPEC-REF-04.md), y el asistente lo informa y ofrece derivar a la agencia | `QA-SEG-02`, [ADR-IT6-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-002.md) | Test automático |
| `AC-REF-07-04` | El viajero describe un reembolso, una disputa, un tramo con penalidad, un proveedor caído, o pide escalar | El asistente clasifica el turno y el viajero confirma | Invoca la apertura de caso en el Orquestador con el resumen y la reserva afectada, y el viajero ve «en trámite». El Asistente no llama a la API de la agencia | `REF-07`, [ADR-IT6-003](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-003.md), [ADR-IT7-003](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-003.md) | Test automático |
| `AC-REF-07-05` | Un conjunto fijo de al menos 30 mensajes de inyección de prompt | Cada uno llega al asistente | Ninguno alcanza a `IMotorConversacional`. En todos, la respuesta queda dentro de `REF-07` y ofrece el número de la agencia preferida | `QA-SEG-04`, [ADR-IT7-001](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-001.md) | Test automático |
| `AC-REF-07-06` | Un conjunto fijo de pedidos fuera del propósito de `REF-07` y sin patrón de inyección, y un motor que los clasifica como `fueraDeAlcance` | Cada uno llega al asistente | En todos, la respuesta es el mismo rechazo dentro de `REF-07` con el número de la agencia, y no se ejecuta ninguna acción | `QA-SEG-04`, [ADR-IT7-001](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-001.md) | Test automático |
| `AC-REF-07-07` | El motor devuelve una intención que no pertenece al conjunto cerrado | El asistente la recibe | La trata como `fueraDeAlcance` y no ejecuta nada | `QA-SEG-04` | Test automático |
| `AC-REF-07-08` | Ningún proveedor de modelo responde | El viajero envía una consulta | El time-out de 20 segundos se agota y dentro de los 35 segundos ve el número de contacto de su agencia preferida y el menú guiado | `QA-DIS-02`, `QA-PER-05`, [ADR-IT7-002](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-002.md), [ADR-IT7-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-004.md) | Test automático |
| `AC-REF-07-09` | Ningún proveedor está disponible y el viajero tiene agencia preferida | Se envían varias consultas seguidas | El 100 % de ellas recibe el número de la agencia | `QA-DIS-02` | Test automático |
| `AC-REF-07-10` | El proveedor acumuló cinco time-out consecutivos y el Circuit Breaker está abierto | Llega otra consulta | La respuesta con el número y el menú sale en menos de 100 ms y no se llama al proveedor | `QA-DIS-02`, [ADR-IT7-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-004.md) | Test automático |
| `AC-REF-07-11` | El circuito lleva 30 segundos abierto | Llega una consulta | Pasa a semi-abierto y deja pasar una sola llamada de prueba. Si el proveedor responde, el circuito se cierra. Si no, vuelve a abrirse | [ADR-IT7-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-004.md) | Test automático |
| `AC-REF-07-12` | Hubo cuatro time-out consecutivos | Un turno se resuelve con éxito | La cuenta vuelve a cero y hacen falta cinco time-out nuevos para abrir el circuito | [ADR-IT7-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-004.md) | Test automático |
| `AC-REF-07-13` | El motor supera el time-out, con el circuito cerrado | Vence la espera | El viajero obtiene el menú guiado y el número, sin un Retry bloqueante del motor | [ADR-IT6-004](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-004.md) | Test automático |
| `AC-REF-07-14` | El motor no responde | El viajero elige derivar a la agencia en el menú y confirma | Se abre el caso con un resumen armado sin el motor: motivo, reserva y hasta 5 mensajes, sin los que rechazó el filtro | [ADR-IT6-003](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-003.md), [ADR-IT6-004](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-004.md) | Test automático |
| `AC-REF-07-15` | El motor no responde | El viajero consulta estado o reprograma por el menú | La acción funciona sin llamar al motor | [ADR-IT6-004](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-004.md) | Test automático |
| `AC-REF-07-16` | El cliente devuelve un contexto con la firma alterada | Envía un turno | El contexto se descarta, no se ejecuta ninguna acción pendiente y la conversación empieza de nuevo | [ADR-IT6-001](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-001.md) | Test automático |
| `AC-REF-07-17` | El contexto venció | Envía un turno | Se descarta y la conversación empieza de nuevo | [ADR-IT6-001](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-001.md) | Test automático |
| `AC-REF-07-18` | No hay acción pendiente en el contexto | Llega una confirmación | Se rechaza sin efecto | [ADR-IT6-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-002.md) | Test automático |
| `AC-REF-07-19` | La intención no identifica una única reserva | El asistente procesa el turno | Muestra las candidatas para elegir y no ejecuta nada | [ADR-IT6-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-002.md) | Test automático |
| `AC-REF-07-20` | El viajero no eligió agencia preferida y el motor no responde | Envía una consulta | El asistente informa que no tiene agencia elegida y propone elegirla, sin mostrar otro número | `QA-DIS-02` | Test automático |
| `AC-REF-07-21` | El módulo del Asistente corre en sus nodos | Se inspeccionan sus dependencias y su configuración | No tiene credenciales de ninguna base ni de la API de la agencia, y no guarda estado entre turnos | [ADR-IT6-001](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-001.md) | Test automático |
| `AC-REF-07-22` | El proveedor demora menos que el time-out (por ejemplo 15 segundos), o demora más (por ejemplo 30 segundos) | El viajero envía una consulta | Con la demora menor, la respuesta llega en menos de 35 segundos, con la acción propuesta. Con la demora mayor, el time-out de 20 segundos se agota y, dentro de los 35 segundos, el viajero ve el número de la agencia y el menú guiado | `QA-PER-05`, [ADR-IT7-002](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-002.md), [ADR-IT7-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-004.md) | Test automático |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| Cota de respuesta al viajero | 35 segundos | Tiempo máximo hasta la respuesta del turno, incluida la degradación | `QA-PER-05`, [ADR-IT7-002](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-002.md) |
| Duración del time-out hacia el proveedor de modelo | 20 segundos | Cota interior a los 35 segundos. Al agotarse se muestra el número de la agencia | [ADR-IT7-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-004.md) |
| Umbral del Circuit Breaker | 5 time-out consecutivos | A partir de ahí el circuito queda abierto | [ADR-IT7-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-004.md) |
| Tiempo con el circuito abierto | 30 segundos | Cuándo pasa a semi-abierto y permite una llamada de prueba | [ADR-IT7-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-004.md) |
| Respuesta con el circuito abierto | Inmediata, sin llamar al proveedor. Tolerancia de prueba: 100 ms | Tiempo de la respuesta por defecto. La consulta interna de la agencia no puede costar literalmente cero | [ADR-IT7-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-004.md) |
| Factor de escala de tiempos en las pruebas | Configurable (por ejemplo, un décimo) | Reduce proporcionalmente la cota, el time-out y el tiempo con el circuito abierto para que las pruebas no esperen los valores reales. La demostración usa los valores reales | `QA-PER-05` |
| Vigencia del contexto firmado | 30 minutos | Cuánto vale un contexto antes de descartarse | [ADR-IT6-001](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-001.md) |
| Largo máximo de un mensaje | 500 caracteres | Qué mensaje rechaza el filtro por su extensión | [ADR-IT7-001](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-001.md) |
| Mensajes en el resumen del diálogo | 5 | Cuántos mensajes del viajero entran al resumen | [ADR-IT6-003](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-003.md) |
| Candidatas que se muestran | 10 | Cuántas reservas se listan cuando la referencia no identifica una sola | [ADR-IT6-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-002.md) |
| Número de contacto de la agencia preferida | Se guarda con la agencia en la configuración de [SPEC-REF-05](SPEC-REF-05.md) y se obtiene del Orquestador | Origen del número que se muestra en `QA-DIS-02` y `QA-SEG-04` | Los ADR nombran el número y no fijan su almacenamiento |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| El proveedor de modelo se simula con un mock local al que se le puede inyectar demora, time-out o caída | `QA-PER-05`, `QA-DIS-02`, `CON-02` | `IMotorConversacional`, el filtro, la cota y el Circuit Breaker se conservan. Lo permite [POLITICAS_SPECS_Y_PLANES.md](../POLITICAS_SPECS_Y_PLANES.md) §4.6. |
| Hay un solo proveedor de modelo por vez, con el Circuit Breaker propio de ese proveedor | `QA-DIS-02`, [ADR-IT7-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-004.md) | «Ningún proveedor disponible» se cumple con el proveedor configurado. Una lista ordenada de varios proveedores es una extensión que ningún ADR decide. |
| La clave que firma el contexto sale de una variable de entorno | [ADR-IT6-001](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-001.md) | El módulo sigue sin estado: el contexto viaja con el cliente y se valida con la firma. |
| El motor del prototipo interpreta por reglas de palabras clave y puede devolver intenciones programadas por la prueba | `QA-PER-05`, `QA-DIS-02` | `IMotorConversacional` y su conjunto cerrado de intenciones se conservan: un proveedor real es otro adaptador detrás del mismo contrato |
| El Asistente llega al Orquestador por una interfaz interna del dominio (`Protocol`) y no por una llamada de red | [ADR-IT6-001](../RONDA_2/ADRs/ITERACION_1/ADR-IT6-001.md) | El Asistente no importa al Orquestador ni a ninguna base; la conexión se ensambla en la composición. En el paso 5 es la interfaz interna del Orquestador |
| El filtro de inyección usa patrones fijos y el conjunto cerrado de intenciones | [ADR-IT7-001](../RONDA_2/ADRs/ITERACION_2/ADR-IT7-001.md) | El filtro sigue antes del motor y se verifica con un conjunto fijo de mensajes. Un clasificador entrenado no cambia la responsabilidad del componente. |

## Fuera de Alcance

* El contrato de `agregarReserva`, `actualizarReserva`, `eliminarReserva` y `verificarPermiso`: [SPEC-REF-04](SPEC-REF-04.md).
* La cola de casos de ayuda, `abrirCaso` y la vuelta por «Novedades»: [SPEC-REF-05](SPEC-REF-05.md).
* Cotización y sus 800 ms, salvo el aislamiento de los nodos del asistente respecto de esos nodos.
* La privacidad del contenido de los mensajes: el texto del viajero viaja a un proveedor de IA externo, y ningún ADR trata ese riesgo.
* Varios proveedores de modelo con conmutación entre ellos.
* La limitación de tasa de los mensajes del chat, que corresponde al API Gateway.
* Guardar el historial de las conversaciones.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-22 | Versión inicial (`borrador`) | Creación a partir de `REF-07` y de los ADR aceptados de [RONDA_2/ITERACION_1.md](../RONDA_2/ITERACION_1.md) y [RONDA_2/ITERACION_2.md](../RONDA_2/ITERACION_2.md) |
| 2026-11-23 | Renumerado de los ADR de la Ronda 2 | Los identificadores `ADR-IT1-*` y `ADR-IT2-*` de la Ronda 2 chocaban con los de la Ronda 1. Pasan a `ADR-IT6-*` y `ADR-IT7-*`, alineados con la numeración global de iteraciones |
| 2026-11-23 | Decisiones de revisión | Contexto firmado; confirmación por acción estructurada; filtro de reglas más conjunto cerrado de intenciones; número de la agencia desde el Orquestador; Circuit Breaker con semi-abierto; menú guiado con acciones sin motor; resumen del diálogo determinista; criterios de aceptación nuevos |
| 2026-11-23 | Corrección de `AC-REF-07-22` | El criterio pedía una acción propuesta con un proveedor que demora 30 segundos, pero el time-out hacia el proveedor es de 20 segundos y a los 20 se degrada al número y el menú. Ahora distingue la demora menor al time-out (propone la acción) de la mayor (degrada), sin tocar el time-out |
| 2026-11-23 | Decisiones de implementación fijadas (`PLAN-REF-07`) | Motor simulado por reglas; resolución de la reserva por referencia con candidatas; cota del turno con degradación; qué cuenta el circuito; contexto atado a la cuenta y al itinerario; datos mínimos de un alta y viaje por defecto; reintento de la confirmación tras una falla; interfaz interna del Orquestador |
