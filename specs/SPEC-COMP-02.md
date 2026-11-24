# SPEC-COMP-02. Cliente web

* **Estado:** aprobada
* **Fecha:** 2026-11-23
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `CON-01`, `REF-01`, `REF-03`, `REF-04`, `REF-05`, `REF-07`, `QA-SEG-02`, `QA-PER-01`, `QA-PER-02` |
| **ADRs** | `ADR-008`, `ADR-IT2-001`, `ADR-IT2-002`, `ADR-IT4-004`, `ADR-IT4-007`, `ADR-IT4-008`, `ADR-IT4-010`, `ADR-IT3-008`, `ADR-IT6-001` |
| **Elemento del paso 5** | Cliente web: [RONDA_1/ITERACION_1.md](../RONDA_1/ITERACION_1.md) §Cliente web; sección «Novedades» y pantalla de Mensajes en revisión ([ITERACION_3.md](../RONDA_1/ITERACION_3.md)); panel del Asistente Virtual ([RONDA_2/ITERACION_1.md](../RONDA_2/ITERACION_1.md)) |
| **Incremento (Slice)** | Transversal: Slices 2, 3, 4 y 5 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

`CON-01` exige dos versiones, web y móvil. El Cliente web es la versión de escritorio del panel: pide la vista principal agrupada por viaje, la cotización y el alta (`ITERACION_1`), presenta la sección «Novedades» y la pantalla de Mensajes en revisión (`ITERACION_3`), y ofrece el panel conversacional del Asistente Virtual (`RONDA_2/ITERACION_1`). No contiene reglas de negocio: todo permiso, validación e idempotencia vive en el backend.

## Drivers que guían el cómo

* **`CON-01`:** el cliente habla con un único punto de entrada, el API Gateway, que en el prototipo es la app principal. *(Origen: [RONDA_1/LISTADO_DRIVERS_RONDA_1.md](../RONDA_1/LISTADO_DRIVERS_RONDA_1.md))*
* **`QA-SEG-02`:** ante un acceso denegado el cliente presenta la página «Error 401». *(Origen: [ITERACION_4.md](../RONDA_1/ITERACION_4.md) §Control de acceso al itinerario)*
* **`QA-PER-02`:** la cotización se muestra con la grilla que devuelva el borde, completa o parcial. *(Origen: [ITERACION_2.md](../RONDA_1/ITERACION_2.md))*
* **`QA-PER-01`:** la sección «Novedades» refleja lo que el backend informa, con una espera máxima de 5 minutos desde que el listener detecta la actualización. *(Origen: LISTADO_DRIVERS_RONDA_1)*

## Conceptos de diseño aceptados

* **API Gateway como único punto de entrada** (`ADR-008`): el cliente no habla con ningún otro servicio.
* **Sesión con token firmado de vida corta** (`ADR-IT4-004`): el Gateway autentica y el Orquestador autoriza. El cliente guarda el token y lo envía en cada pedido; cuando venza, vuelve al login.
* **Clave de operación generada por el cliente** (`ADR-IT4-008`): el cliente genera la clave de cada acción del usuario y la reutiliza si reintenta, para que un reintento no duplique.
* **Autorización por itinerario** (`ADR-IT4-007`): el cliente presenta «Error 401» cuando el Orquestador responde acceso denegado.
* **Whitelist con «Mensajes en revisión»** (`ADR-IT3-008`): el cliente permite aprobar o descartar un remitente.
* **Adaptador de agencia detrás de `IAgencia`** (`ADR-IT4-010`): el viajero ve el caso «en trámite» y su avance en «Novedades».
* **Asistente Virtual en nodos propios** (`ADR-IT6-001`): el cliente devuelve en cada pedido el contexto firmado que recibió en el anterior.

## Relaciones Permitidas

* **Recibe llamadas de:** el viajero, desde el navegador.
* **Invoca:** el API Gateway, por HTTPS/REST (en el prototipo, la app principal): vista principal, alta de viaje, miembros, reservas, novedades, casos, agencia preferida, revisión, asistente y cotización.
* **Restricciones de frontera:** el cliente no llama a la API de una agencia, de un proveedor ni del correo. No calcula permisos: los pide. No conserva datos de otras cuentas. No envía coordenadas de ubicación: el web no las usa.

## Pantallas

| Pantalla | Qué hace | Endpoints que usa |
| :--- | :--- | :--- |
| Ingreso | Pide la identidad. Mientras no exista [SPEC-COMP-05](SPEC-COMP-05.md) la identidad es simulada: se escribe el nombre de la cuenta | — (con COMP-05: login) |
| Mis viajes | Lista los itinerarios de la cuenta y, de cada uno, sus viajes agrupados con sus reservas. Alta de viaje | `GET /itinerarios`, `GET /itinerarios/{id}`, `POST /viajes` |
| Viaje | Reservas del viaje; alta, edición y baja manual; archivados | `POST/PATCH/DELETE /itinerarios/{id}/reservas`, `GET /viajes/archivados` |
| Miembros | Lista, agrega y quita miembros del itinerario (el organizador) | `GET/POST/DELETE /itinerarios/{id}/miembros` |
| Novedades | Cambios de proveedores no aplicados, avisos de Booking y estado de los casos de ayuda; reintento de un caso «sin entregar» | `GET /itinerarios/{id}/novedades`, `GET /casos`, `POST /casos/{id}/reintentar`, y el listado de anuncios de [SPEC-COMP-07](SPEC-COMP-07.md) |
| Agencia y problemas | Elegir agencia con consentimiento; reportar un problema sobre una reserva | `PUT/GET /agencia-preferida`, `POST /casos` |
| Mensajes en revisión | Reservas de remitentes desconocidos; aprobar o descartar; quitar un remitente seguro | `GET /revision`, `POST /revision/remitentes`, `DELETE /revision/remitentes/{r}`, `POST /revision/descartar` |
| Correo | Autorizar o revocar la lectura del correo | `POST/DELETE /correo/autorizacion` |
| Asistente | Panel de chat con acciones a confirmar | `POST /asistente/turno`, `POST /asistente/accion` |
| Cotización | Elegir fecha, hospedaje y compañía; ver la grilla, completa o parcial | `GET /cotizaciones` de [SPEC-COMP-06](SPEC-COMP-06.md) |
| Error 401 | Página a la que se redirige ante un acceso denegado | — |

## Contrato e Interfaces

El cliente solo consume. Cada fila es una operación del Gateway; las entradas, salidas y códigos exactos están en la spec de cada servicio.

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen (ADR / Iteración) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /itinerarios`, `GET /itinerarios/{id}` | Síncrono · REST, cliente hacia el Gateway | Token de sesión | Itinerarios de la cuenta; viajes agrupados con sus reservas | 401 sin sesión, 403 sin permiso, 503/504: se conserva lo mostrado y se permite reintentar | `ADR-008`, `ADR-IT4-004`, [SPEC-REF-01](SPEC-REF-01.md) |
| `POST /viajes` | Síncrono · REST | Nombre del viaje (hasta 100 caracteres), itinerario opcional; clave de operación | Viaje creado, con identificador asignado por el sistema | 403 sin permiso o itinerario ajeno, 422 campos inválidos, 503/504 con la misma clave en el reintento | `ADR-IT4-008`, [SPEC-COMP-01](SPEC-COMP-01.md) |
| `POST/PATCH/DELETE /itinerarios/{id}/reservas` | Síncrono · REST | Reserva (con `lugar`), clave de operación | Reserva persistida, actualizada o dada de baja | 403 → «Error 401»; 404; 409 reserva en baja; 422 | `ADR-IT4-008`, [SPEC-REF-04](SPEC-REF-04.md) |
| `GET /viajes/archivados` | Síncrono · REST | Token | Viajes archivados con sus reservas | Lista vacía si no hay | [SPEC-REF-01](SPEC-REF-01.md) |
| `GET/POST/DELETE /itinerarios/{id}/miembros` | Síncrono · REST | Cuenta del miembro, rol | Lista o confirmación | 403 si no es organizador | `ADR-IT4-007`, [SPEC-REF-04](SPEC-REF-04.md) |
| `GET /itinerarios/{id}/novedades` y anuncios de Booking | Síncrono · REST; sondeo cada `refresco_novedades_segundos` | Token | Cambios no aplicados, avisos y estado de los casos | 503/504: conserva lo mostrado | `QA-PER-01`, [SPEC-COMP-07](SPEC-COMP-07.md) |
| `GET /casos`, `POST /casos`, `POST /casos/{id}/reintentar`, `PUT/GET /agencia-preferida` | Síncrono · REST | Reserva afectada y consentimiento; agencia elegida | Caso y su estado; agencia preferida | 403, 422 sin consentimiento | `ADR-IT4-010`, [SPEC-REF-05](SPEC-REF-05.md) |
| `GET /revision`, `POST /revision/remitentes`, `DELETE /revision/remitentes/{r}`, `POST /revision/descartar` | Síncrono · REST | Remitente o reserva en revisión | Lista o confirmación | 403, 404 | `ADR-IT3-008`, [SPEC-REF-03](SPEC-REF-03.md) |
| `POST/DELETE /correo/autorizacion` | Síncrono · REST | Autorización del usuario | Estado de la autorización | 403, 503 | [SPEC-COMP-04](SPEC-COMP-04.md) |
| `POST /asistente/turno`, `POST /asistente/accion` | Síncrono · REST | Mensaje o acción confirmada, contexto firmado | Respuesta, contexto firmado nuevo, acción pendiente o menú guiado | 503: se muestra el menú guiado | `ADR-IT6-001`, [SPEC-REF-07](SPEC-REF-07.md) |
| `GET /cotizaciones` | Síncrono · REST | Fecha, hospedaje, compañía | Grilla completa o parcial con los orígenes que no respondieron | 504: se conserva lo mostrado; aviso «en curso» sin error | `ADR-IT2-002`, [SPEC-COMP-06](SPEC-COMP-06.md) |

## Reglas de Comportamiento

1. **Sin lógica de negocio:** el cliente solo presenta lo que el backend resuelve. No decide permisos, ni valida tipos de reserva, ni deduplica. *(Origen: `ADR-IT4-007`)*
2. **«Error 401»:** toda respuesta 403 de una operación sobre un itinerario lleva a la página «Error 401». *(Origen: `QA-SEG-02`)*
3. **Clave de operación:** cada acción de escritura genera una clave nueva. Si el pedido falla por red o responde 503, el reintento usa **la misma clave**. Una acción nueva usa una nueva. *(Origen: `ADR-IT4-008`)*
4. **Servicio no disponible:** ante 503 o 504 el cliente conserva lo que estaba en pantalla, avisa y permite reintentar. No borra datos ni pierde lo que el usuario escribió. *(Origen: `ADR-IT2-002`)*
5. **Cotización degradada:** una grilla parcial se muestra con el aviso de qué orígenes no respondieron. Un aviso de «cotización en curso» se muestra como tal, sin error. *(Origen: `ADR-IT2-002`)*
6. **Contexto del asistente:** el cliente guarda el contexto firmado de cada respuesta y lo devuelve en el siguiente turno. Si el asistente degrada a menú guiado, el cliente muestra el menú. Una acción pendiente se ejecuta solo con una confirmación explícita del usuario. *(Origen: `ADR-IT6-001`)*
7. **Consentimiento visible:** antes de reportar un problema el cliente muestra qué datos viajarán a la agencia y exige el consentimiento. *(Origen: `ADR-IT4-010`)*
8. **Sin datos en el DOM por texto:** todo texto que viene del backend (nombres, lugares, descripciones, mensajes del asistente) se inserta como texto y nunca como HTML. *(Origen: seguridad de la interfaz, `QA-SEG-03*`)*
9. **Sin dependencias:** HTML5, CSS y JavaScript sin framework ni paso de compilación. Lo sirve la app principal bajo `/web`. *(Origen: [PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) §2)*
10. **Novedades:** la sección se actualiza sola cada 60 s mientras está abierta y siempre al abrirla. *(Origen: `QA-PER-01`, parámetro)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-COMP-02-01` | Un viajero ingresó | Abre «Mis viajes» | Ve sus itinerarios y, de cada uno, las reservas agrupadas por viaje | `REF-01` | Test de navegador |
| `AC-COMP-02-02` | Un participante en un itinerario | Intenta quitar a un miembro | El backend responde 403 y el cliente presenta «Error 401» | `QA-SEG-02` | Test de navegador |
| `AC-COMP-02-03` | Un organizador | Da de alta una reserva y la red falla en la primera respuesta | El reintento reutiliza la clave y la reserva aparece **una** vez | `ADR-IT4-008` | Test de navegador con corte inyectado |
| `AC-COMP-02-04` | La base de viajes no está disponible | El viajero pide la vista | El cliente conserva lo mostrado, avisa y ofrece reintentar | `ADR-IT2-002` | Test de navegador |
| `AC-COMP-02-05` | Hay un caso «sin entregar» | El viajero lo reintenta desde «Novedades» | El caso vuelve a «en trámite» | `REF-05` | Test de navegador |
| `AC-COMP-02-06` | Un mensaje del backend contiene `<script>` | Se muestra en cualquier pantalla | Se ve como texto y no se ejecuta | `QA-SEG-03*` | Test de navegador |
| `AC-COMP-02-07` | El viajero no eligió agencia | Intenta reportar un problema | El cliente lo lleva a elegir agencia con el consentimiento explícito | `REF-05` | Test de navegador |
| `AC-COMP-02-08` | Hay una reserva de un remitente desconocido | El viajero la aprueba | Sale de «Mensajes en revisión» y entra al itinerario | `REF-03` | Test de navegador |
| `AC-COMP-02-09` | El asistente propone una acción | El viajero no confirma | No se ejecuta nada | `REF-07` | Test de navegador |
| `AC-COMP-02-10` | El asistente degrada a menú guiado | El viajero escribe | El cliente muestra el menú y no un error | `REF-07` | Test de navegador |
| `AC-COMP-02-11` | La cotización devuelve una grilla parcial | El viajero la ve | Se muestran los orígenes que respondieron y cuáles no | `QA-PER-02` | Test de navegador, depende de COMP-06 |
| `AC-COMP-02-12` | El cliente cargado | Se inspeccionan los pedidos de red | Ninguno va a un host que no sea la app principal | `CON-01` | Test de navegador |
| `AC-COMP-02-13` | El usuario deja abierta «Novedades» | Llega una novedad | Aparece en 60 s sin recargar | `QA-PER-01` | Test de navegador |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| `refresco_novedades_segundos` | 60 | Cada cuánto se actualiza «Novedades» abierta | — (valor de prototipo) |
| `reintento_automatico` | no | El cliente solo reintenta cuando el usuario lo pide | — |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| La app principal sirve los archivos del cliente | `ADR-IT2-001`, `ADR-008` | La caché de borde y el Gateway se simulan en el mismo proceso; el cliente no sabe quién lo sirve |
| Identidad simulada hasta COMP-05 | `ADR-IT4-004` | El cliente ya envía la identidad en un solo lugar; cambiarla por el token es un cambio de ese lugar |

## Fuera de Alcance

* Consultas analíticas del equipo de datos (`REF-06`): no son del viajero.
* Cliente móvil, GPS e instalación: [SPEC-COMP-03](SPEC-COMP-03.md).
* Diseño visual fino, internacionalización, modo oscuro.

## Decisiones tomadas

1. **Verificación:** los criterios `AC-COMP-02-*` se prueban con Playwright (Chromium), como dependencia de desarrollo.
2. **Orden:** se implementa después de [SPEC-COMP-05](SPEC-COMP-05.md), así el cliente nace con login real.
3. **Identidad:** COMP-05 ya está implementado. El ingreso usa `POST /auth/alta` y `POST /auth/login` y guarda `token_acceso`.
4. **Vista principal:** además de `GET /itinerarios` y `GET /itinerarios/{id}`, Mis viajes muestra `GET /viajes` para las reservas que no están en un itinerario con membresía (las que incorpora el correo, con `itinerario_id` igual a la cuenta).
5. **Anuncios:** la sección «Anuncios» queda vacía. El listado lo agrega [SPEC-COMP-07](SPEC-COMP-07.md); el cliente no llama un endpoint que todavía no existe.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-23 | Versión inicial (`borrador`) | Pedido del usuario; falta de cliente detectada en la prueba de humo |
| 2026-11-23 | Sección «Contrato e Interfaces» y confirmación de `refresco_novedades_segundos` = 60 | Decisiones de revisión: ajuste a la plantilla y valor del prototipo fijado |
| 2026-11-23 | Paso a `aprobada` (`OK SPEC`) | Aprobación del usuario tras resolver las decisiones de revisión |
| 2026-11-23 | Decisiones: Playwright y orden de implementación | Respuesta del usuario |
| 2026-11-23 | Decisiones de implementación fijadas (`PLAN-COMP-02`) | Login real de COMP-05; `GET /viajes` en Mis viajes para las reservas sin membresía; anuncios de Booking vacíos hasta COMP-07 |
| 2026-11-23 | Criterios `AC-COMP-02-01` a `AC-COMP-02-13` en verde | `pytest tests/test_comp02_web.py`: 13 passed |
