# SPEC-REF-05. Resolución de problemas

* **Estado:** aprobada
* **Fecha:** 2026-11-23
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `REF-05`, `CON-02` |
| **ADRs** | `ADR-IT4-010`, `ADR-IT3-002`, `ADR-IT3-003`, `ADR-IT4-007`, `ADR-IT4-008` |
| **Elemento del paso 5** | [RONDA_1/ITERACION_4.md](../RONDA_1/ITERACION_4.md) `IAgencia`, Adaptador de agencia, cola de casos de ayuda |
| **Incremento (Slice)** | Slice 5 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

El sistema debe integrarse con la agencia de viajes preferida del usuario para facilitar una rápida resolución de problemas.

El Orquestador guarda el caso y publica el pedido en la cola de casos de ayuda. El Adaptador de agencia, detrás de `IAgencia`, lo entrega a la API de la agencia. [SPEC-REF-07](SPEC-REF-07.md) usa este mismo camino cuando delega un caso complejo. No forma parte de esta spec la clasificación de ese caso.

## Drivers que guían el cómo

* **`CON-02`:** la agencia se integra por API. `IAgencia` extiende `IProveedor` con `abrirCaso(caso)` y `consultarCaso(idCaso)`. Una agencia nueva es un adaptador más, sin tocar al Orquestador. *(Origen: [RONDA_1/ITERACION_4.md](../RONDA_1/ITERACION_4.md); [ADR-IT4-010](../RONDA_1/ADRs/ITERACION_4/ADR-IT4-010.md))*

## Conceptos de diseño aceptados

* **Adaptador de agencia detrás de `IAgencia`, con pedidos asíncronos por el Broker** (`ADR-IT4-010`): la capa anti-corrupción aísla el contrato de cada agencia. El Orquestador guarda el caso y la agencia preferida del viajero y publica el pedido en la cola de casos de ayuda. El adaptador, en nodos propios junto a la ingesta, lo entrega con Retry e identificador único. Las novedades del caso entran por la cola de novedades y la ingesta. La cola queda acotada, con la misma regla de tamaño máximo y de Retry que las colas ya decididas. El viajero ve el caso «en trámite». Si se agotan los reintentos, el caso queda «sin entregar», visible en «Novedades», con opción de reintentar.
* **Colas acotadas y Retry con identificador único** (`ADR-IT3-002`, `ADR-IT3-003`): ante una cola llena, el Orquestador de viajes reintenta la publicación del pedido. Cada pedido lleva un identificador único asignado por quien publica, y el que agota sus reintentos va a la cola de mensajes muertos, con aviso a operaciones.
* **Autorización y auditoría** (`ADR-IT4-007`) **y clave de operación** (`ADR-IT4-008`): las operaciones del Orquestador declaran el permiso que exigen, dejan su asiento de auditoría en la misma transacción y llevan una clave de operación para que un reintento del cliente no duplique.

## Relaciones Permitidas

* **Recibe llamadas / mensajes de:** el viajero, por el gateway y el balanceador, elige su agencia, reporta un problema, reintenta un caso y consulta sus casos. [SPEC-REF-07](SPEC-REF-07.md) invoca la apertura de caso en el Orquestador. El Adaptador consume la cola de casos de ayuda. La agencia avisa al listener del Adaptador cuando cambia un caso.
* **Invoca / publica hacia:** la cola de casos de ayuda; la API de la agencia mediante `abrirCaso(caso)` y `consultarCaso(idCaso)`; la cola de novedades, con cada cambio de estado del caso. El Orquestador recibe esas novedades por el Servicio de ingesta.
* **Restricciones de frontera:** el viajero no llama a la API de la agencia. El Adaptador no escribe la Base de viajes ni la lee: no sabe qué casos hay abiertos, y todo cambio de estado vuelve por la cola de novedades, la ingesta y el Orquestador. `ICanal` no transporta el ciclo de vida del caso. El pedido no es una llamada síncrona que deje al viajero esperando a la agencia.

## Estados del caso

| Estado | Significado | Cómo se llega |
| :--- | :--- | :--- |
| **En trámite** | El Orquestador guardó el caso. Puede estar esperando lugar en la cola o en camino a la agencia | El Orquestador, al reportar o al reintentar |
| **Abierto** | La agencia recibió y abrió el caso | Novedad que informa la agencia |
| **En curso** | La agencia está trabajando en el caso | Novedad que informa la agencia |
| **Resuelto** | La agencia lo resolvió. Es final: no se reabre en el prototipo | Novedad que informa la agencia |
| **Sin entregar** | No se pudo entregar el pedido a la agencia. Se puede reintentar | Novedad que publica el Adaptador al agotar sus reintentos, o el Orquestador al agotar los de publicación |

Los estados solo avanzan (en trámite, abierto, en curso, resuelto). Una novedad que retrocedería el estado se ignora. «Sin entregar» solo se sale reintentando, que vuelve el caso a «en trámite».

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen (ADR / Iteración) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `elegirAgenciaPreferida(agencia, consentimiento)` | Síncrono, cliente por el gateway hacia el Orquestador | Identidad del actor, agencia y consentimiento explícito de que la reserva afectada y la descripción del problema viajarán a ese tercero | Agencia preferida y consentimiento guardados | Sin consentimiento, o agencia que no está registrada como adaptador: rechazo sin guardar | `ADR-IT4-010` |
| Reportar problema | Síncrono hasta el Orquestador. El resto es asíncrono por cola | Identidad del actor, clave de operación, reserva afectada, descripción del problema y, si lo trae el asistente, el resumen del diálogo | Caso «en trámite», con su identificador único y la agencia vigente al reportar | Sin permiso `registrar` sobre el itinerario: acceso denegado, con asiento. Sin agencia preferida o sin consentimiento, o reserva inexistente: rechazo sin crear el caso. Cola llena: el caso se guarda «en trámite» y el Orquestador reintenta la publicación. El viajero no recibe confirmación inmediata de la agencia | `ADR-IT4-010`, `ADR-IT3-002`, `ADR-IT4-007` |
| Reintentar un caso | Síncrono, cliente por el gateway hacia el Orquestador | Identidad del actor, clave de operación e identificador del caso | El caso vuelve a «en trámite» y el pedido se publica de nuevo con el mismo identificador | Caso que no está «sin entregar»: rechazo sin efecto. Sin permiso `registrar`: acceso denegado, con asiento | `ADR-IT4-010`, `ADR-IT3-003` |
| Consultar agencia preferida | Síncrono, solo lectura, hacia el Orquestador | Identidad del actor | Nombre y número de contacto de la agencia preferida, o la falta de agencia. El número se guarda con la agencia en la configuración | Sin agencia elegida: respuesta que lo indica, no error. Lo usa [SPEC-REF-07](SPEC-REF-07.md) | `ADR-IT4-010` |
| Consultar casos | Síncrono, solo lectura | Identidad del actor | Los casos del viajero con su estado, que es lo que se ve en «Novedades» | Sin casos: lista vacía, no error | `ADR-IT4-010` |
| `abrirCaso(caso)` | El Adaptador llama a la API de la agencia, con Retry e identificador único | Caso publicado en la cola de casos de ayuda | Pedido entregado, o reintento | Al agotar reintentos, el Adaptador publica la novedad «sin entregar» | `ADR-IT4-010` |
| Aviso de la agencia | La agencia llama al listener del Adaptador | Identificador del caso y la clave compartida | El Adaptador llama a `consultarCaso` y publica la novedad con el estado | Clave inválida: rechazo sin efecto. Caso desconocido para la agencia: no se publica nada | `ADR-IT4-010` |
| `consultarCaso(idCaso)` | El Adaptador llama a la API de la agencia | Identificador del caso | Estado que informe la agencia | Sin respuesta: el aviso se pierde y la agencia puede avisar de nuevo | `ADR-IT4-010` |
| Novedad de caso | Asíncrona, por la cola de novedades y la ingesta | Identificador del caso y estado | El Orquestador aplica el estado y el viajero lo ve en «Novedades» | El identificador de la novedad se forma con el del caso y el estado, para que la ingesta descarte repetidas | `ADR-IT4-010`, `ADR-IT3-003` |

## Reglas de Comportamiento

1. **Desacople:** el Orquestador persiste el caso, lo publica en la cola de casos de ayuda y muestra «en trámite» sin esperar a la agencia. *(Origen: `ADR-IT4-010`)*
2. **Entrega:** el Adaptador consume la cola y llama a `abrirCaso(caso)` con Retry y un identificador único. Un reintento no duplica el pedido. *(Origen: `ADR-IT4-010`)*
3. **Vuelta por novedades:** todo cambio de estado del caso, incluido «abierto» y «sin entregar», entra por la cola de novedades y la ingesta, y el Orquestador lo refleja en «Novedades». El Adaptador nunca escribe la base. *(Origen: [RONDA_1/ITERACION_4.md](../RONDA_1/ITERACION_4.md), `ADR-IT4-010`)*
4. **Aviso liviano:** la agencia avisa con el identificador del caso. El Adaptador obtiene el estado con `consultarCaso` y recién entonces publica la novedad. *(Origen: `ADR-IT4-010`)*
5. **Reintentos agotados:** el caso queda «sin entregar», visible en «Novedades», con opción de reintentar. Reintentar publica el pedido de nuevo con el mismo identificador, para no duplicar si la agencia ya lo había abierto. *(Origen: `ADR-IT4-010`, `ADR-IT3-003`)*
6. **Cola llena:** el Orquestador guarda el caso «en trámite» y reintenta la publicación con espera creciente. Si agota esos reintentos, el caso queda «sin entregar». *(Origen: `ADR-IT3-002`)*
7. **Consentimiento:** la reserva afectada y la descripción del problema viajan a un tercero. Sin consentimiento y sin agencia preferida no se abre un caso. *(Origen: `ADR-IT4-010`)*
8. **Autorización:** reportar y reintentar exigen el permiso `registrar` sobre el itinerario de la reserva, y dejan su asiento de auditoría. La agencia es la preferida del actor, y el caso guarda la que estaba vigente al reportar. *(Origen: `ADR-IT4-007`)*
9. **Idempotencia del reporte:** la clave de operación evita que un doble toque abra dos casos. *(Origen: `ADR-IT4-008`)*
10. **Estados que solo avanzan:** una novedad que retrocede el estado se ignora. *(Origen: `ADR-IT4-010`)*
11. **Agencia nueva:** una agencia se suma como un adaptador más, registrado en la configuración, sin cambios en el Orquestador. *(Origen: `CON-02`, `ADR-IT4-010`)*
12. **Itinerario y reserva:** el reporte indica el itinerario y la reserva. Primero se verifica el permiso `registrar` sobre ese itinerario y después que la reserva sea de él y no esté dada de baja, así que no se revela si una reserva existe a quien no tiene permiso. *(Origen: `ADR-IT4-007`)*
13. **Quién ve y reintenta un caso:** cada viajero ve solo los casos que él reportó y solo él los reintenta, además de tener el permiso `registrar` sobre el itinerario. Un caso ajeno es indistinguible de uno inexistente. *(Origen: `ADR-IT4-010`)*
14. **Publicación:** el Orquestador publica el pedido después de confirmar la escritura, en segundo plano, con reintentos de 1 s, 2 s y 4 s si la cola está llena. Si el proceso se detiene durante esos reintentos, el caso queda «en trámite» sin publicarse. *(Origen: `ADR-IT3-002`)*
15. **Pedido a la agencia:** lleva el identificador del caso, la agencia, la reserva afectada (identificador, tipo, lugar y fechas), la descripción y el resumen del diálogo. No incluye miembros, cuentas ni otras reservas del itinerario. Reintentar vuelve a publicar el mismo pedido guardado. *(Origen: `ADR-IT4-010`)*
16. **Estados:** «sin entregar» solo se alcanza desde «en trámite» y solo se sale reintentando: una novedad sobre un caso «sin entregar» o «resuelto» se ignora. *(Origen: `ADR-IT4-010`)*
17. **Aviso de la agencia:** cada agencia avisa en su propia ruta (`POST /agencia/{agencia}/avisos`) con la clave compartida en `X-Clave-Agencia`. Clave inválida: 401 sin consultar nada. Agencia sin adaptador: 404. Agencia que no responde a `consultarCaso` o cola de novedades llena: 503, y la agencia puede avisar de nuevo. Caso desconocido para la agencia: 200 sin publicar nada. *(Origen: `ADR-IT4-010`, `ADR-IT3-002`)*
18. **Respuestas del viajero:** 403 acceso denegado; 404 la reserva o el caso no existe; 409 hay que elegir agencia y dar consentimiento antes de reportar, o el caso no está «sin entregar»; 422 consentimiento ausente, agencia no registrada o descripción vacía o de más de 2000 caracteres. Una clave repetida devuelve el resultado de la primera operación. *(Origen: `ADR-IT4-007`, `ADR-IT4-008`)*
19. **Agencia preferida y contacto:** consultar la agencia preferida devuelve su nombre y el número de contacto que la configuración guarda para ella, o ambos vacíos si el viajero no eligió una (no es un error). *(Origen: `ADR-IT4-010`)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-REF-05-01` | El viajero tiene una agencia preferida con consentimiento y una reserva | Reporta un problema sobre esa reserva | El Orquestador guarda el caso, lo publica en la cola de casos de ayuda y le muestra «en trámite» | `REF-05`, `ADR-IT4-010` | Test automático |
| `AC-REF-05-02` | Hay un caso en la cola de casos de ayuda | El Adaptador de agencia lo consume | Llama a `abrirCaso(caso)` contra la API de la agencia | `REF-05`, `CON-02`, `ADR-IT4-010` | Test automático |
| `AC-REF-05-03` | La entrega a la agencia falla y se reintenta con el mismo identificador | El Adaptador reintenta | No se abre un segundo caso por ese mismo pedido | `ADR-IT4-010` | Test automático |
| `AC-REF-05-04` | Se agotan los reintentos de entrega | El Adaptador deja de reintentar | El Adaptador publica la novedad «sin entregar», el caso queda «sin entregar» y visible en «Novedades», con opción de reintentar | `ADR-IT4-010` | Test automático |
| `AC-REF-05-05` | La agencia avisa un cambio de un caso | El Adaptador consulta el estado y lo publica en la cola de novedades | El Servicio de ingesta se lo entrega al Orquestador y el viajero lo ve en «Novedades» | `REF-05`, `ADR-IT4-010` | Test automático |
| `AC-REF-05-06` | El viajero no da su consentimiento | Intenta elegir su agencia | Se rechaza y no se guarda ni la agencia ni el consentimiento | `ADR-IT4-010` | Test automático |
| `AC-REF-05-07` | El viajero no tiene agencia preferida o no dio su consentimiento | Intenta reportar un problema | Se rechaza y no se crea ningún caso | `ADR-IT4-010` | Test automático |
| `AC-REF-05-08` | El actor no tiene el permiso `registrar` sobre el itinerario de la reserva | Intenta reportar un problema | Acceso denegado, no se crea el caso y queda el asiento de la denegación | `ADR-IT4-007` | Test automático |
| `AC-REF-05-09` | La misma clave de operación ya abrió un caso | El cliente reintenta el reporte | No aparece un segundo caso | `ADR-IT4-008` | Test automático |
| `AC-REF-05-10` | La cola de casos de ayuda está llena | El viajero reporta un problema | El caso se guarda «en trámite» y el Orquestador reintenta la publicación. Cuando hay lugar, el pedido se publica | `ADR-IT3-002` | Test automático |
| `AC-REF-05-11` | La cola de casos sigue llena y el Orquestador agota sus reintentos de publicación | Se cumple el último reintento | El caso queda «sin entregar» | `ADR-IT3-002`, `ADR-IT4-010` | Test automático |
| `AC-REF-05-12` | Un caso está «sin entregar» | El viajero lo reintenta | El caso vuelve a «en trámite» y el pedido se publica de nuevo con el mismo identificador | `ADR-IT4-010`, `ADR-IT3-003` | Test automático |
| `AC-REF-05-13` | Un caso no está «sin entregar» | El viajero intenta reintentarlo | Se rechaza sin efecto | `ADR-IT4-010` | Test automático |
| `AC-REF-05-14` | Llega un aviso con una clave compartida inválida | El listener del Adaptador lo recibe | Se rechaza y no se consulta ni se publica nada | `ADR-IT4-010` | Test automático |
| `AC-REF-05-15` | Un caso está «en curso» | Llega una novedad «abierto» | Se ignora y el caso sigue «en curso» | `ADR-IT4-010` | Test automático |
| `AC-REF-05-16` | Se registra un segundo adaptador que implementa `IAgencia` | El viajero elige esa agencia y reporta un problema | El pedido se entrega a esa agencia sin cambios en el Orquestador | `CON-02`, `ADR-IT4-010` | Test automático |
| `AC-REF-05-17` | El asistente invoca la apertura de caso con el resumen del diálogo | El Orquestador guarda el caso | El caso guarda el resumen y el pedido que recibe la agencia lo incluye | `REF-05`, `ADR-IT4-010` | Test automático |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| Tamaño máximo de la cola de casos de ayuda | 100 pedidos (5 en los tests), configurable | Tope de pedidos retenidos en esa cola | `ADR-IT4-010`, que aplica la cota de `ADR-IT3-002` |
| Límite de reintentos y backoff de la entrega a la agencia | 3 reintentos con espera de 1 s, 2 s y 4 s | Cuántas veces y con qué espera se reintenta `abrirCaso` | `ADR-IT4-010`, que aplica `ADR-IT3-003` |
| Reintentos de publicación del Orquestador con la cola llena | 3 reintentos con espera de 1 s, 2 s y 4 s | Cuántas veces y con qué espera el Orquestador reintenta publicar el pedido | `ADR-IT3-002` |
| Retención de las claves de operación | 7 días, como en [SPEC-REF-04](SPEC-REF-04.md) | Cuánto tiempo se guardan para reconocer un reintento del reporte | `ADR-IT4-008` |
| Modo en que la agencia informa un cambio | Aviso al listener con el identificador del caso y consulta posterior con `consultarCaso` | Cómo el Adaptador se entera de un cambio sin leer la base | `ADR-IT4-010` |
| Largo máximo de la descripción del problema | 2000 caracteres | Tope de lo que el viajero cuenta y viaja a la agencia | `ADR-IT4-010` |
| Número de contacto de cada agencia | Configurable por agencia (`TROTA_AGENCIAS_CONTACTO`) | El número que devuelve la consulta de la agencia preferida | `ADR-IT4-010` |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| La API de la agencia se simula con un mock local al que se le puede inyectar demora o caída, y que puede avisar cambios de estado | `CON-02` | `IAgencia`, el Adaptador y la cola se conservan. Lo permite [POLITICAS_SPECS_Y_PLANES.md](../POLITICAS_SPECS_Y_PLANES.md) §4.6. |
| El aviso de la agencia se autentica con una clave compartida tomada de una variable de entorno | `ADR-IT4-010` | El Adaptador sigue siendo la capa anti-corrupción que valida lo que entra de la agencia. La autenticación real depende de cada agencia. |
| Las claves de operación de los casos comparten tabla con las de la gestión manual, con el prefijo `caso:` | `ADR-IT4-008` | Cada cuenta puede repetir el mismo valor en reservas y en casos sin confundirlos |
| El Orquestador solo conoce los nombres de las agencias; los adaptadores se ensamblan en la composición | `CON-02`, `ADR-IT4-010` | El Orquestador no importa a los nodos de entrada, que es lo que permite sumar una agencia sin tocarlo |
| Las agencias disponibles se registran en la configuración, cada una con su nombre y su número de contacto | `CON-02` | La agencia sigue siendo un adaptador detrás de `IAgencia`. No hay catálogo de agencias gestionado por el sistema. |

## Fuera de Alcance

* Clasificación de primer nivel y casos complejos del asistente: [SPEC-REF-07](SPEC-REF-07.md).
* El texto de las novedades de Booking y el resto de la ingesta que no sea la vuelta de un caso de agencia. La ingesta de la cola de novedades sigue sin spec propia: esta spec solo exige que descarte repetidas por identificador, como la de [SPEC-REF-03](SPEC-REF-03.md).
* El canal `ICanal` como transporte del caso.
* Reabrir un caso resuelto y cancelar un caso.
* Una medida de tiempo de resolución: `REF-05` es un requerimiento funcional y no la tiene.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-22 | Versión inicial (`borrador`) | Creación a partir de `REF-05` y de `ADR-IT4-010` |
| 2026-11-23 | Operación de lectura de la agencia preferida y número de contacto en la configuración de agencias | Lo necesita [SPEC-REF-07](SPEC-REF-07.md) para mostrar el número en `QA-DIS-02`. Cambio aditivo, no modifica ningún criterio aprobado |
| 2026-11-23 | Decisiones de revisión | Operación para elegir la agencia con consentimiento; estados del caso; aviso liviano de la agencia con `consultarCaso`; cola llena con reintento del Orquestador; valores de parámetros; estados que solo avanzan; permiso `registrar` y clave de operación en el reporte; criterios de aceptación nuevos |
| 2026-11-23 | Decisiones de implementación fijadas (`PLAN-REF-05`) | Itinerario y reserva explícitos en el reporte; cada viajero ve y reintenta solo sus casos; publicación en segundo plano con el riesgo de un reinicio; contenido del pedido; «sin entregar» y «resuelto» no admiten novedades; ruta de aviso por agencia; códigos de respuesta; descripción de hasta 2000 caracteres; claves de operación con prefijo; consulta de la agencia preferida con su contacto |
