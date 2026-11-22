# SPEC-REF-03. Filtros y whitelists

* **Estado:** borrador
* **Fecha:** 2026-11-22
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `REF-03`, `QA-SEG-03*` |
| **ADRs** | `ADR-IT3-008` |
| **Elemento del paso 5** | [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md) Filtro de remitentes, whitelist, Mensajes en revisión |
| **Incremento (Slice)** | Slice 3 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

Debe permitir filtrar y crear listas de remitentes seguros (whitelists) para ciertos correos electrónicos de viaje.

El Filtro de remitentes está entre el Parseo aislado de [SPEC-REF-02](SPEC-REF-02.md) y la ingesta. La whitelist y los mensajes en revisión los guarda el Orquestador de viajes.

## Drivers que guían el cómo

* **`QA-SEG-03*`:** la medida del 100 % queda condicional. Se cumple para los titulares autorizados cuyos remitentes son seguros o fueron aprobados. Una reserva que espera aprobación no está en el itinerario hasta que el titular actúa. Lo que se descarta es solo el contenido que no pasa la validación del parseo. *(Origen: [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md), párrafo de tensión de `QA-SEG-03*` con la whitelist; [ADR-IT3-008](../RONDA_1/ADRs/ITERACION_3/ADR-IT3-008.md))*

## Conceptos de diseño aceptados

* **Whitelist con Mensajes en revisión** (`ADR-IT3-008`): el Filtro de remitentes ubica la whitelist y los mensajes en revisión entre el Parseo aislado y la ingesta. Un remitente desconocido no se descarta: queda en Mensajes en revisión hasta que el titular lo aprueba. Al aprobarlo, el remitente entra a la whitelist y la reserva sigue hacia la ingesta. Lo que se descarta es solo el contenido que no pasa la validación del parseo.

## Relaciones Permitidas

* **Recibe llamadas / mensajes de:** el Parseo aislado, con la reserva normalizada y su identificador ([SPEC-REF-02](SPEC-REF-02.md)). El titular, por el API Gateway y el balanceador, aprueba un remitente o consulta Mensajes en revisión.
* **Invoca / publica hacia:** el Orquestador de viajes, que guarda la whitelist y los mensajes en revisión. La ingesta, cuando el remitente es seguro o acaba de ser aprobado, recibe la reserva normalizada.
* **Restricciones de frontera:** el filtro no descarta una reserva válida de un remitente desconocido. No reemplaza al Parseo aislado: no valida el contenido del mensaje. No escribe la reserva en la Base de viajes por su cuenta; la entrega a la ingesta, y el Orquestador es el dueño de lo que se guarda.

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen (ADR / Iteración) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Filtrar remitente | Interna, después del Parseo aislado | Reserva normalizada e identificador | Hacia la ingesta si el remitente está en la whitelist; si no, Mensajes en revisión | [sin especificar] | `ADR-IT3-008` |
| Aprobar remitente | Síncrono, cliente por el API Gateway hacia el Orquestador | Titular y remitente retenido | El remitente se suma a la whitelist y la reserva retenida sigue hacia la ingesta | [sin especificar] | [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md), `ADR-IT3-008` |

## Reglas de Comportamiento

1. **Remitente seguro:** si el remitente está en la whitelist del titular, la reserva pasa a la ingesta. *(Origen: [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md))*
2. **Remitente desconocido:** la reserva queda en Mensajes en revisión. No se descarta y no entra al itinerario hasta la aprobación. *(Origen: `ADR-IT3-008`)*
3. **Aprobación:** el titular aprueba al remitente, el remitente entra a la whitelist y la reserva retenida sigue hacia la ingesta. La aprobación vale para los mensajes siguientes de ese remitente. *(Origen: `ADR-IT3-008`)*
4. **Medida condicional:** el 100 % de `QA-SEG-03*` se lee para titulares autorizados cuyos remitentes son seguros o fueron aprobados. *(Origen: `ADR-IT3-008`)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-REF-03-01` | El titular autorizó el correo y el remitente está en su whitelist | Llega una reserva normalizada de ese remitente | La reserva pasa a la ingesta para entrar al itinerario | `REF-03`, `QA-SEG-03*`, `ADR-IT3-008` | Test automático |
| `AC-REF-03-02` | El titular autorizó el correo y el remitente no está en su whitelist | Llega una reserva normalizada de ese remitente | La reserva queda en Mensajes en revisión y no entra al itinerario | `REF-03`, `ADR-IT3-008` | Test automático |
| `AC-REF-03-03` | Hay una reserva en Mensajes en revisión | El titular aprueba a ese remitente | El remitente entra a la whitelist y la reserva retenida sigue hacia la ingesta | `REF-03`, `ADR-IT3-008` | Test automático |
| `AC-REF-03-04` | El contenido no pasó la validación del Parseo aislado | El filtro evalúa el mensaje | El filtro no lo retiene en Mensajes en revisión: el descarte ya ocurrió en el parseo | `QA-SEG-03*`, `ADR-IT3-008` | Test automático |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| Retención de Mensajes en revisión | [sin especificar] | Cuánto tiempo se guardan las reservas normalizadas de remitentes todavía no aprobados | `ADR-IT3-008` |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| Ninguna adicional | `ADR-IT3-008` | La whitelist, la retención y la aprobación del titular se conservan como las fija el ADR. |

## Fuera de Alcance

* Autorización del buzón, sondeo y parseo: [SPEC-REF-02](SPEC-REF-02.md).
* Novedades de Booking (`QA-PER-01`) y la pantalla de «Novedades» que no sea Mensajes en revisión.
* La sección «Novedades» de proveedores.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-22 | Versión inicial (`borrador`) | Creación a partir de `REF-03` y de `ADR-IT3-008` |
