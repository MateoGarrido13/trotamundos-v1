# SPEC-COMP-04. Correo real (Gmail API)

* **Estado:** aprobada
* **Fecha:** 2026-11-23
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `REF-02`, `QA-SEG-03*`, `CON-02` |
| **ADRs** | `ADR-007`, `ADR-IT3-003`, `ADR-IT3-006`, `ADR-IT3-007`, `ADR-IT3-010` |
| **Elemento del paso 5** | Adaptador de correo y Gestor de autorización: [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md) |
| **Incremento (Slice)** | Slice 3 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

[SPEC-REF-02](SPEC-REF-02.md) deja el correo detrás del puerto `ApiCorreo` y lo prueba con un mock (`CON-02`). Esta spec agrega la implementación real contra la **Gmail API**: el titular autoriza por OAuth, el sistema sondea su buzón con ese permiso y entrega los mensajes al camino de `REF-02`. No cambia el Adaptador de correo, el Parseo aislado, el filtro ni el Orquestador.

## Drivers que guían el cómo

* **`CON-02`:** la integración con el correo es por API. *(Origen: LISTADO_DRIVERS_RONDA_1)*
* **`QA-SEG-03*`:** el sistema accede al correo solo con la autorización del titular. El 100 % de los usuarios autorizados ven sus reservas reflejadas. *(Origen: LISTADO_DRIVERS_RONDA_1)*

## Conceptos de diseño aceptados

* **Capa Anti-Corrupción (ACL)** (`ADR-007`): la clase nueva traduce el contrato de Gmail al `CorreoCrudo` que ya espera el adaptador. Es el único módulo que conoce Gmail.
* **Acceso controlado al correo del titular** (`ADR-IT3-006`): el token solo se guarda cifrado, solo lo usa el Adaptador de correo, vive poco y se revoca a pedido. El Gestor de autorización le pasa el token por llamada en memoria.
* **Parseo aislado** (`ADR-IT3-007`): el parseo corre como proceso separado, sin token y sin acceso a la base. La implementación real no cambia eso.
* **Retry con identificador único** (`ADR-IT3-003`): el identificador es el `Message-ID`, o el hash del contenido si falta.
* **Nodos propios para los adaptadores de entrada** (`ADR-IT3-010`).

## Relaciones Permitidas

* **Recibe llamadas de:** el Adaptador de correo, a través del puerto `ApiCorreo.leer_mensajes(token, desde)`. El viajero, por el cliente, para autorizar y revocar.
* **Invoca:** la Gmail API, por HTTPS/REST, y el servicio de OAuth de Google para el consentimiento.
* **Restricciones de frontera:** nada fuera de la clase nueva importa el cliente de Google. El token no llega al Parseo, al Filtro, al Orquestador ni a un log. El permiso que se pide es de **solo lectura** (`gmail.readonly`).

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `iniciarAutorizacion()` | Cliente hacia la app, luego redirección a Google | Identidad del titular | URL de consentimiento de Google, con un `state` de un solo uso ligado al titular | — | `ADR-IT3-006` |
| `completarAutorizacion(code, state)` | Google redirige a la app | Código y `state` | El token de acceso queda guardado cifrado en el Gestor; el titular queda autorizado | `state` inválido, usado o vencido: se rechaza sin guardar nada | `ADR-IT3-006` |
| `leer_mensajes(token, desde)` | Adaptador de correo hacia Gmail | Token y fecha de inicio de la ventana | Lista de `CorreoCrudo` (cuerpo, remitente, fecha, `Message-ID`) | Token inválido o vencido: `TokenInvalido`. Cualquier otro fallo: `ErrorApiCorreo`. El sondeo falla solo para ese titular | `REF-02`, `ADR-IT3-003` |
| `revocar()` | Cliente hacia el Gestor y Gmail | Identidad del titular | Token borrado y revocado en Google | Si Google no responde, el token local igual se borra | `ADR-IT3-006` |

## Reglas de Comportamiento

1. **Solo lectura:** el único alcance que se solicita es `gmail.readonly`. *(Origen: `ADR-IT3-006`)*
2. **Sin autorización no hay lectura:** sin token vigente el sondeo no llama a Gmail. *(Origen: `REF-02`)*
3. **Token con vida corta y sin renovación:** vence como fija `REF-02`; no se guarda un token de renovación. El titular vuelve a autorizar. *(Origen: `ADR-IT3-006`)*
4. **Ventana:** se piden los mensajes de la ventana de sondeo de `REF-02` (7 días), de a páginas, hasta un máximo de mensajes por sondeo. *(Origen: `REF-02`)*
5. **Identificador:** `Message-ID` del encabezado; si falta, el hash del contenido. *(Origen: `ADR-IT3-003`)*
6. **Cuerpo:** se entrega el texto del mensaje sin adjuntos; el HTML se reduce a texto antes de entregarlo. *(Origen: `ADR-IT3-007`)*
7. **Secretos:** `client_id` y `client_secret` salen del entorno (`TROTA_GMAIL_CLIENT_ID`, `TROTA_GMAIL_CLIENT_SECRET`). Nunca se escriben en un log ni en la base. *(Origen: `ADR-IT3-006`)*
8. **Sin credenciales, el mock:** si el entorno no tiene credenciales, la app usa `MockApiCorreo` y lo avisa en el log. *(Origen: COMP-01)*
9. **Cota:** cada llamada a Gmail tiene una cota de espera. Al vencer es `ErrorApiCorreo` y no se reintenta dentro del sondeo; lo reintenta el sondeo siguiente. *(Origen: `ADR-IT2-003`)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-COMP-04-01` | Un titular sin autorización | Inicia la autorización | Recibe una URL de Google con alcance `gmail.readonly` y un `state` de un solo uso | `QA-SEG-03*` | Test automático con servidor de Google simulado |
| `AC-COMP-04-02` | Un `state` ya usado | Se completa la autorización de nuevo | Se rechaza y no se guarda token | `QA-SEG-03*` | Test automático |
| `AC-COMP-04-03` | Un titular autorizado y mensajes de viaje en su buzón simulado | Corre el sondeo | Los mensajes llegan como `CorreoCrudo` al camino de `REF-02` y las reservas aparecen en el itinerario | `REF-02` | Test automático con Gmail simulado |
| `AC-COMP-04-04` | Gmail responde 401 | Corre el sondeo | Se informa `TokenInvalido` y el titular queda sin lectura hasta autorizar de nuevo | `QA-SEG-03*` | Test automático |
| `AC-COMP-04-05` | Gmail no responde | Corre el sondeo de varios titulares | Falla solo el de ese titular | `REF-02` | Test automático |
| `AC-COMP-04-06` | Un titular que revoca | Corre el sondeo | No se llama a Gmail y el token se borró | `QA-SEG-03*` | Test automático |
| `AC-COMP-04-07` | Cualquier ejecución | Se revisan los logs y la base | El token no figura en claro en ningún lado | `ADR-IT3-006` | Test automático |
| `AC-COMP-04-08` | Mensajes sin `Message-ID` | Corre el sondeo dos veces | Se identifican por hash y no se duplican | `ADR-IT3-003` | Test automático |
| `AC-COMP-04-09` | Un mensaje con HTML y adjuntos | Corre el sondeo | Se entrega solo el texto | `ADR-IT3-007` | Test automático |
| `AC-COMP-04-10` | Una cuenta de Google real de prueba | Se autoriza y llega un correo de reserva | La reserva aparece en el itinerario | `QA-SEG-03*` | Demo manual con credenciales reales |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| `max_mensajes_por_sondeo` | 100 | Tope por titular y sondeo | — (valor de prototipo) |
| `cota_llamada_gmail_segundos` | 10 | Espera máxima por llamada | `ADR-IT2-003` |
| `redireccion_oauth` | `http://localhost:8000/correo/oauth/callback` | Dónde vuelve Google | — |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| Sondeo en el mismo proceso que la API | `ADR-IT3-010` | Es una tarea separada; solo cambia el despliegue |
| Google simulado en los tests automáticos | `CON-02` | La clase real se prueba con respuestas grabadas del contrato de Gmail; la prueba contra Google real es manual (AC-10) |

## Fuera de Alcance

* Otros proveedores de correo (Microsoft Graph, IMAP).
* Renovación automática del token (`REF-02` fija que vence).
* Verificación de la app ante Google para uso público.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-23 | Versión inicial (`borrador`) | Pedido del usuario; proveedor Gmail elegido |
| 2026-11-23 | Paso a `aprobada` (`OK SPEC`) | Aprobación del usuario tras resolver las decisiones de revisión |
