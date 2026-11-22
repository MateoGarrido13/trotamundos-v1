# SPEC-REF-07. Asistente virtual (Chatbot)

* **Estado:** borrador
* **Fecha:** 2026-11-22
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `REF-07`, `QA-DIS-02`, `QA-PER-05`, `QA-SEG-04`, `QA-SEG-02` |
| **ADRs** | [ADR-IT1-001](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-001.md), [ADR-IT1-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-002.md), [ADR-IT1-003](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-003.md), [ADR-IT1-004](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-004.md), [ADR-IT2-001](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-001.md), [ADR-IT2-002](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-002.md), [ADR-IT2-003](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-003.md), [ADR-IT2-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-004.md) |
| **Elemento del paso 5** | [RONDA_2/ITERACION_1.md](../RONDA_2/ITERACION_1.md) Módulo de Asistente Virtual e `IMotorConversacional`; [RONDA_2/ITERACION_2.md](../RONDA_2/ITERACION_2.md) filtrado de inyección, cota de 35 segundos, time-out y Circuit Breaker |
| **Incremento (Slice)** | Slice 5 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

Implementar un bot conversacional integrado que actúe como primer nivel de soporte interactivo para gestionar reprogramaciones, consultas de estado y problemas menores, delegando a la agencia de viajes preferida del usuario únicamente aquellos casos complejos.

Las escrituras de primer nivel usan las operaciones de [SPEC-REF-04](SPEC-REF-04.md). La delegación usa la cola y `IAgencia` de [SPEC-REF-05](SPEC-REF-05.md).

## Drivers que guían el cómo

* **`QA-PER-05`:** con un proveedor de modelo de IA disponible, la respuesta al viajero llega en como máximo 35 segundos. *(Origen: [RONDA_2/LISTADO_DRIVERS_RONDA_2.md](../RONDA_2/LISTADO_DRIVERS_RONDA_2.md))*
* **`QA-DIS-02`:** si ningún proveedor de modelo de IA está disponible, el asistente muestra el número de contacto de la agencia de viajes preferida del usuario. En el 100 % de las consultas en esa condición, el viajero recibe ese número. *(Origen: [RONDA_2/LISTADO_DRIVERS_RONDA_2.md](../RONDA_2/LISTADO_DRIVERS_RONDA_2.md))*
* **`QA-SEG-04`:** ante una inyección de prompt, o un pedido distinto de una reprogramación, una consulta de estado, un problema menor o la delegación de un caso complejo, el asistente no obedece la instrucción y no responde fuera del propósito de `REF-07`. Como alternativa, ofrece el número de contacto de la agencia de viajes preferida. *(Origen: [RONDA_2/LISTADO_DRIVERS_RONDA_2.md](../RONDA_2/LISTADO_DRIVERS_RONDA_2.md))*
* **`QA-SEG-02`:** una escritura de primer nivel pasa por el permiso y la auditoría del Orquestador. Sin permiso, el rechazo es el mismo que en la gestión manual. *(Origen: [ADR-IT1-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-002.md); el contrato está en [SPEC-REF-04](SPEC-REF-04.md))*

## Conceptos de diseño aceptados

* **Módulo en nodos propios, detrás del API Gateway** ([ADR-IT1-001](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-001.md)): el Módulo de Asistente Virtual corre en nodos propios, sin estado, detrás del API Gateway, separado de los nodos que resuelven la cotización. Llega al Orquestador por su interfaz interna.
* **Invocación al Orquestador con identidad y clave de operación** ([ADR-IT1-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-002.md)): el primer nivel llama a las operaciones del Orquestador propagando la identidad del actor y una clave de operación. El control de acceso y la auditoría son los de esa operación. Una misma clave no aplica dos veces la reprogramación.
* **Delegación asíncrona por la cola de casos de ayuda** ([ADR-IT1-003](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-003.md)): un caso complejo se delega invocando la apertura de caso en el Orquestador, con el resumen del diálogo y la reserva afectada. El pedido sale por la cola de casos de ayuda hacia `IAgencia`. El viajero ve el caso «en trámite» y las respuestas en «Novedades».
* **`IMotorConversacional` con cota y degradación a menú** ([ADR-IT1-004](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-004.md)): `interpretar(mensaje, contexto)` abstrae el motor. Si la cota vence, el asistente degrada a opciones guiadas de primer nivel, sin Retry bloqueante.
* **Filtrado de inyección de prompt** ([ADR-IT2-001](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-001.md)): un módulo intercepta, antes de `IMotorConversacional`, cualquier mensaje que intente instrucciones distintas de reprogramaciones, consultas de estado, problemas menores o delegación a la agencia. La respuesta permanece dentro de `REF-07` y ofrece el número de contacto de la agencia preferida.
* **Cota de 35 segundos** ([ADR-IT2-002](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-002.md)): la espera de `IMotorConversacional` no pasa de 35 segundos para el viajero. Si el proveedor no responde, el viajero recibe el número de contacto de la agencia preferida dentro de esa cota.
* **Clasificación en dos niveles** ([ADR-IT2-003](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-003.md)): primer nivel es lo que se resuelve con las operaciones ya existentes sobre el itinerario (consultas de estado o novedades, reprogramaciones o bajas sobre reservas editables). Caso complejo es lo que involucra dinero, penalidades de proveedor o un tercero que no responde: reembolsos, disputas, tramos con penalidad, proveedor caído o pedido explícito del viajero. El escalamiento pasa por el Orquestador.
* **Time-out y Circuit Breaker** ([ADR-IT2-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-004.md)): el time-out hacia el proveedor de modelo se agota antes de los 35 segundos, libera el hilo y muestra el número de contacto. A la quinta vez consecutiva, el Circuit Breaker pasa a abierto, corta las llamadas a ese proveedor y la respuesta por defecto sale en 0 ms, hasta que el proveedor se recupere.

## Relaciones Permitidas

* **Recibe llamadas / mensajes de:** Cliente web y Cliente móvil, por el API Gateway, con la identidad ya verificada.
* **Invoca / publica hacia:** `IMotorConversacional.interpretar(mensaje, contexto)`, después del filtro de inyección. El Orquestador, con las operaciones de [SPEC-REF-04](SPEC-REF-04.md) para el primer nivel y con la apertura de caso de [SPEC-REF-05](SPEC-REF-05.md) para el caso complejo.
* **Restricciones de frontera:** el Asistente no lee ni escribe la Base de viajes. No llama a la API de la agencia. No hay Retry bloqueante contra el motor dentro del turno del viajero. El filtro corre antes de `IMotorConversacional`.

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen (ADR / Iteración) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Turno de chat | Síncrono, cliente por el API Gateway | Mensaje e identidad verificada | Respuesta de primer nivel, menú guiado, número de la agencia, o caso «en trámite» | 35 segundos como máximo | `QA-PER-05`, [ADR-IT2-002](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-002.md) |
| Filtro de inyección | Interno, antes del motor | Mensaje del viajero | Mensaje aceptado hacia `interpretar`, o rechazo dentro de `REF-07` con el número de la agencia | [sin especificar] el criterio textual fino del filtro, más allá de los cuatro propósitos nombrados | [ADR-IT2-001](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-001.md) |
| `interpretar(mensaje, contexto)` | Síncrono, hacia el adaptador del motor, sin Retry | Mensaje ya filtrado y contexto | Intención tipada | Time-out interior a los 35 segundos: [sin especificar] la duración exacta | [ADR-IT1-004](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-004.md), [ADR-IT2-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-004.md) |
| Escritura de primer nivel | Hacia el Orquestador, igual que la gestión manual | Identidad del actor, clave de operación, y la operación `agregarReserva`, `actualizarReserva(id)` o `eliminarReserva(id)` | El resultado de [SPEC-REF-04](SPEC-REF-04.md), después de la confirmación del viajero | Sin permiso, la misma denegación y auditoría de esa spec | [ADR-IT1-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-002.md) |
| Apertura de caso complejo | Hacia el Orquestador | Resumen del diálogo y reserva afectada | Caso «en trámite» por [SPEC-REF-05](SPEC-REF-05.md) | La agencia no se llama desde el Asistente | [ADR-IT1-003](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-003.md), [ADR-IT2-003](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-003.md) |

## Reglas de Comportamiento

1. **Primer nivel:** consultas de estado o novedades, y reprogramaciones o bajas sobre reservas editables, se resuelven con las operaciones del Orquestador. Una escritura pide confirmación del viajero antes de ejecutarse. *(Origen: [RONDA_2/ITERACION_1.md](../RONDA_2/ITERACION_1.md), [ADR-IT2-003](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-003.md))*
2. **Caso complejo:** reembolsos, disputas, tramos con penalidad, proveedor caído o un pedido explícito de escalar se delegan por el Orquestador hacia la cola de casos de ayuda, con el resumen y la reserva afectada. *(Origen: [ADR-IT2-003](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-003.md))*
3. **Permisos:** la identidad y la clave de operación viajan en la llamada. Sin permiso, el Orquestador rechaza y audita como en la gestión manual. *(Origen: [ADR-IT1-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-002.md))*
4. **Inyección:** el filtro corre antes del motor. La respuesta no sale del propósito de `REF-07` y ofrece el número de la agencia preferida. *(Origen: [ADR-IT2-001](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-001.md))*
5. **Tiempo:** el viajero recibe una respuesta en como máximo 35 segundos. Si el motor no responde, esa respuesta es el número de contacto de la agencia preferida, y el chat puede pasar al menú guiado. *(Origen: [ADR-IT2-002](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-002.md), [ADR-IT1-004](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-004.md))*
6. **Proveedor caído:** el time-out se agota antes de los 35 segundos. Al quinto time-out consecutivo el Circuit Breaker queda abierto y el número de la agencia sale en 0 ms, sin llamar al proveedor, hasta que se recupere. *(Origen: [ADR-IT2-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-004.md))*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-REF-07-01` | Hay un proveedor de modelo disponible y el viajero confirma una reprogramación simple | Envía esa consulta al asistente | El Asistente llama a `actualizarReserva` en el Orquestador con la identidad y la clave de operación, y la respuesta llega en como máximo 35 segundos | `REF-07`, `QA-PER-05`, [ADR-IT1-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-002.md) | Test automático |
| `AC-REF-07-02` | La misma clave de operación ya aplicó esa reprogramación | El turno se reintenta | El Orquestador no aplica la reprogramación por segunda vez | [ADR-IT1-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-002.md) | Test automático |
| `AC-REF-07-03` | El actor no tiene permiso sobre el itinerario | Pide por el asistente registrar o reprogramar | No se escribe la reserva y la denegación queda auditada como en [SPEC-REF-04](SPEC-REF-04.md) | `QA-SEG-02`, [ADR-IT1-002](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-002.md) | Test automático |
| `AC-REF-07-04` | El viajero describe un reembolso, una disputa, un tramo con penalidad, un proveedor caído, o pide escalar | El asistente clasifica el turno | Invoca la apertura de caso en el Orquestador con el resumen y la reserva afectada, y el viajero ve «en trámite». El Asistente no llama a la API de la agencia | `REF-07`, [ADR-IT1-003](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-003.md), [ADR-IT2-003](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-003.md) | Test automático |
| `AC-REF-07-05` | El mensaje intenta una inyección de prompt o pide algo fuera de `REF-07` | Llega al asistente | No alcanza a `IMotorConversacional`. La respuesta queda dentro de `REF-07` y ofrece el número de contacto de la agencia preferida | `QA-SEG-04`, [ADR-IT2-001](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-001.md) | Test automático |
| `AC-REF-07-06` | Ningún proveedor de modelo responde | El viajero acaba de enviar una consulta | Dentro de los 35 segundos ve el número de contacto de su agencia preferida | `QA-DIS-02`, `QA-PER-05`, [ADR-IT2-002](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-002.md), [ADR-IT2-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-004.md) | Test automático |
| `AC-REF-07-07` | El proveedor acumuló cinco time-out consecutivos y el Circuit Breaker está abierto | Llega otra consulta | El número de la agencia sale en 0 ms y no se llama al proveedor | `QA-DIS-02`, [ADR-IT2-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-004.md) | Test automático |
| `AC-REF-07-08` | El motor supera la cota o no responde, y el Circuit Breaker no está abierto | Vence la espera | El viajero obtiene el menú guiado de primer nivel, que incluye consultar estado, reprogramar y derivar a la agencia, sin un Retry bloqueante del motor | [ADR-IT1-004](../RONDA_2/ADRs/ITERACION_1/ADR-IT1-004.md) | Test automático |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| Cota de respuesta al viajero | 35 segundos | Tiempo máximo hasta la respuesta del turno, incluida la degradación | `QA-PER-05`, [ADR-IT2-002](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-002.md) |
| Duración del time-out hacia el proveedor de modelo | [sin especificar] | Cota interior a los 35 segundos. Al agotarse se muestra el número de la agencia | [ADR-IT2-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-004.md) |
| Umbral del Circuit Breaker | 5 time-out consecutivos | A partir de ahí el circuito queda abierto | [ADR-IT2-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-004.md) |
| Respuesta con el circuito abierto | 0 ms, sin llamar al proveedor | Tiempo de la respuesta por defecto | [ADR-IT2-004](../RONDA_2/ADRs/ITERACION_2/ADR-IT2-004.md) |
| Dónde se guarda el número de contacto de la agencia preferida | [sin especificar] | Origen del número que se muestra en `QA-DIS-02` y `QA-SEG-04` | Los ADR nombran el número y no fijan su almacenamiento |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| El proveedor de modelo se simula con un mock local al que se le puede inyectar demora, time-out o caída | `QA-PER-05`, `QA-DIS-02`, `CON-02` | `IMotorConversacional`, el filtro, la cota y el Circuit Breaker se conservan. Lo permite [POLITICAS_SPECS_Y_PLANES.md](../POLITICAS_SPECS_Y_PLANES.md) §4.6. |

## Fuera de Alcance

* El contrato de `agregarReserva`, `actualizarReserva`, `eliminarReserva` y `verificarPermiso`: [SPEC-REF-04](SPEC-REF-04.md).
* La cola de casos de ayuda, `abrirCaso` y la vuelta por «Novedades»: [SPEC-REF-05](SPEC-REF-05.md).
* Cotización y sus 800 ms, salvo el aislamiento de los nodos del asistente respecto de esos nodos.
* Dónde está almacenado el número de la agencia, hasta que se especifique.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-22 | Versión inicial (`borrador`) | Creación a partir de `REF-07` y de los ADR aceptados de [RONDA_2/ITERACION_1.md](../RONDA_2/ITERACION_1.md) y [RONDA_2/ITERACION_2.md](../RONDA_2/ITERACION_2.md) |
