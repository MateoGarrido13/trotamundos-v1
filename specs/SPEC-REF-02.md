# SPEC-REF-02. Procesamiento de correo

* **Estado:** borrador
* **Fecha:** 2026-11-22
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `REF-02`, `QA-SEG-03*`, `CON-02` |
| **ADRs** | `ADR-IT3-006`, `ADR-IT3-001`, `ADR-IT3-002`, `ADR-IT3-003`, `ADR-IT3-007`, `ADR-IT3-010` |
| **Elemento del paso 5** | [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md) Gestor de autorización del correo, Adaptador de correo, cola de correo del Broker, Parseo aislado |
| **Incremento (Slice)** | Slice 3 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

El sistema debe sondear y escanear el correo electrónico de los usuarios en busca de correos relacionados con viajes para agregar automáticamente las reservas al itinerario.

Esta spec llega hasta el Parseo aislado, que valida el mensaje y entrega la reserva normalizada al Filtro de remitentes. La whitelist y Mensajes en revisión son [SPEC-REF-03](SPEC-REF-03.md).

## Drivers que guían el cómo

* **`QA-SEG-03*`:** el sistema accede al correo solo con la autorización del titular. Sin token vigente el Adaptador de correo no lee. Al revocar, deja de leerse el correo y la reserva ya incorporada al itinerario se conserva. *(Origen: [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md), secuencia «Reserva desde el correo»; [ADR-IT3-006](../RONDA_1/ADRs/ITERACION_3/ADR-IT3-006.md))*
* **`CON-02`:** el correo se integra por API. El Adaptador de correo es la capa anti-corrupción de esa API. *(Origen: [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md), Adaptador de correo)*

## Conceptos de diseño aceptados

* **Gestor de autorización** (`ADR-IT3-006`): consentimiento del titular, permisos mínimos, tokens cifrados y revocación. El Adaptador de correo no lee sin token vigente. Al revocar, deja de leerse el correo y la reserva ya incorporada se conserva.
* **Broker con cola de correo** (`ADR-IT3-001`): un broker con colas separadas. El Adaptador de correo publica en la cola de correo y no bloquea al Orquestador.
* **Colas acotadas** (`ADR-IT3-002`): cada cola tiene un tamaño máximo. Si la cola de correo está llena, el Adaptador de correo no publica y vuelve en el sondeo siguiente. No hay pérdida en ese productor. El mensaje que agota sus reintentos va a una cola de mensajes muertos, con aviso a operaciones.
* **Retry con identificador único** (`ADR-IT3-003`): cada mensaje lleva un identificador único asignado por quien publica. En el correo es el `Message-ID`, o un hash del contenido si falta. Ese identificador viaja con la reserva por el Parseo aislado hasta la ingesta, que descarta duplicados.
* **Parseo aislado** (`ADR-IT3-007`): proceso separado, sin acceso a la base y sin token. Lo que no valida se descarta. Lo válido se entrega normalizado al Filtro de remitentes.
* **Nodos propios** (`ADR-IT3-010`): el Adaptador de correo, el Gestor de autorización y el Parseo aislado corren en nodos de entrada, separados de los nodos del Orquestador. El Gestor es la única pieza de esos nodos que accede a la base, para los tokens cifrados. El Parseo no tiene token ni acceso a la base.

## Relaciones Permitidas

* **Recibe llamadas / mensajes de:** el cliente, por el API Gateway, para autorizar o revocar. La cola de correo entrega el mensaje crudo al Parseo aislado.
* **Invoca / publica hacia:** la API de correo; la cola de correo del Broker; el Filtro de remitentes de [SPEC-REF-03](SPEC-REF-03.md), con la reserva normalizada y su identificador.
* **Restricciones de frontera:** el Parseo aislado no accede a la base ni al token. El Adaptador de correo no lee sin token vigente. El Adaptador no escribe en la Base de viajes. El contacto del adaptador con el resto del sistema es el broker, salvo el token que le pasa el Gestor en memoria.

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen (ADR / Iteración) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Autorizar o revocar | Síncrono, cliente por API Gateway hacia el Gestor | Consentimiento del titular, o pedido de revocación | Token cifrado vigente, o su falta | Sin token vigente no hay lectura | `ADR-IT3-006` |
| Sondeo del buzón | El Adaptador llama a la API de correo | Token vigente | Mensaje crudo con identificador, publicado en la cola de correo | Cola llena: no publica y reintenta en el sondeo siguiente | [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md), `ADR-IT3-002` |
| Parseo | Asíncrono, desde la cola de correo, proceso separado | Mensaje crudo e identificador | Reserva normalizada hacia el Filtro de remitentes, o descarte de lo que no valida | El proceso no tiene token ni acceso a la base | `ADR-IT3-007` |

## Reglas de Comportamiento

1. **Autorización previa:** no se lee un buzón sin token vigente del titular. *(Origen: `ADR-IT3-006`)*
2. **Sondeo:** con token vigente, el Adaptador sondea el buzón y publica cada mensaje en la cola de correo con su identificador. *(Origen: [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md))*
3. **Aislamiento del parseo:** el Parseo aislado valida y normaliza sin token y sin base. Lo inválido se descarta. Lo válido pasa al Filtro de remitentes. *(Origen: `ADR-IT3-007`)*
4. **Revocación:** al revocar, el Adaptador deja de leer. La reserva ya incorporada al itinerario se conserva. *(Origen: `ADR-IT3-006`)*
5. **Idempotencia:** el identificador asignado por el Adaptador llega intacto al otro lado del parseo para que la ingesta pueda descartar duplicados. *(Origen: `ADR-IT3-003`)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-REF-02-01` | El titular no autorizó la lectura, o revocó el acceso | Llega el momento de sondear su buzón | El Adaptador no lee el correo | `QA-SEG-03*`, `ADR-IT3-006` | Test automático |
| `AC-REF-02-02` | El titular autorizó y hay un token vigente | El Adaptador sondea y el buzón tiene un mensaje | El mensaje queda en la cola de correo con `Message-ID` o, si falta, con un hash de su contenido | `REF-02`, `CON-02`, `ADR-IT3-003` | Test automático |
| `AC-REF-02-03` | La cola de correo está llena | El Adaptador intenta publicar | No publica, no pierde el mensaje y vuelve en el sondeo siguiente | `ADR-IT3-002` | Test automático |
| `AC-REF-02-04` | Un mensaje de la cola de correo no pasa la validación del parseo | El Parseo aislado lo procesa | Lo descarta y no lo entrega al Filtro de remitentes. El proceso no lee ni escribe la base ni el token | `ADR-IT3-007` | Test automático |
| `AC-REF-02-05` | Un mensaje de la cola de correo valida como reserva de viaje | El Parseo aislado lo procesa | Entrega la reserva normalizada, con su identificador, al Filtro de remitentes | `REF-02`, `ADR-IT3-007` | Test automático |
| `AC-REF-02-06` | Una reserva de correo ya está en el itinerario y el titular revoca el acceso | El Gestor revoca | El Adaptador deja de leer y la reserva ya incorporada permanece | `QA-SEG-03*`, `ADR-IT3-006` | Test automático |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| Frecuencia de sondeo | 15 minutos por buzón, configurable por despliegue | Cada cuánto el Adaptador consulta un buzón autorizado | `ADR-IT3-006`; el valor lo fija el paso 5 de [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md) |
| Tamaño máximo de la cola de correo | [sin especificar] | Tope de mensajes retenidos en la cola de correo | `ADR-IT3-002` |
| Límite de reintentos y backoff | [sin especificar] | Cuántas veces y con qué espera se reintenta en la ruta asíncrona del correo | `ADR-IT3-003` |
| Retención de identificadores ya procesados | [sin especificar] | Cuánto tiempo se conservan los identificadores para descartar duplicados | `ADR-IT3-003` |
| Límite de tasa de entrega de la ingesta al Orquestador | [sin especificar] | Tope de entregas para que el pico de entrada no consuma los nodos del Orquestador | `ADR-IT3-010` |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| La API de correo se simula con un mock local al que se le puede inyectar demora o caída | `CON-02` | El Adaptador de correo y el contrato se conservan. Lo permite [POLITICAS_SPECS_Y_PLANES.md](../POLITICAS_SPECS_Y_PLANES.md) §4.6. |

## Fuera de Alcance

* Whitelist, Mensajes en revisión y la entrada de la reserva al itinerario después del filtro: [SPEC-REF-03](SPEC-REF-03.md).
* Novedades de Booking (`QA-PER-01`) y notificaciones (`QA-INT-02`).
* Qué pasa si el titular pide eliminar una reserva ya incorporada al revocar: el ADR lo deja pendiente.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-22 | Versión inicial (`borrador`) | Creación a partir de `REF-02` y de los ADR aceptados que la iteración le asocia |
