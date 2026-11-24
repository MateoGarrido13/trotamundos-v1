# SPEC-COMP-07. Novedades de Booking

* **Estado:** aprobada
* **Fecha:** 2026-11-23
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `QA-PER-01`, `QA-INT-01`, `CON-02` |
| **ADRs** | `ADR-IT3-001`, `ADR-IT3-002`, `ADR-IT3-003`, `ADR-IT3-004`, `ADR-IT3-009`, `ADR-IT3-010`, `ADR-004`, `ADR-007` |
| **Elemento del paso 5** | Adaptador de anuncios (Booking), cola de novedades, Servicio de ingesta: [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md) |
| **Incremento (Slice)** | Slice 3 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

A las 8 am los proveedores cargan sus viajes nuevos. El usuario los ve en la sección «Novedades» con un retraso promedio de **5 minutos como máximo** desde que el listener detecta la actualización (`QA-PER-01`). El aviso de Booking llega por push a un listener propio, se traduce al modelo interno y se deja en la cola de novedades con un identificador único; el Servicio de ingesta lo entrega al Orquestador.

## Drivers que guían el cómo

* **`QA-PER-01`:** la medida corre desde que el listener detecta la actualización hasta que la app la refleja: 5 minutos como máximo, en promedio. *(Origen: LISTADO_DRIVERS_RONDA_1)*

## Conceptos de diseño aceptados

* **Novedades por aviso (push) a un listener** (`ADR-IT3-009`): el Adaptador de anuncios es el listener: traduce el aviso al modelo interno y lo deja en la cola de novedades con el identificador único que él asigna. Como contrapartida, no puede reencolar un aviso consumido: con la cola llena responde a Booking una indisponibilidad y delega en él la reentrega. El endpoint del listener es una segunda entrada pública que **no pasa por el API Gateway**: se autentica el origen del aviso y se limita su tasa.
* **Intermediario asíncrono con colas acotadas y Retry con identificador** (`ADR-IT3-001`, `ADR-IT3-002`, `ADR-IT3-003`).
* **Nodos propios para la ingesta y los adaptadores de entrada** (`ADR-IT3-010`), con límite de tasa de entrega de la ingesta al Orquestador.
* **`IProveedor`** (`ADR-IT3-004`) y **Ping/Echo** (`ADR-004`) contra Booking; **ACL** (`ADR-007`).

## Relaciones Permitidas

* **Recibe llamadas de:** Booking, por HTTPS, al listener. El Servicio de ingesta consume la cola de novedades.
* **Invoca / publica hacia:** el Broker (cola de novedades). La ingesta entrega al Orquestador de viajes, que guarda la novedad y la muestra en «Novedades».
* **Restricciones de frontera:** el listener solo habla con el Broker; no escribe la Base de viajes ni llama al Orquestador. La ingesta no escribe la base: entrega al Orquestador. El aviso no pasa por el Gateway.

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `POST /proveedores/booking/avisos` | Booking hacia el listener | Aviso de actualización y clave compartida en `X-Clave-Proveedor` | 202 si quedó en la cola | Clave inválida: 401 sin publicar. Tasa excedida: 429. Cola llena: 503, Booking reentrega. Aviso mal formado: 422 | `ADR-IT3-009` |
| `IProveedor.ping()` | Adaptador hacia Booking | — | Eco | Sin eco: se informa a operaciones | `ADR-004` |
| `IProveedor.traducir(aviso)` | Interno | Aviso de Booking | Novedad del modelo interno | Aviso que no se puede traducir: 422 | `ADR-007` |
| Mensaje de novedad | Listener hacia el Broker | Novedad con identificador único | En la cola de novedades | Cola llena: 503 al origen | `ADR-IT3-002` |
| `GET /novedades/anuncios` | Cliente hacia el Orquestador | Identidad | Anuncios recientes, ordenados por fecha de recepción | Sin anuncios: lista vacía | `QA-PER-01` |

## Reglas de Comportamiento

1. **Identificador único:** lo asigna el listener a partir de la identidad del aviso de Booking; un aviso repetido se descarta en la ingesta. *(Origen: `ADR-IT3-003`)*
2. **Autenticar el origen:** un aviso sin la clave compartida válida se rechaza antes de tocar el Broker. *(Origen: `ADR-IT3-009`)*
3. **Tasa:** el listener limita pedidos por origen; lo excedido recibe 429. La ingesta limita la entrega al Orquestador para que el pico de las 8 am no consuma los nodos de cotización. *(Origen: `ADR-IT3-009`, `ADR-IT3-010`)*
4. **Cola llena:** 503 a Booking y aviso a operaciones; la reentrega es de Booking. *(Origen: `ADR-IT3-002`, `ADR-IT3-009`)*
5. **Retry y mensajes muertos:** la ingesta reintenta con espera creciente (1, 2 y 4 s) y, al agotar, el mensaje va a muertos con aviso a operaciones. *(Origen: `ADR-IT3-003`)*
6. **Visible en «Novedades»:** el anuncio aparece en el cliente en el siguiente refresco de la sección. *(Origen: `QA-PER-01`)*
7. **Separación de tipos de novedad:** los anuncios de Booking no modifican reservas; los cambios de una reserva existente siguen su camino de [SPEC-REF-04](SPEC-REF-04.md). *(Origen: `REF-04`)*
8. **Booking simulado:** el mock de Booking permite inyectar demora, caída y ráfagas. *(Origen: PLAN_MAESTRO §1.3)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-COMP-07-01` | Un aviso válido de Booking | Llega al listener | 202 y el mensaje queda en la cola de novedades con su identificador | `ADR-IT3-009` | Test automático |
| `AC-COMP-07-02` | Un aviso con clave inválida | Llega | 401 y no se publica nada | `ADR-IT3-009` | Test automático |
| `AC-COMP-07-03` | Cola de novedades llena | Llega un aviso | 503 y aviso a operaciones | `ADR-IT3-002` | Test automático |
| `AC-COMP-07-04` | El mismo aviso dos veces | Llegan | Se muestra una sola vez | `ADR-IT3-003` | Test automático |
| `AC-COMP-07-05` | Un aviso | Pasa el listener, la cola y la ingesta | El anuncio está en «Novedades» y el tiempo medio desde que el listener lo detecta es menor que 5 minutos | `QA-PER-01` | Test automático con medición |
| `AC-COMP-07-06` | Ráfaga de avisos a las 8 am | Se envían | La ingesta entrega al Orquestador sin superar su límite de tasa | `ADR-IT3-010` | Test automático |
| `AC-COMP-07-07` | La ráfaga | Corre mientras se piden cotizaciones | La cotización no se degrada | `ADR-IT3-010` | Prueba de carga |
| `AC-COMP-07-08` | Booking sin eco al ping | Corre el ping | Se informa a operaciones | `ADR-004` | Test automático |
| `AC-COMP-07-09` | El listener | Se revisan sus dependencias | Solo importa el Broker, no la persistencia ni el Orquestador | `ADR-IT3-010` | Test de arquitectura |
| `AC-COMP-07-10` | Un aviso que no se puede traducir | Llega | 422 y no entra a la cola | `ADR-007` | Test automático |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| `tasa_avisos_por_origen` | 50 por segundo | Límite del listener | `ADR-IT3-009` |
| `limite_entrega_ingesta` | el de `REF-03` | Límite de entrega al Orquestador | `ADR-IT3-010` |
| `retencion_anuncios_dias` | 30 | Cuánto se muestran | — (valor de prototipo) |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| Booking simulado | `CON-02` | El contrato del aviso es el que fija el adaptador; cambiar al real es cambiar ese módulo |
| Los 8 am se simulan con una ráfaga | `QA-PER-01` | Se verifica el desacople y la cola, no el reloj |

## Fuera de Alcance

* Notificar al usuario por canal ([SPEC-COMP-08](SPEC-COMP-08.md)).
* Reservar un viaje anunciado.

## Decisiones tomadas

1. **Qué es un aviso:** un **anuncio de viaje nuevo** (título, destino, fechas y proveedor) que ven todos los viajeros en «Novedades». No modifica reservas. Se guarda en una tabla propia `anuncio` del Orquestador y `GET /novedades/anuncios` los lista.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-23 | Versión inicial (`borrador`) | Pedido del usuario; Slice 3 sin spec |
| 2026-11-23 | Paso a `aprobada` (`OK SPEC`) | Aprobación del usuario tras resolver las decisiones de revisión |
| 2026-11-23 | Decisión: el aviso de Booking es un anuncio de viaje nuevo, visible a todos | Respuesta del usuario |
