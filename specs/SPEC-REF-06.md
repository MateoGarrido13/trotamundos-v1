# SPEC-REF-06. Analítica de datos

* **Estado:** borrador
* **Fecha:** 2026-11-22
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `REF-06`, `QA-PER-04*`, `QA-PER-02`, `QA-DIS-01` |
| **ADRs** | `ADR-IT5-001`, `ADR-IT5-002`, `ADR-IT4-008`, `ADR-IT4-009` |
| **Elemento del paso 5** | [RONDA_1/ITERACION_5.md](../RONDA_1/ITERACION_5.md) cola de eventos analíticos, Proyector analítico, Base analítica, Servicio de consultas analíticas |
| **Incremento (Slice)** | Slice 5 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

Trotamundos recopilará datos analíticos de los viajes (tendencias, destinos, cancelaciones) para su monetización por parte del equipo de datos, implicando la ejecución de consultas analíticas pesadas.

El Orquestador emite un evento anonimizado en cada alta, modificación o baja lógica de `Reserva`. El Servicio de consultas analíticas responde el informe desde la Base analítica.

## Drivers que guían el cómo

* **`QA-PER-04*`:** es la contraparte de `REF-06`. El equipo de datos consulta tendencias, destinos y cancelaciones con el panel en operación (2 millones de usuarios activos por semana, 15 millones de cuentas, y un pico de domingo a lunes, de jueves a viernes o de una disrupción de viajes). El informe, en promedio, se procesa y se genera antes de los 10 segundos. *(Origen: [RONDA_1/ITERACION_5.md](../RONDA_1/ITERACION_5.md))*
* **`QA-PER-02`:** la consulta analítica no compite con la cotización ni usa los nodos del Orquestador. Durante el pico, el Orquestador solo encola un evento liviano. *(Origen: [RONDA_1/ITERACION_5.md](../RONDA_1/ITERACION_5.md), sección B.1; [ADR-IT5-001](../RONDA_1/ADRs/ITERACION_5/ADR-IT5-001.md))*
* **`QA-DIS-01`:** el camino analítico no lee la Base de viajes, ni la primaria ni la pasiva. La caída o la saturación de la Base analítica no afecta las operaciones de los viajeros. *(Origen: [ADR-IT5-001](../RONDA_1/ADRs/ITERACION_5/ADR-IT5-001.md))*

## Conceptos de diseño aceptados

* **Quinta cola, Proyector en nodos propios y Base analítica separada** (`ADR-IT5-001`): el Orquestador publica eventos anonimizados en la quinta cola del Broker. El Proyector analítico los consume en nodos propios, descarta duplicados por identificador de evento y escribe en una Base analítica distinta de la Base de viajes y de las Bases de cuentas. El Servicio de consultas analíticas lee solo esa base. La Base analítica no almacena correos ni credenciales.
* **Preagregación incremental y cota de 10 segundos** (`ADR-IT5-002`): el Proyector actualiza contadores y series por destino y fecha al ingresar cada evento. La consulta del equipo de datos lee esas tablas preagregadas. El Servicio abre una cota de 10 segundos.
* **Baja lógica** (`ADR-IT4-008`): la baja lógica de una reserva conserva la cancelación que el informe analítico necesita. El evento de esa baja entra al camino analítico.
* **`lugar`** (`ADR-IT4-009`): el destino del informe sale de `Reserva.lugar`. El evento lleva `lugar.destino`.

## Relaciones Permitidas

* **Recibe llamadas / mensajes de:** el equipo de datos, por el API Gateway, pide el informe al Servicio de consultas analíticas. El Proyector consume la cola de eventos analíticos.
* **Invoca / publica hacia:** el Orquestador publica en la quinta cola. El Proyector escribe la Base analítica. El Servicio lee la Base analítica.
* **Restricciones de frontera:** el Servicio de consultas analíticas no lee la Base de viajes ni llama a un nodo del Orquestador para armar el informe. El Orquestador no escribe la Base analítica. La cotización no publica ni espera este camino.

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen (ADR / Iteración) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Evento analítico | Asíncrono, cola del Broker | Alta, modificación o baja lógica de `Reserva`, anonimizada, con identificador de evento, `lugar.destino` y estado | Evento en la quinta cola | Tamaño de cola y reintentos: [sin especificar] | `ADR-IT5-001`, [RONDA_1/ITERACION_5.md](../RONDA_1/ITERACION_5.md) |
| Proyección | El Proyector consume la cola y escribe la Base analítica | Evento analítico | Contadores preagregados por destino, ventana temporal, tipo de reserva y estado o cancelación | Un identificador repetido no vuelve a sumar | `ADR-IT5-002` |
| Informe analítico | Síncrono, equipo de datos por el API Gateway | Consulta de tendencias, destinos y cancelaciones | Informe leído de las tablas preagregadas | Cota de 10 segundos | `ADR-IT5-002`, `QA-PER-04*` |

## Reglas de Comportamiento

1. **Emisión:** cada alta, modificación o baja lógica de `Reserva` en el Orquestador publica un evento anonimizado en la quinta cola. *(Origen: [RONDA_1/ITERACION_5.md](../RONDA_1/ITERACION_5.md), `ADR-IT5-001`)*
2. **Aislamiento:** el informe no toca la Base de viajes ni un nodo del Orquestador. *(Origen: `ADR-IT5-001`)*
3. **Preagregación:** el Proyector actualiza las series de forma idempotente con el identificador del evento. La consulta lee esas series, no el histórico reserva por reserva. *(Origen: `ADR-IT5-002`)*
4. **Cota:** el Servicio de consultas analíticas abre una cota de 10 segundos y devuelve el informe dentro de esa medida en promedio. *(Origen: `QA-PER-04*`, `ADR-IT5-002`)*
5. **Dimensiones:** el informe cubre tendencias, destinos (`lugar.destino`) y cancelaciones (baja lógica). *(Origen: `REF-06`, `ADR-IT4-008`, `ADR-IT4-009`)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-REF-06-01` | El Orquestador crea, modifica o da de baja lógica una reserva con `lugar` | Termina esa escritura | Publica un evento anonimizado, con identificador, `lugar.destino` y estado, en la quinta cola. El evento no lleva correo ni credenciales | `REF-06`, `ADR-IT5-001`, `ADR-IT4-009` | Test automático |
| `AC-REF-06-02` | Hay un evento nuevo en la quinta cola | El Proyector lo consume | Actualiza los agregados de destino, tendencia y cancelación en la Base analítica, y un segundo consumo del mismo identificador no los vuelve a sumar | `REF-06`, `ADR-IT5-002` | Test automático |
| `AC-REF-06-03` | La Base analítica tiene agregados y el panel está en operación, incluido un pico | El equipo de datos pide tendencias, destinos y cancelaciones | El Servicio lee solo la Base analítica y el informe se genera, en promedio, antes de los 10 segundos | `QA-PER-04*`, `ADR-IT5-002` | Test automático |
| `AC-REF-06-04` | El equipo de datos pide el informe mientras hay cotizaciones en curso | El Servicio responde | La consulta no lee la Base de viajes ni ocupa un nodo del Orquestador | `QA-PER-02`, `QA-DIS-01`, `ADR-IT5-001` | Test automático |
| `AC-REF-06-05` | Una reserva pasa a baja lógica | El Orquestador publica el evento | El agregado de cancelaciones puede contar esa baja | `REF-06`, `ADR-IT4-008` | Test automático |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| Tamaño máximo de la cola de eventos analíticos | [sin especificar] | Tope de eventos retenidos en la quinta cola | `ADR-IT5-001`, que reutiliza la cota de `ADR-IT3-002` |
| Límite de reintentos y backoff del Proyector | [sin especificar] | Reintento idempotente del consumo de la quinta cola | `ADR-IT5-001`, que reutiliza `ADR-IT3-003` |
| Cota del informe | 10 segundos | Tiempo máximo promedio de procesamiento y generación del informe | `QA-PER-04*`, `ADR-IT5-002` |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| Ninguna adicional | `ADR-IT5-001` | La quinta cola, el Proyector en nodos propios y la Base analítica separada se conservan. El informe no se lee de la Base de viajes. |

## Fuera de Alcance

* La operación de gestión manual que produce la baja lógica y el `lugar`: [SPEC-REF-04](SPEC-REF-04.md). Esta spec consume ese dato.
* Cotización, caché y el failover de la Base de viajes, salvo la restricción de no leerla desde el camino analítico.
* La instantaneidad del último dato. La consistencia del informe es eventual.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-22 | Versión inicial (`borrador`) | Creación a partir de `REF-06` y de los ADR aceptados que la iteración le asocia |
