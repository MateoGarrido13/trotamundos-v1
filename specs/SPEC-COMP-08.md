# SPEC-COMP-08. Notificaciones por canales (`ICanal`)

* **Estado:** aprobada
* **Fecha:** 2026-11-23
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `QA-INT-02`, `QA-SEG-01`, `CON-02` |
| **ADRs** | `ADR-IT3-001`, `ADR-IT3-002`, `ADR-IT3-003`, `ADR-IT3-004`, `ADR-IT4-006` |
| **Elemento del paso 5** | `ICanal`, Servicio de notificaciones, Adaptador de Instagram: [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md) |
| **Incremento (Slice)** | Slice 3 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

El Orquestador de viajes deja pedidos de envío (propuestas e itinerarios a clientes, correo de recuperación, aviso al titular) en la cola de notificaciones. El Servicio de notificaciones los consume y los entrega por el canal pedido, a través de `ICanal`. Sumar Instagram es agregar un adaptador, sin modificar Email ni WhatsApp ni a quien publica (`QA-INT-02`). Hoy la cola existe pero no tiene consumidor.

## Drivers que guían el cómo

* **`QA-INT-02`:** integrar Instagram requiere menos de 1 semana, impacta en un único componente nuevo (0 modificaciones en consumidores existentes) y los canales previos no degradan su latencia (0 %). El envío es asíncrono y no bloquea el hilo principal. *(Origen: LISTADO_DRIVERS_RONDA_1)*

## Conceptos de diseño aceptados

* **Intermediario asíncrono con colas separadas** (`ADR-IT3-001`): la cola de notificaciones desacopla al Orquestador de los canales.
* **Colas acotadas** (`ADR-IT3-002`): el Orquestador reintenta el pedido de envío cuando la cola está llena, avisa a operaciones y el que agota sus reintentos termina en mensajes muertos.
* **Retry con identificador único** (`ADR-IT3-003`): un reintento no duplica el envío.
* **Interfaces comunes `IProveedor` e `ICanal`** (`ADR-IT3-004`): `ICanal.enviar(destinatario, propuesta)`. Los canales de Email y WhatsApp ya existen; Instagram es el único componente nuevo.
* **Recuperación con aviso al titular por la cola de notificaciones** (`ADR-IT4-006`): el correo de recuperación y el aviso de actividad sospechosa usan este mismo camino y el canal Email.

## Relaciones Permitidas

* **Recibe llamadas / mensajes de:** el Orquestador de viajes y el módulo de registro y autenticación, que publican en la cola de notificaciones.
* **Invoca:** las implementaciones de `ICanal`, en memoria y de forma síncrona; cada una llama a la API de su canal por HTTPS/REST.
* **Restricciones de frontera:** el publicador no conoce los canales. Los canales no leen ni escriben la Base de viajes. Agregar un canal no modifica a quien publica ni a otro canal.

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Pedido de envío | Publicador hacia la cola de notificaciones | Identificador único, canal, destinatario, propuesta (asunto y cuerpo) | Mensaje en cola | Cola llena: el publicador reintenta con 1, 2 y 4 s | `ADR-IT3-002` |
| `ICanal.enviar(destinatario, propuesta)` | Servicio de notificaciones hacia el canal | Destinatario y propuesta | Envío confirmado | Falla del canal: el Broker reintenta con el mismo identificador | `ADR-IT3-004` |
| Canales | Email, WhatsApp, Instagram (adaptadores) | — | — | Canal no registrado: el mensaje va a muertos con aviso | `ADR-IT3-004` |

## Reglas de Comportamiento

1. **Consumo continuo:** el Servicio de notificaciones tiene su consumidor en el ciclo de vida de la app. *(Origen: [SPEC-COMP-01](SPEC-COMP-01.md))*
2. **Un canal por pedido:** el pedido nombra el canal y el servicio lo busca en su registro. *(Origen: `ADR-IT3-004`)*
3. **Sin duplicar:** un envío que ya salió con ese identificador no se repite. *(Origen: `ADR-IT3-003`)*
4. **Reintento y muertos:** 3 reintentos con 1, 2 y 4 s; al agotarlos el mensaje va a mensajes muertos con aviso a operaciones. *(Origen: `ADR-IT3-003`)*
5. **Canal nuevo:** se agrega registrando un adaptador de `ICanal`; ningún otro módulo cambia. *(Origen: `QA-INT-02`)*
6. **Aislamiento de latencia:** un canal lento no atrasa a los demás ni al publicador. *(Origen: `QA-INT-02`)*
7. **Canales simulados:** Email, WhatsApp e Instagram son mocks que admiten demora y caída inyectadas. *(Origen: PLAN_MAESTRO §1.3)*
8. **Contenido:** el servicio entrega el contenido tal como lo recibe; no arma textos de negocio. *(Origen: `ADR-IT3-004`)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-COMP-08-01` | Un pedido por Email en la cola | Corre el consumidor | `ICanal.enviar` de Email se invoca una vez | `ADR-IT3-004` | Test automático |
| `AC-COMP-08-02` | Los canales Email y WhatsApp | Se agrega Instagram | Solo hay un archivo nuevo y ningún otro cambia | `QA-INT-02` | Test de arquitectura |
| `AC-COMP-08-03` | Un pedido por Instagram | Corre el consumidor | Se entrega por Instagram sin tocar Email ni WhatsApp | `QA-INT-02` | Test automático |
| `AC-COMP-08-04` | Instagram caído | Llegan pedidos de Instagram y de Email | Los de Email salen sin demora adicional y los de Instagram se reintentan | `QA-INT-02` | Test automático con caída inyectada |
| `AC-COMP-08-05` | Instagram agotó los reintentos | Termina | El mensaje está en mensajes muertos y se avisó a operaciones | `ADR-IT3-003` | Test automático |
| `AC-COMP-08-06` | El mismo pedido entregado dos veces por el Broker | Corre el consumidor | Se envía una sola vez | `ADR-IT3-003` | Test automático |
| `AC-COMP-08-07` | La cola llena | El Orquestador publica | Reintenta con 1, 2 y 4 s y avisa a operaciones | `ADR-IT3-002` | Test automático |
| `AC-COMP-08-08` | Un pedido por un canal no registrado | Corre el consumidor | Va a mensajes muertos con aviso | `ADR-IT3-004` | Test automático |
| `AC-COMP-08-09` | El correo de recuperación de [SPEC-COMP-05](SPEC-COMP-05.md) | Se publica | Se envía por Email por este mismo camino | `ADR-IT4-006` | Test automático |
| `AC-COMP-08-10` | Un canal con demora de 2 s | Se envía a varios canales | La latencia de los otros canales no cambia | `QA-INT-02` | Test automático |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| `canales` | `email`, `whatsapp`, `instagram` | Canales registrados | `ADR-IT3-004` |
| `reintentos` | 3 con 1, 2, 4 s | Reintentos del Broker | `ADR-IT3-003` |
| `tamano_cola_notificaciones` | 100 | Cola acotada | `ADR-IT3-002` |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| Canales simulados | `CON-02` | El contrato `ICanal` es el mismo que el de un canal real |
| Un solo proceso | `ADR-IT3-001` | La cola y el consumidor siguen siendo componentes separados |

## Fuera de Alcance

* Qué propuestas o itinerarios se envían a leads, y cuándo (no hay un `REF` que lo pida).
* Credenciales y alta real de la API de Instagram.
* Preferencias de notificación del viajero.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-23 | Versión inicial (`borrador`) | Pedido del usuario; Slice 3 sin spec |
| 2026-11-23 | Paso a `aprobada` (`OK SPEC`) | Aprobación del usuario tras resolver las decisiones de revisión |
