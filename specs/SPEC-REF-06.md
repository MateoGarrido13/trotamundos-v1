# SPEC-REF-06. Analítica de datos

* **Estado:** aprobada
* **Fecha:** 2026-11-23
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `REF-06`, `QA-PER-04*`, `QA-PER-02`, `QA-DIS-01` |
| **ADRs** | `ADR-IT5-001`, `ADR-IT5-002`, `ADR-IT4-008`, `ADR-IT4-009`, `ADR-IT3-002`, `ADR-IT3-003` |
| **Elemento del paso 5** | [RONDA_1/ITERACION_5.md](../RONDA_1/ITERACION_5.md) cola de eventos analíticos, Proyector analítico, Base analítica, Servicio de consultas analíticas |
| **Incremento (Slice)** | Slice 5 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

Trotamundos recopilará datos analíticos de los viajes (tendencias, destinos, cancelaciones) para su monetización por parte del equipo de datos, implicando la ejecución de consultas analíticas pesadas.

El Orquestador emite un evento anonimizado en cada alta, modificación, baja lógica o archivado de reserva o viaje. El Servicio de consultas analíticas responde el informe desde la Base analítica.

## Drivers que guían el cómo

* **`QA-PER-04*`:** es la contraparte de `REF-06`. El equipo de datos consulta tendencias, destinos y cancelaciones con el panel en operación (2 millones de usuarios activos por semana, 15 millones de cuentas, y un pico de domingo a lunes, de jueves a viernes o de una disrupción de viajes). El informe, en promedio, se procesa y se genera antes de los 10 segundos. *(Origen: [RONDA_1/ITERACION_5.md](../RONDA_1/ITERACION_5.md))*
* **`QA-PER-02`:** la consulta analítica no compite con la cotización ni usa los nodos del Orquestador. Durante el pico, el Orquestador solo encola un evento liviano. *(Origen: [RONDA_1/ITERACION_5.md](../RONDA_1/ITERACION_5.md), sección B.1; [ADR-IT5-001](../RONDA_1/ADRs/ITERACION_5/ADR-IT5-001.md))*
* **`QA-DIS-01`:** el camino analítico no lee la Base de viajes, ni la primaria ni la pasiva. La caída o la saturación de la Base analítica no afecta las operaciones de los viajeros. *(Origen: [ADR-IT5-001](../RONDA_1/ADRs/ITERACION_5/ADR-IT5-001.md))*

## Conceptos de diseño aceptados

* **Quinta cola, Proyector en nodos propios y Base analítica separada** (`ADR-IT5-001`): el Orquestador publica eventos anonimizados en la quinta cola del Broker. El Proyector analítico los consume en nodos propios, descarta duplicados por identificador de evento y escribe en una Base analítica distinta de la Base de viajes y de las Bases de cuentas. El Servicio de consultas analíticas lee solo esa base. La Base analítica no almacena correos ni credenciales.
* **Preagregación incremental y cota de 10 segundos** (`ADR-IT5-002`): el Proyector actualiza contadores y series por destino y fecha al ingresar cada evento. La consulta del equipo de datos lee esas tablas preagregadas. El Servicio abre una cota de 10 segundos. La Base analítica conserva los eventos históricos, de modo que una dimensión nueva se pueda recalcular a partir de ellos.
* **Colas acotadas y Retry con identificador único** (`ADR-IT3-002`, `ADR-IT3-003`): la quinta cola reutiliza la regla de tamaño máximo y de Retry de las colas anteriores. Ante una cola llena, el Orquestador reintenta la publicación. El evento que agota sus reintentos va a la cola de mensajes muertos, con aviso a operaciones.
* **Baja lógica** (`ADR-IT4-008`): la baja lógica de una reserva conserva la cancelación que el informe analítico necesita. El evento de esa baja entra al camino analítico.
* **`lugar`** (`ADR-IT4-009`): el destino del informe sale de `Reserva.lugar`. El evento lleva `lugar.destino`.

## Relaciones Permitidas

* **Recibe llamadas / mensajes de:** el equipo de datos, por el API Gateway, pide el informe al Servicio de consultas analíticas. El Proyector consume la cola de eventos analíticos.
* **Invoca / publica hacia:** el Orquestador publica en la quinta cola. El Proyector escribe la Base analítica. El Servicio lee la Base analítica.
* **Restricciones de frontera:** el Servicio de consultas analíticas no lee la Base de viajes ni llama a un nodo del Orquestador para armar el informe. El Orquestador no escribe la Base analítica. La cotización no publica ni espera este camino.

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen (ADR / Iteración) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Evento analítico | Asíncrono, cola del Broker. El Orquestador lo publica después de confirmar la escritura, sin demorar la respuesta al viajero | Alta, modificación, baja lógica o archivado de reserva o viaje. Lleva identificador único del evento, tipo de evento, tipo de reserva, `lugar.destino`, fechas, `origen` y estado. No lleva cuenta, correo, nombre, descripción libre, resumen de diálogo ni credenciales | Evento en la quinta cola | Cola llena: el Orquestador reintenta. Reintentos agotados: cola de mensajes muertos con aviso a operaciones. Un corte entre la escritura y la publicación puede perder el evento | `ADR-IT5-001`, `ADR-IT3-002`, `ADR-IT3-003`, [RONDA_1/ITERACION_5.md](../RONDA_1/ITERACION_5.md) |
| Proyección | El Proyector consume la cola y escribe la Base analítica | Evento analítico | El evento queda guardado y suma al contador de su tipo de evento por destino, día y tipo de reserva | Un identificador repetido no vuelve a sumar. Falla de escritura: Retry idempotente | `ADR-IT5-002` |
| Informe analítico | Síncrono, equipo de datos por el API Gateway | Cuenta autorizada, fecha desde, fecha hasta y, opcionalmente, destino y tipo de reserva | Informe con tres secciones, por día: tendencias (altas), destinos (ranking por cantidad de reservas) y cancelaciones (bajas por destino) | Cota de 10 segundos: al vencer, error de tiempo agotado y sin informe. Cuenta no autorizada: acceso denegado. Sin datos en el rango: secciones vacías, no error | `ADR-IT5-002`, `QA-PER-04*` |

## Reglas de Comportamiento

1. **Emisión:** cada alta, modificación, baja lógica o archivado de reserva o viaje en el Orquestador publica un evento anonimizado en la quinta cola, después de confirmar la escritura. La publicación no demora la respuesta al viajero. *(Origen: [RONDA_1/ITERACION_5.md](../RONDA_1/ITERACION_5.md), `ADR-IT5-001`)*
2. **Anonimización:** el evento no lleva datos personales de la cuenta. Ningún campo del evento permite identificar al viajero. *(Origen: `ADR-IT5-001`)*
3. **Aislamiento:** el informe no toca la Base de viajes ni un nodo del Orquestador. *(Origen: `ADR-IT5-001`)*
4. **Preagregación por tipo de evento:** el Proyector guarda cada evento y suma a un contador según su tipo de evento, por destino, día y tipo de reserva. No recalcula el estado de ninguna reserva, y no necesita saber a qué reserva pertenece el evento. La consulta lee esos contadores, no el histórico reserva por reserva. *(Origen: `ADR-IT5-002`)*
5. **Idempotencia:** el Proyector descarta un evento cuyo identificador ya guardó. El identificador se conserva mientras se conserve el evento. *(Origen: `ADR-IT5-002`, `ADR-IT3-003`)*
6. **Cota:** el Servicio de consultas analíticas abre una cota de 10 segundos. Si vence, devuelve un error de tiempo agotado y ningún informe parcial. En promedio, el informe se genera antes de los 10 segundos. *(Origen: `QA-PER-04*`, `ADR-IT5-002`)*
7. **Dimensiones:** el informe cubre tendencias (altas por día), destinos (`lugar.destino`) y cancelaciones (baja lógica). *(Origen: `REF-06`, `ADR-IT4-008`, `ADR-IT4-009`)*
8. **Acceso:** solo las cuentas autorizadas del equipo de datos piden el informe. Cualquier otra cuenta recibe acceso denegado. *(Origen: `REF-06`)*
9. **Aislamiento de fallas:** la caída o la saturación de la Base analítica no afecta las operaciones de los viajeros. *(Origen: `QA-DIS-01`, `ADR-IT5-001`)*
10. **Campos del evento:** el evento tiene una lista cerrada de campos: identificador del evento (aleatorio), tipo de evento, tipo de reserva, destino (el `lugar` de la reserva), fechas, origen, estado y el momento en que ocurrió. No lleva el identificador de la reserva, del viaje, del itinerario ni de la cuenta: el Proyector no sabe a qué reserva pertenece. *(Origen: `ADR-IT5-001`, `ADR-IT5-002`)*
11. **Día de los contadores:** el día es el día en que **ocurrió el evento**, en UTC: una alta cuenta el día en que se creó la reserva y una baja el día en que se canceló, no el día del viaje. *(Origen: `ADR-IT5-002`)*
12. **Evento de archivado:** un viaje archivado publica un solo evento, sin tipo de reserva ni destino. Se guarda y se cuenta, pero no entra a ninguna de las tres secciones del informe. *(Origen: `REF-06`)*
13. **Qué publica un evento:** cada alta, modificación y baja de la gestión manual, la reserva nueva que entra por el correo (alta con origen `correo`), una novedad aplicada (modificación con origen `proveedor`) y el archivado de un viaje. No publican las operaciones repetidas con la misma clave, las denegadas, las rechazadas ni las que fallan. Una novedad retenida por una edición manual tampoco, porque no cambió nada. *(Origen: `ADR-IT5-001`)*
14. **Informe:** tendencias (altas por día), destinos (los 100 primeros por cantidad de altas, con desempate alfabético) y cancelaciones (bajas por día y destino), sobre el rango pedido y con filtros opcionales de destino y tipo de reserva. Un destino vacío se informa sin destino. Un rango invertido se rechaza. *(Origen: `ADR-IT5-002`)*
15. **Cota doble:** la consulta se cancela en la Base analítica al vencer la cota y el servicio responde el error de tiempo agotado sin esperarla. *(Origen: `QA-PER-04*`)*
16. **Respuestas del informe:** 403 cuenta no autorizada (sin ningún dato), 504 tiempo agotado (sin informe parcial), 503 la Base analítica no responde, 422 fechas inválidas. *(Origen: `REF-06`, `QA-PER-04*`)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-REF-06-01` | El Orquestador crea, modifica o da de baja lógica una reserva con `lugar`, o archiva un viaje | Termina esa escritura | Publica un evento anonimizado, con identificador, tipo de evento, tipo de reserva, `lugar.destino`, fechas, `origen` y estado, en la quinta cola | `REF-06`, `ADR-IT5-001`, `ADR-IT4-009` | Test automático |
| `AC-REF-06-02` | Hay un evento nuevo en la quinta cola | El Proyector lo consume | Guarda el evento y actualiza los contadores de destino, tendencia y cancelación en la Base analítica | `REF-06`, `ADR-IT5-002` | Test automático |
| `AC-REF-06-03` | La Base analítica tiene un millón de eventos sembrados y el Proyector sigue consumiendo eventos | Se piden diez informes de tendencias, destinos y cancelaciones en forma concurrente | El Servicio lee solo la Base analítica y el tiempo promedio de generación del informe es menor a 10 segundos | `QA-PER-04*`, `ADR-IT5-002` | Prueba de carga |
| `AC-REF-06-04` | El equipo de datos pide el informe mientras hay cotizaciones en curso | El Servicio responde | La consulta no lee la Base de viajes ni ocupa un nodo del Orquestador | `QA-PER-02`, `QA-DIS-01`, `ADR-IT5-001` | Test automático |
| `AC-REF-06-05` | Una reserva pasa a baja lógica | El Orquestador publica el evento y el Proyector lo consume | El contador de cancelaciones de ese destino y día suma esa baja | `REF-06`, `ADR-IT4-008` | Test automático |
| `AC-REF-06-06` | El Proyector ya guardó un evento con cierto identificador | Llega de nuevo un evento con ese identificador | No se guarda ni se vuelve a sumar | `ADR-IT5-002`, `ADR-IT3-003` | Test automático |
| `AC-REF-06-07` | Un evento publicado por el Orquestador | Se inspeccionan todos sus campos | No contiene cuenta, correo, nombre, descripción libre, resumen de diálogo ni credenciales | `ADR-IT5-001` | Test automático |
| `AC-REF-06-08` | La quinta cola está llena | El Orquestador confirma una escritura de reserva | La respuesta al viajero no se demora, el Orquestador reintenta publicar el evento y, si agota los reintentos, el evento va a la cola de mensajes muertos con aviso a operaciones | `QA-PER-02`, `ADR-IT3-002`, `ADR-IT3-003` | Test automático |
| `AC-REF-06-09` | La Base analítica no está disponible | Un viajero crea, modifica o elimina una reserva | La operación se completa con normalidad | `QA-DIS-01`, `ADR-IT5-001` | Test automático |
| `AC-REF-06-10` | Una cuenta que no es del equipo de datos | Pide el informe | Acceso denegado y ningún dato del informe | `REF-06` | Test automático |
| `AC-REF-06-11` | La consulta supera la cota de 10 segundos | Vence la cota | Error de tiempo agotado y ningún informe parcial | `QA-PER-04*`, `ADR-IT5-002` | Test automático |
| `AC-REF-06-12` | No hay eventos en el rango pedido | El equipo de datos pide el informe | Las tres secciones llegan vacías, no es un error | `REF-06` | Test automático |
| `AC-REF-06-13` | Una reserva cambia de tipo de evento a lo largo de su vida (alta, modificación, baja) | El Proyector consume los tres eventos | Cada evento suma solo al contador de su tipo, sin recalcular el estado de la reserva | `ADR-IT5-002` | Test automático |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| Tamaño máximo de la cola de eventos analíticos | 1.000 eventos (5 en los tests), configurable | Tope de eventos retenidos en la quinta cola | `ADR-IT5-001`, que reutiliza la cota de `ADR-IT3-002` |
| Límite de reintentos y backoff | 3 reintentos con espera de 1 s, 2 s y 4 s | Reintento de la publicación del Orquestador y del consumo del Proyector | `ADR-IT5-001`, que reutiliza `ADR-IT3-003` |
| Cota del informe | 10 segundos | Tiempo máximo de procesamiento y generación del informe | `QA-PER-04*`, `ADR-IT5-002` |
| Cuentas autorizadas del equipo de datos | Lista en la configuración del Servicio de consultas | Quién puede pedir el informe | `REF-06` |
| Granularidad de las series | Día | Ventana temporal de los contadores y del informe | `ADR-IT5-002` |
| Máximo de destinos del ranking | 100 | Tamaño del ranking de destinos | `ADR-IT5-002` |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| Las cuentas del equipo de datos se listan en la configuración del Servicio de consultas. No hay un rol en el token ni un módulo de gestión de analistas | `REF-06` | El camino de lectura analítico, su aislamiento y su cota no cambian. El control de acceso real queda fuera de las decisiones de esta iteración. |
| La publicación del evento no es atómica con la escritura de la reserva: un corte entre ambas puede perder un evento | `ADR-IT5-001` | La consistencia del informe ya es eventual por diseño, y el ADR no exige entrega garantizada. Garantizarla pediría un registro de salida en la Base de viajes, que ningún ADR decide. |
| El Servicio de consultas y el Proyector se prueban en el mismo proceso que el Orquestador, cada uno con su propia conexión a la Base analítica | `ADR-IT5-001` | Lo que importa es la frontera: no importan al Orquestador ni la persistencia de viajes, y un test de arquitectura lo hace cumplir |
| La Base analítica es una instancia de PostgreSQL propia, sin las demás réplicas de las bases de viajes | `QA-DIS-01` | El aislamiento físico se conserva; la réplica de la Base analítica no la pide ningún ADR |
| El volumen de la prueba de carga se siembra directamente en la Base analítica, sin pasar por el Orquestador | `QA-PER-04*` | La cota mide la generación del informe sobre preagregados. Cómo llegaron los eventos no cambia esa lectura. |

## Fuera de Alcance

* La operación de gestión manual que produce la baja lógica y el `lugar`: [SPEC-REF-04](SPEC-REF-04.md). Esta spec consume ese dato.
* El archivado de viajes que produce uno de los eventos: [SPEC-REF-01](SPEC-REF-01.md).
* Cotización, caché y el failover de la Base de viajes, salvo la restricción de no leerla desde el camino analítico.
* La instantaneidad del último dato. La consistencia del informe es eventual.
* Entrega garantizada del evento ante un corte entre la escritura y la publicación. Si resultara inaceptable, se reabre con un registro de salida en la Base de viajes.
* Dimensiones nuevas del informe que no estén preagregadas: se recalculan a partir de los eventos históricos.
* Informe parcial o degradado al vencer la cota.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-22 | Versión inicial (`borrador`) | Creación a partir de `REF-06` y de los ADR aceptados que la iteración le asocia |
| 2026-11-23 | Decisiones de revisión y paso a `aprobada` (`OK SPEC`) | Evento por archivado y campos completos del evento; anonimización explícita; publicación asíncrona con Retry sin entrega garantizada; informe único con filtros, por día; contadores por tipo de evento; cota con error de tiempo agotado; cuentas autorizadas por configuración; prueba de carga con un millón de eventos; criterios de aceptación nuevos |
| 2026-11-23 | Decisiones de implementación fijadas (`PLAN-REF-06`) | El día es el del evento en UTC; el archivado emite un evento por viaje sin destino ni tipo; la prueba de carga corre en la suite completa; campos cerrados del evento sin identificadores de reserva, viaje ni cuenta; qué operaciones publican; forma del informe; cota doble; códigos de respuesta |
