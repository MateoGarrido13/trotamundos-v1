# SPEC-REF-03. Filtros y whitelists

* **Estado:** aprobada
* **Fecha:** 2026-11-23
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `REF-03`, `QA-SEG-03*` |
| **ADRs** | `ADR-IT3-008`, `ADR-IT3-003`, `ADR-IT3-010` |
| **Elemento del paso 5** | [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md) Filtro de remitentes, whitelist, Mensajes en revisión y Servicio de ingesta |
| **Incremento (Slice)** | Slice 3 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

Debe permitir filtrar y crear listas de remitentes seguros (whitelists) para ciertos correos electrónicos de viaje.

El Filtro de remitentes está entre el Parseo aislado de [SPEC-REF-02](SPEC-REF-02.md) y la ingesta. La whitelist y los mensajes en revisión los guarda el Orquestador de viajes.

Esta spec también fija el contrato del Servicio de ingesta del lado del correo, porque es el destino del filtro y quien cierra la idempotencia que empieza en [SPEC-REF-02](SPEC-REF-02.md). Con eso, esta spec verifica de punta a punta que la reserva llega al itinerario.

## Drivers que guían el cómo

* **`QA-SEG-03*`:** la medida del 100 % queda condicional. Se cumple para los titulares autorizados cuyos remitentes son seguros o fueron aprobados. Una reserva que espera aprobación no está en el itinerario hasta que el titular actúa. Lo que se descarta es solo el contenido que no pasa la validación del parseo. Esta spec verifica la medida de punta a punta. *(Origen: [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md), párrafo de tensión de `QA-SEG-03*` con la whitelist; [ADR-IT3-008](../RONDA_1/ADRs/ITERACION_3/ADR-IT3-008.md))*

## Conceptos de diseño aceptados

* **Whitelist con Mensajes en revisión** (`ADR-IT3-008`): el Filtro de remitentes ubica la whitelist y los mensajes en revisión entre el Parseo aislado y la ingesta. Un remitente desconocido no se descarta: queda en Mensajes en revisión hasta que el titular lo aprueba. Al aprobarlo, el remitente entra a la whitelist y la reserva sigue hacia la ingesta. Lo que se descarta es solo el contenido que no pasa la validación del parseo.
* **Retry con identificador único** (`ADR-IT3-003`): el Servicio de ingesta descarta los duplicados por identificador único y reintenta si falla la entrega. Debe conservar los identificadores ya procesados.
* **Nodos propios y límite de tasa** (`ADR-IT3-010`): el Servicio de ingesta corre en los nodos de entrada, separado de los nodos del Orquestador, y entrega al Orquestador con un límite de tasa para que el pico no consuma los nodos que atienden la cotización.

## Relaciones Permitidas

* **Recibe llamadas / mensajes de:** el Parseo aislado, con la reserva normalizada y su identificador ([SPEC-REF-02](SPEC-REF-02.md)). El titular, por el API Gateway y el balanceador, consulta Mensajes en revisión, aprueba o quita un remitente y descarta un mensaje. El Filtro de remitentes entrega a la ingesta las reservas de remitentes seguros o aprobados.
* **Invoca / publica hacia:** el Orquestador de viajes, que guarda la whitelist y los mensajes en revisión. La ingesta, cuando el remitente es seguro o acaba de ser aprobado, recibe la reserva normalizada y la entrega al Orquestador.
* **Restricciones de frontera:** el filtro no descarta una reserva válida de un remitente desconocido. No reemplaza al Parseo aislado: no valida el contenido del mensaje. No escribe la reserva en la Base de viajes por su cuenta; la entrega a la ingesta, y el Orquestador es el dueño de lo que se guarda. La ingesta nunca escribe en la base: entrega al Orquestador.

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen (ADR / Iteración) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Filtrar remitente | Interna, después del Parseo aislado | Reserva normalizada, remitente e identificador | Hacia la ingesta si el remitente está en la whitelist del titular. Si no, a Mensajes en revisión | Un identificador que ya está en revisión se ignora, sin crear otra entrada. Con el tope de revisión alcanzado, el mensaje no se retiene y no se pierde: sigue en el buzón y vuelve en un sondeo posterior mientras esté en la ventana. Si el Orquestador no responde, aplica el reintento y la cola de mensajes muertos de [SPEC-REF-02](SPEC-REF-02.md) | `ADR-IT3-008`, `ADR-IT3-003` |
| Consultar Mensajes en revisión | Síncrono, cliente por el API Gateway hacia el Orquestador | Titular | Mensajes pendientes con remitente y resumen de la reserva | Sin mensajes: lista vacía, no error | `ADR-IT3-008` |
| Aprobar remitente | Síncrono, cliente por el API Gateway hacia el Orquestador | Titular y remitente, ya sea el de un mensaje en revisión o uno nuevo | El remitente entra a la whitelist y todos los mensajes pendientes de ese remitente siguen hacia la ingesta | Remitente ya aprobado: no cambia nada y no es error | [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md), `ADR-IT3-008` |
| Descartar mensaje en revisión | Síncrono, cliente por el API Gateway hacia el Orquestador | Titular e identificador del mensaje | El mensaje sale de pendientes y queda registrado como descartado, con su identificador, hasta cumplir la retención | Mensaje inexistente, ya resuelto o de otro titular: rechazo sin efecto | `ADR-IT3-008` |
| Quitar remitente de la whitelist | Síncrono, cliente por el API Gateway hacia el Orquestador | Titular y remitente | El remitente sale de la whitelist. Sus mensajes siguientes van a revisión. Las reservas ya incorporadas permanecen | Remitente que no está en la whitelist: no cambia nada y no es error | `REF-03` |
| Entregar reserva a la ingesta | Asíncrono, desde el Filtro de remitentes. La ingesta entrega al Orquestador con límite de tasa | Reserva normalizada e identificador | La reserva llega al Orquestador una sola vez, y el Orquestador la guarda | Identificador ya procesado: se descarta. Entrega fallida: Retry. Reintentos agotados: cola de mensajes muertos, con aviso a operaciones | `ADR-IT3-003`, `ADR-IT3-010` |

## Reglas de Comportamiento

1. **Remitente seguro:** si el remitente está en la whitelist del titular, la reserva pasa a la ingesta. *(Origen: [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md))*
2. **Remitente desconocido:** la reserva queda en Mensajes en revisión. No se descarta y no entra al itinerario hasta la aprobación. *(Origen: `ADR-IT3-008`)*
3. **Aprobación:** el titular aprueba al remitente, el remitente entra a la whitelist y las reservas retenidas de ese remitente siguen hacia la ingesta. La aprobación vale para los mensajes siguientes de ese remitente. Se puede aprobar desde un mensaje en revisión o dando de alta el remitente directamente. *(Origen: `ADR-IT3-008`, `REF-03`)*
4. **Descarte:** el titular puede descartar un mensaje en revisión sin bloquear al remitente. Como el correo sigue en el buzón mientras esté en la ventana de sondeo, el mensaje descartado queda registrado con su identificador y no reaparece en revisión. *(Origen: `ADR-IT3-008`)*
5. **Baja de la whitelist:** quitar un remitente solo cambia el destino de sus mensajes siguientes. No elimina reservas ya incorporadas. *(Origen: `REF-03`)*
6. **Idempotencia del filtro:** el Filtro de remitentes trata el identificador como clave. Como [SPEC-REF-02](SPEC-REF-02.md) relee una ventana de sondeo en cada sondeo, el mismo mensaje llega varias veces, y no puede quedar repetido en revisión. *(Origen: `ADR-IT3-003`, `ADR-IT3-008`)*
7. **Retención y tope:** un mensaje en revisión, pendiente o descartado, se conserva hasta cumplir la retención, que nunca es menor que la ventana de sondeo. Cada titular tiene un tope de mensajes pendientes. *(Origen: `ADR-IT3-008`)*
8. **Ingesta idempotente:** la ingesta descarta una reserva cuyo identificador ya procesó y entrega cada reserva al Orquestador una sola vez, sin superar el límite de tasa. *(Origen: `ADR-IT3-003`, `ADR-IT3-010`)*
9. **Medida condicional:** el 100 % de `QA-SEG-03*` se lee para titulares autorizados cuyos remitentes son seguros o fueron aprobados. *(Origen: `ADR-IT3-008`)*
10. **Remitentes:** se comparan en minúsculas y sin espacios en los extremos. La whitelist es de cada titular. *(Origen: `REF-03`)*
11. **Identificador de la reserva:** la reserva que entra al itinerario se identifica por `<titular>:<identificador del mensaje>`. Un mismo correo enviado a dos titulares comparte `Message-ID` y da dos reservas. La ingesta usa esa misma clave para descartar duplicados. *(Origen: `ADR-IT3-003`)*
12. **Mensaje ya incorporado:** un mensaje cuya reserva ya está en el itinerario no vuelve a Mensajes en revisión, aunque se haya quitado al remitente de la whitelist y el correo siga dentro de la ventana de sondeo. *(Origen: `ADR-IT3-003`, `ADR-IT3-008`)*
13. **Aprobar libera antes de borrar:** el Orquestador agrega el remitente a la whitelist, entrega las reservas pendientes de ese remitente a la ingesta y recién entonces las borra de revisión. Si la entrega falla no se pierde ninguna y aprobar de nuevo la reintenta. Aprobar un remitente ya aprobado también libera lo que hubiera quedado pendiente. *(Origen: `ADR-IT3-008`)*
14. **Descartado:** el mensaje descartado conserva solo su identificador y su fecha, no la reserva. No cuenta para el tope de pendientes. *(Origen: `ADR-IT3-008`)*
15. **Viaje de la reserva del correo:** cada reserva que llega por el correo crea su propio viaje en el itinerario del titular. Agrupar reservas en un mismo viaje es de la gestión manual ([SPEC-REF-04](SPEC-REF-04.md)). *(Origen: `REF-03`)*
16. **Tipo desconocido:** si el tipo de la reserva no está en el Registro de tipos, la entrega al Orquestador falla, se reintenta y, agotados los reintentos, va a la cola de mensajes muertos con aviso a operaciones. No se descarta en silencio, porque solo se descarta lo que no pasa la validación del parseo. *(Origen: `ADR-IT3-008`, `ADR-IT3-003`)*
17. **Operaciones del titular:** se piden con la identidad ya encaminada (`X-Viajero-Id`; sin ella, 422). Consultar responde la lista de pendientes con identificador, remitente y resumen (`tipo en lugar (inicio a fin)`). Aprobar y quitar no son error si no hay nada que cambiar. Descartar un mensaje inexistente, ya resuelto o de otro titular responde 404 sin cambiar datos. *(Origen: `ADR-IT3-008`)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-REF-03-01` | El titular autorizó el correo y el remitente está en su whitelist | Llega una reserva normalizada de ese remitente | La reserva pasa a la ingesta para entrar al itinerario | `REF-03`, `QA-SEG-03*`, `ADR-IT3-008` | Test automático |
| `AC-REF-03-02` | El titular autorizó el correo y el remitente no está en su whitelist | Llega una reserva normalizada de ese remitente | La reserva queda en Mensajes en revisión y no entra al itinerario | `REF-03`, `ADR-IT3-008` | Test automático |
| `AC-REF-03-03` | Hay una reserva en Mensajes en revisión | El titular aprueba a ese remitente | El remitente entra a la whitelist y la reserva retenida sigue hacia la ingesta | `REF-03`, `ADR-IT3-008` | Test automático |
| `AC-REF-03-04` | El contenido no pasó la validación del Parseo aislado | El filtro evalúa el mensaje | El filtro no lo retiene en Mensajes en revisión: el descarte ya ocurrió en el parseo | `QA-SEG-03*`, `ADR-IT3-008` | Test automático |
| `AC-REF-03-05` | Una reserva de un remitente desconocido ya está en revisión | El mismo mensaje llega de nuevo en un sondeo posterior | Sigue habiendo una sola entrada en revisión | `ADR-IT3-003`, `ADR-IT3-008` | Test automático |
| `AC-REF-03-06` | Un titular tiene el tope de mensajes pendientes en revisión | Llega otro mensaje de un remitente desconocido | No se retiene, no se pierde y sigue disponible en el buzón para un sondeo posterior dentro de la ventana | `ADR-IT3-008` | Test automático |
| `AC-REF-03-07` | Hay un mensaje en revisión | El titular lo descarta y el mismo mensaje llega de nuevo en un sondeo posterior | No aparece en pendientes ni antes ni después | `ADR-IT3-008` | Test automático |
| `AC-REF-03-08` | Hay un mensaje en revisión y el titular da de alta a su remitente directamente | Se aprueba el remitente | El remitente entra a la whitelist y la reserva retenida sigue hacia la ingesta | `REF-03`, `ADR-IT3-008` | Test automático |
| `AC-REF-03-09` | Un remitente está en la whitelist y ya hay una reserva suya en el itinerario | El titular lo quita de la whitelist y llega otro mensaje suyo | El mensaje nuevo va a revisión y la reserva ya incorporada permanece | `REF-03` | Test automático |
| `AC-REF-03-10` | El titular no tiene mensajes en revisión | Consulta Mensajes en revisión | La respuesta es una lista vacía, no un error | `ADR-IT3-008` | Test automático |
| `AC-REF-03-11` | Un mensaje en revisión cumplió la retención | Pasa el plazo de retención | El mensaje se elimina de revisión | `ADR-IT3-008` | Test automático |
| `AC-REF-03-12` | Se intenta descartar un mensaje que no existe, ya está resuelto o es de otro titular | El titular pide descartarlo | El pedido se rechaza y no cambia ningún dato | `ADR-IT3-008` | Test automático |
| `AC-REF-03-13` | La ingesta ya procesó una reserva con un identificador | Llega de nuevo una reserva con ese identificador | La ingesta la descarta y el Orquestador recibe una sola | `ADR-IT3-003` | Test automático |
| `AC-REF-03-14` | Llega un pico de reservas a la ingesta por encima del límite de tasa | La ingesta entrega al Orquestador | La entrega no supera el límite de tasa configurado | `ADR-IT3-010` | Test automático |
| `AC-REF-03-15` | La entrega de la ingesta al Orquestador falla y agota sus reintentos | Se cumple el último reintento | La reserva va a la cola de mensajes muertos y se avisa a operaciones | `ADR-IT3-003` | Test automático |
| `AC-REF-03-16` | El titular autorizó el correo y su remitente es seguro, y el mismo mensaje se publica en tres sondeos | Los tres mensajes recorren el parseo, el filtro y la ingesta | El itinerario tiene una sola reserva de ese mensaje | `QA-SEG-03*`, `REF-02`, `REF-03` | Test automático |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| Retención de Mensajes en revisión | 30 días, configurable. Nunca menor que la ventana de sondeo de [SPEC-REF-02](SPEC-REF-02.md) | Cuánto tiempo se guardan las reservas normalizadas de remitentes todavía no aprobados, y los identificadores de los descartados | `ADR-IT3-008` |
| Tope de mensajes pendientes por titular | 50, configurable | Cuántos mensajes puede tener en revisión cada titular | `ADR-IT3-008` |
| Retención de identificadores, límite de tasa, reintentos y backoff de la ingesta | Los valores de [SPEC-REF-02](SPEC-REF-02.md): 7 días, 20 mensajes por segundo, 3 reintentos de 1 s, 2 s y 4 s | Idempotencia, tasa de entrega al Orquestador y reintentos de la ruta asíncrona del correo | `ADR-IT3-003`, `ADR-IT3-010` |
| Intervalo de la purga de Mensajes en revisión | 3600 s, configurable (`TROTA_INTERVALO_PURGA`) | Cada cuánto el Orquestador elimina los mensajes que cumplieron la retención | `ADR-IT3-008` |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| Las conexiones HTTP/REST internas entre el Filtro, la ingesta y el Orquestador son llamadas a método detrás de un `Protocol` | `ADR-IT3-008`, `ADR-IT3-010` | El contrato y las fronteras se conservan: el Filtro y la ingesta no importan al Orquestador ni a la base. Lo permite [POLITICAS_SPECS_Y_PLANES.md](../POLITICAS_SPECS_Y_PLANES.md) §4.6 |
| La ingesta recibe del Filtro por la cola `novedades` del Broker, y guarda los identificadores procesados en memoria | `ADR-IT3-003` | El Broker aporta Retry, backoff y cola de mensajes muertos. Si la ingesta se reinicia, la escritura del Orquestador es idempotente por identificador y no duplica |
| `Reserva` gana un campo opcional `codigo` en sus cinco tipos concretos | `ADR-IT3-005` | El esquema del correo trae un código de reserva y el contrato común no tiene dónde guardarlo. Viaja en los datos propios del tipo |

## Fuera de Alcance

* Autorización del buzón, sondeo y parseo: [SPEC-REF-02](SPEC-REF-02.md).
* Novedades de Booking (`QA-PER-01`): la ingesta de esa ruta (cola de novedades) sigue sin spec. Esta spec solo cubre la ingesta de reservas que vienen del correo.
* La pantalla de «Novedades» que no sea Mensajes en revisión.
* El aviso al titular de que hay mensajes por revisar, que usaría `ICanal` (`QA-INT-02`).
* El riesgo de un remitente falsificado que el titular aprueba sin cuidado: el ADR lo reconoce como riesgo y no lo resuelve.
* Inconsistencia a corregir en [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md): el Filtro de remitentes, que corre en los nodos de entrada, lee y escribe la whitelist en el Orquestador, y la lista de excepciones de esos nodos solo nombra a la ingesta y al Gestor de autorización. Esta spec sigue lo que dice el paso 5 de los elementos.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-22 | Versión inicial (`borrador`) | Creación a partir de `REF-03` y de `ADR-IT3-008` |
| 2026-11-23 | Decisiones de revisión | Filtro idempotente por identificador; aprobar, dar de alta y quitar remitentes; descarte de mensajes en revisión con registro; retención de 30 días y tope de 50 por titular; contrato del Servicio de ingesta del lado del correo y verificación de punta a punta de `QA-SEG-03*` |
| 2026-11-23 | Decisiones de implementación fijadas (`PLAN-REF-03`) | Remitentes en minúsculas; identificador de reserva con el titular; mensaje ya incorporado no vuelve a revisión; aprobar libera antes de borrar; descartado conserva solo identificador y fecha; un viaje por reserva del correo; tipo desconocido a mensajes muertos; operaciones y códigos del titular; intervalo de purga; simplificaciones de la ingesta y del campo `codigo` |
