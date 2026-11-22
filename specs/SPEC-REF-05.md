# SPEC-REF-05. Resolución de problemas

* **Estado:** borrador
* **Fecha:** 2026-11-22
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `REF-05`, `CON-02` |
| **ADRs** | `ADR-IT4-010` |
| **Elemento del paso 5** | [RONDA_1/ITERACION_4.md](../RONDA_1/ITERACION_4.md) `IAgencia`, Adaptador de agencia, cola de casos de ayuda |
| **Incremento (Slice)** | Slice 5 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

El sistema debe integrarse con la agencia de viajes preferida del usuario para facilitar una rápida resolución de problemas.

El Orquestador guarda el caso y publica el pedido en la cola de casos de ayuda. El Adaptador de agencia, detrás de `IAgencia`, lo entrega a la API de la agencia. [SPEC-REF-07](SPEC-REF-07.md) usa este mismo camino cuando delega un caso complejo. No forma parte de esta spec la clasificación de ese caso.

## Drivers que guían el cómo

* **`CON-02`:** la agencia se integra por API. `IAgencia` extiende `IProveedor` con `abrirCaso(caso)` y `consultarCaso(idCaso)`. Una agencia nueva es un adaptador más, sin tocar al Orquestador. *(Origen: [RONDA_1/ITERACION_4.md](../RONDA_1/ITERACION_4.md); [ADR-IT4-010](../RONDA_1/ADRs/ITERACION_4/ADR-IT4-010.md))*

## Conceptos de diseño aceptados

* **Adaptador de agencia detrás de `IAgencia`, con pedidos asíncronos por el Broker** (`ADR-IT4-010`): la capa anti-corrupción aísla el contrato de cada agencia. El Orquestador guarda el caso y la agencia preferida del viajero y publica el pedido en la cola de casos de ayuda. El adaptador, en nodos propios junto a la ingesta, lo entrega con Retry e identificador único. Las novedades del caso entran por la cola de novedades y la ingesta. La cola queda acotada, con la misma regla de tamaño máximo y de Retry que las colas ya decididas. El viajero ve el caso «en trámite». Si se agotan los reintentos, el caso queda «sin entregar», visible en «Novedades», con opción de reintentar.

## Relaciones Permitidas

* **Recibe llamadas / mensajes de:** el viajero, por el gateway y el balanceador, reporta un problema sobre una reserva. El Adaptador consume la cola de casos de ayuda.
* **Invoca / publica hacia:** la cola de casos de ayuda; la API de la agencia mediante `abrirCaso(caso)` y `consultarCaso(idCaso)`; la cola de novedades, cuando la agencia informa un cambio.
* **Restricciones de frontera:** el viajero no llama a la API de la agencia. El Adaptador no escribe la Base de viajes: las novedades vuelven por la ingesta y el Orquestador. `ICanal` no transporta el ciclo de vida del caso. El pedido no es una llamada síncrona que deje al viajero esperando a la agencia.

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen (ADR / Iteración) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Reportar problema | Síncrono hasta el Orquestador; el resto es asíncrono por cola | Reserva afectada y descripción del problema, con la agencia preferida del viajero | Caso «en trámite» | El viajero no recibe confirmación inmediata de la agencia | `ADR-IT4-010` |
| `abrirCaso(caso)` | El Adaptador llama a la API de la agencia, con Retry e identificador único | Caso publicado en la cola de casos de ayuda | Pedido entregado, o reintento | Al agotar reintentos, estado «sin entregar» | `ADR-IT4-010` |
| `consultarCaso(idCaso)` | El Adaptador llama a la API de la agencia | Identificador del caso | Estado que informe la agencia | Cómo la agencia informa el cambio: [sin especificar] | `ADR-IT4-010` |

## Reglas de Comportamiento

1. **Desacople:** el Orquestador persiste el caso, lo publica en la cola de casos de ayuda y muestra «en trámite» sin esperar a la agencia. *(Origen: `ADR-IT4-010`)*
2. **Entrega:** el Adaptador consume la cola y llama a `abrirCaso(caso)` con Retry y un identificador único. Un reintento no duplica el pedido. *(Origen: `ADR-IT4-010`)*
3. **Vuelta:** un cambio que informa la agencia entra por la cola de novedades y la ingesta, y el Orquestador lo refleja en «Novedades». *(Origen: [RONDA_1/ITERACION_4.md](../RONDA_1/ITERACION_4.md))*
4. **Reintentos agotados:** el caso queda «sin entregar», visible en «Novedades», con opción de reintentar. *(Origen: `ADR-IT4-010`)*
5. **Consentimiento:** la reserva afectada y la descripción del problema viajan a un tercero. Hace falta el consentimiento del viajero al elegir su agencia. *(Origen: `ADR-IT4-010`)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-REF-05-01` | El viajero tiene una agencia preferida y una reserva | Reporta un problema sobre esa reserva | El Orquestador guarda el caso, lo publica en la cola de casos de ayuda y le muestra «en trámite» | `REF-05`, `ADR-IT4-010` | Test automático |
| `AC-REF-05-02` | Hay un caso en la cola de casos de ayuda | El Adaptador de agencia lo consume | Llama a `abrirCaso(caso)` contra la API de la agencia | `REF-05`, `CON-02`, `ADR-IT4-010` | Test automático |
| `AC-REF-05-03` | La entrega a la agencia falla y se reintenta con el mismo identificador | El Adaptador reintenta | No se abre un segundo caso por ese mismo pedido | `ADR-IT4-010` | Test automático |
| `AC-REF-05-04` | Se agotan los reintentos de entrega | El Adaptador deja de reintentar | El caso queda «sin entregar» y visible en «Novedades», con opción de reintentar | `ADR-IT4-010` | Test automático |
| `AC-REF-05-05` | La agencia informa un cambio del caso | Esa novedad entra por la cola de novedades | El Servicio de ingesta se la entrega al Orquestador y el viajero la ve en «Novedades» | `REF-05`, `ADR-IT4-010` | Test automático |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| Tamaño máximo de la cola de casos de ayuda | [sin especificar] | Tope de pedidos retenidos en esa cola | `ADR-IT4-010`, que aplica la cota de `ADR-IT3-002` |
| Límite de reintentos y backoff de la entrega a la agencia | [sin especificar] | Cuántas veces y con qué espera se reintenta `abrirCaso` | `ADR-IT4-010`, que aplica `ADR-IT3-003` |
| Modo en que la agencia informa un cambio | [sin especificar] | Si la agencia avisa a un listener o si el adaptador consulta | `ADR-IT4-010` |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| La API de la agencia se simula con un mock local al que se le puede inyectar demora o caída | `CON-02` | `IAgencia`, el Adaptador y la cola se conservan. Lo permite [POLITICAS_SPECS_Y_PLANES.md](../POLITICAS_SPECS_Y_PLANES.md) §4.6. |

## Fuera de Alcance

* Clasificación de primer nivel y casos complejos del asistente: [SPEC-REF-07](SPEC-REF-07.md).
* El texto de las novedades de Booking y el resto de la ingesta que no sea la vuelta de un caso de agencia.
* El canal `ICanal` como transporte del caso.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-22 | Versión inicial (`borrador`) | Creación a partir de `REF-05` y de `ADR-IT4-010` |
