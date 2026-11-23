# SPEC-REF-02. Procesamiento de correo

* **Estado:** aprobada
* **Fecha:** 2026-11-23
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

* **Gestor de autorización** (`ADR-IT3-006`): consentimiento del titular, permisos mínimos, tokens cifrados y revocación. Los tokens cifrados se guardan en la Base primaria de viajes. El Adaptador de correo no lee sin token vigente. Al revocar, deja de leerse el correo y la reserva ya incorporada se conserva.
* **Broker con cola de correo** (`ADR-IT3-001`): un broker con colas separadas. El Adaptador de correo publica en la cola de correo y no bloquea al Orquestador.
* **Colas acotadas** (`ADR-IT3-002`): cada cola tiene un tamaño máximo. Si la cola de correo está llena, el Adaptador de correo no publica y vuelve en el sondeo siguiente. No hay pérdida en ese productor. El mensaje que agota sus reintentos va a una cola de mensajes muertos, con aviso a operaciones.
* **Retry con identificador único** (`ADR-IT3-003`): cada mensaje lleva un identificador único asignado por quien publica. En el correo es el `Message-ID`, o un hash del contenido si falta. Ese identificador viaja con la reserva por el Parseo aislado hasta la ingesta, que descarta duplicados.
* **Parseo aislado** (`ADR-IT3-007`): proceso separado, sin acceso a la base y sin token. Lo que no valida se descarta. Lo válido se entrega normalizado al Filtro de remitentes.
* **Nodos propios** (`ADR-IT3-010`): el Adaptador de correo, el Gestor de autorización y el Parseo aislado corren en nodos de entrada, separados de los nodos del Orquestador. El Gestor es la única pieza de esos nodos que accede a la base (la Base primaria de viajes), para los tokens cifrados. El Parseo no tiene token ni acceso a la base: corre como proceso real del sistema operativo, con su propio entorno, sin credenciales de base ni token.

## Relaciones Permitidas

* **Recibe llamadas / mensajes de:** el cliente, por el API Gateway, para autorizar o revocar. La cola de correo entrega el mensaje crudo al Parseo aislado.
* **Invoca / publica hacia:** la API de correo; la cola de correo del Broker; el Filtro de remitentes de [SPEC-REF-03](SPEC-REF-03.md), con la reserva normalizada y su identificador.
* **Restricciones de frontera:** el Parseo aislado no accede a la base ni al token. El Adaptador de correo no lee sin token vigente. El Adaptador no escribe en la Base de viajes. El contacto del adaptador con el resto del sistema es el broker, salvo el token que le pasa el Gestor en memoria.

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen (ADR / Iteración) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Autorizar o revocar | Síncrono, cliente por API Gateway hacia el Gestor | Consentimiento del titular con el token de acceso que entrega la API de correo (`POST /correo/autorizacion`, cuerpo `{"token": ...}`, encabezado `X-Titular-Id`), o pedido de revocación (`DELETE /correo/autorizacion`, idempotente) | Token cifrado con vencimiento, guardado en la Base primaria de viajes, o su falta | Sin token vigente no hay lectura. Un token vencido es un token no vigente: no se renueva solo, el titular debe volver a autorizar. Autorizar responde 201 con el vencimiento y revocar responde 204. Sin `X-Titular-Id`, ambas responden 401 | `ADR-IT3-006` |
| Sondeo del buzón | El Adaptador llama a la API de correo | Token vigente | Mensajes crudos de la ventana de sondeo, cada uno con su identificador, publicados en la cola de correo. En cada sondeo se vuelven a publicar los de la ventana que ya se habían publicado, con el mismo identificador | Cola llena: no publica, informa que la cola estaba llena (sin lanzar error) y reintenta en el sondeo siguiente. API de correo sin respuesta: el sondeo falla, sin afectar el sondeo de los demás titulares, y se repite en el sondeo siguiente | [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md), `ADR-IT3-002`, `ADR-IT3-003` |
| Parseo | Asíncrono, desde la cola de correo, proceso separado | Mensaje crudo e identificador | Reserva normalizada (con su identificador, el titular y el remitente) hacia el Filtro de remitentes, o descarte de lo que no valida | Un mensaje válido es el que cumple el esquema estructurado de reserva de viaje (tipo, fechas, lugar y código). Lo demás se descarta. El proceso no tiene token ni acceso a la base | `ADR-IT3-007` |

## Reglas de Comportamiento

1. **Autorización previa:** no se lee un buzón sin token vigente del titular. *(Origen: `ADR-IT3-006`)*
2. **Sondeo:** con token vigente, el Adaptador sondea el buzón sin guardar estado: lee la ventana de sondeo completa y publica cada mensaje en la cola de correo con su identificador, aunque ya lo haya publicado en un sondeo anterior. El Adaptador no escribe la Base de viajes, así que no guarda hasta dónde leyó. *(Origen: [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md), `ADR-IT3-003`)*
3. **Aislamiento del parseo:** el Parseo aislado valida y normaliza sin token y sin base. Un mensaje es válido si cumple el esquema estructurado de reserva de viaje. Lo inválido se descarta. Lo válido pasa al Filtro de remitentes. *(Origen: `ADR-IT3-007`)*
4. **Revocación:** al revocar, el Adaptador deja de leer. La reserva ya incorporada al itinerario se conserva. *(Origen: `ADR-IT3-006`)*
5. **Idempotencia:** el identificador asignado por el Adaptador llega intacto al otro lado del parseo para que la ingesta pueda descartar duplicados. Como cada sondeo repite los mensajes de la ventana, la ingesta es quien evita que un mismo correo cree dos reservas. *(Origen: `ADR-IT3-003`)*
6. **Vencimiento del token:** un token vencido cuenta como no vigente. El Adaptador no lee y el titular debe volver a autorizar. *(Origen: `ADR-IT3-006`)*
7. **Mensaje que agota reintentos:** va a la cola de mensajes muertos, con aviso a operaciones. *(Origen: `ADR-IT3-002`, `ADR-IT3-003`)*
8. **Identificador sin `Message-ID`:** si el correo no trae `Message-ID`, el identificador es el SHA-256 del cuerpo crudo. *(Origen: `ADR-IT3-003`)*
9. **Mensaje publicado:** el Adaptador publica en la cola de correo el identificador, el titular, el remitente y el cuerpo crudo. Nunca el token. *(Origen: `ADR-IT3-007`)*
10. **Validación del Parseo:** el cuerpo debe ser un JSON con exactamente `tipo`, `inicio`, `fin`, `lugar` y `codigo`. Se descartan los campos extra, los textos vacíos o de más de 200 caracteres (`tipo`, `lugar` y `codigo`), los caracteres de control, un identificador, titular o remitente de más de 200 caracteres o con caracteres de control, un `fin` anterior a `inicio` y un cuerpo de más de 64 KB. *(Origen: `ADR-IT3-007`)*
11. **Descarte y fallo del Parseo:** un mensaje que el Parseo descarta cuenta como entregado: no se reintenta ni va a la cola de mensajes muertos. Si el proceso de parseo falla o muere, sí se reintenta (regla 7). *(Origen: `ADR-IT3-002`, `ADR-IT3-007`)*
12. **Sondeo programado:** en cada ciclo el Adaptador sondea a todos los titulares con token guardado, vigente o vencido; la vigencia la comprueba el Adaptador al leer. *(Origen: `ADR-IT3-006`)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-REF-02-01` | El titular no autorizó la lectura, o revocó el acceso | Llega el momento de sondear su buzón | El Adaptador no lee el correo | `QA-SEG-03*`, `ADR-IT3-006` | Test automático |
| `AC-REF-02-07` | El token del titular venció | Llega el momento de sondear su buzón | El Adaptador no lee el correo y el titular debe volver a autorizar | `QA-SEG-03*`, `ADR-IT3-006` | Test automático |
| `AC-REF-02-02` | El titular autorizó y hay un token vigente | El Adaptador sondea y el buzón tiene un mensaje | El mensaje queda en la cola de correo con `Message-ID` o, si falta, con un hash de su contenido | `REF-02`, `CON-02`, `ADR-IT3-003` | Test automático |
| `AC-REF-02-03` | La cola de correo está llena | El Adaptador intenta publicar | No publica, no pierde el mensaje y vuelve en el sondeo siguiente | `ADR-IT3-002` | Test automático |
| `AC-REF-02-04` | Un mensaje de la cola de correo no cumple el esquema de reserva de viaje, o trae contenido malicioso | El Parseo aislado lo procesa | Lo descarta y no lo entrega al Filtro de remitentes. El proceso no lee ni escribe la base ni el token | `ADR-IT3-007` | Test automático |
| `AC-REF-02-08` | El Parseo aislado corre como proceso del sistema operativo | Se inspecciona su entorno | Ese proceso no tiene credenciales de la base ni el token | `ADR-IT3-007` | Test automático |
| `AC-REF-02-09` | Un mismo mensaje del buzón sigue dentro de la ventana en dos sondeos seguidos | El Adaptador sondea dos veces | El mensaje se publica en ambos sondeos con el mismo identificador | `ADR-IT3-003` | Test automático |
| `AC-REF-02-10` | Un mensaje de la cola de correo agota sus reintentos | Se cumple el último reintento | El mensaje va a la cola de mensajes muertos y se avisa a operaciones | `ADR-IT3-002`, `ADR-IT3-003` | Test automático |
| `AC-REF-02-05` | Un mensaje de la cola de correo valida como reserva de viaje | El Parseo aislado lo procesa | Entrega la reserva normalizada, con su identificador, al Filtro de remitentes | `REF-02`, `ADR-IT3-007` | Test automático |
| `AC-REF-02-06` | Una reserva de correo ya está en el itinerario y el titular revoca el acceso | El Gestor revoca | El Adaptador deja de leer y la reserva ya incorporada permanece | `QA-SEG-03*`, `ADR-IT3-006` | Test automático |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| Frecuencia de sondeo | 15 minutos por buzón, configurable por despliegue | Cada cuánto el Adaptador consulta un buzón autorizado | `ADR-IT3-006`; el valor lo fija el paso 5 de [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md) |
| Ventana de sondeo | 7 días, configurable | Cuántos días hacia atrás lee el Adaptador en cada sondeo | `ADR-IT3-003` |
| Tamaño máximo de la cola de correo | 100 mensajes (5 en los tests), configurable | Tope de mensajes retenidos en la cola de correo | `ADR-IT3-002` |
| Límite de reintentos y backoff | 3 reintentos con espera exponencial de 1 s, 2 s y 4 s, y luego cola de mensajes muertos | Cuántas veces y con qué espera se reintenta en la ruta asíncrona del correo | `ADR-IT3-003` |
| Retención de identificadores ya procesados | 7 días, configurable. Nunca menor que la ventana de sondeo | Cuánto tiempo se conservan los identificadores para descartar duplicados | `ADR-IT3-003` |
| Límite de tasa de entrega de la ingesta al Orquestador | 20 mensajes por segundo, configurable | Tope de entregas para que el pico de entrada no consuma los nodos del Orquestador | `ADR-IT3-010` |
| Vigencia del token de acceso | 60 minutos, configurable | Cuánto dura un token antes de contar como no vigente | `ADR-IT3-006` |
| Tamaño máximo del correo crudo | 64 KB | Tope de lo que el Parseo acepta; lo que lo excede se descarta | `ADR-IT3-007` |
| Largo máximo de un campo de texto de la reserva | 200 caracteres | Tope de `tipo`, `lugar` y `codigo`, y de identificador, titular y remitente | `ADR-IT3-007` |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| La API de correo se simula con un mock local al que se le puede inyectar demora o caída | `CON-02` | El Adaptador de correo y el contrato se conservan. Lo permite [POLITICAS_SPECS_Y_PLANES.md](../POLITICAS_SPECS_Y_PLANES.md) §4.6. |
| Los mensajes de prueba usan un formato estructurado simple (tipo, fechas, lugar y código) y no los formatos reales de cada proveedor | `ADR-IT3-007` | El Parseo aislado conserva su responsabilidad: validar entrada no confiable y descartar lo que no cumple. Cambia el esquema, no el aislamiento. |
| El token vencido no se renueva solo: el titular vuelve a autorizar | `ADR-IT3-006` | Se conserva el control de acceso por token vigente. La renovación automática es un costo que el ADR reconoce y no es lo que se demuestra. |
| La clave que cifra los tokens se toma de una variable de entorno | `ADR-IT3-006` | Los tokens se guardan cifrados en la Base primaria de viajes igual que en el diseño. Un servicio de gestión de claves no cambia la responsabilidad del Gestor. |

## Fuera de Alcance

* Whitelist, Mensajes en revisión y la entrada de la reserva al itinerario después del filtro: [SPEC-REF-03](SPEC-REF-03.md).
* La medida del 100 % de `QA-SEG-03*` («ven reflejadas las reservas en sus itinerarios») se verifica de punta a punta en [SPEC-REF-03](SPEC-REF-03.md), porque esta spec termina antes del Filtro de remitentes y de la ingesta.
* El Servicio de ingesta (descarte de duplicados y entrega al Orquestador): su contrato del lado del correo se especifica en [SPEC-REF-03](SPEC-REF-03.md). Esta spec depende de él para la idempotencia.
* Renovación automática del token de acceso.
* Novedades de Booking (`QA-PER-01`) y notificaciones (`QA-INT-02`).
* Qué pasa si el titular pide eliminar una reserva ya incorporada al revocar: el ADR lo deja pendiente.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-22 | Versión inicial (`borrador`) | Creación a partir de `REF-02` y de los ADR aceptados que la iteración le asocia |
| 2026-11-23 | Decisiones de revisión | Esquema estructurado de mensaje válido; valores de parámetros; sondeo de ventana sin estado con idempotencia por identificador; token con vencimiento sin renovación; Parseo como proceso real del sistema operativo; Base primaria de viajes nombrada para los tokens; criterios de aceptación nuevos |
| 2026-11-23 | Decisiones de implementación fijadas (`PLAN-REF-02`) | Cuerpo y códigos de los endpoints de autorización; hash SHA-256 del cuerpo sin `Message-ID`; mensaje publicado sin token; reglas de validación del Parseo con topes de 64 KB y 200 caracteres; descarte contado como entregado; resultado de cola llena; sondeo de todos los titulares con token guardado; la reserva normalizada lleva titular y remitente |
