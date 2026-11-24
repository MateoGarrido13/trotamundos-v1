# SPEC-COMP-05. Identidad regional y seguridad en el borde

* **Estado:** aprobada
* **Fecha:** 2026-11-23
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `QA-ESC-01`, `QA-SEG-01`, `CON-01` |
| **ADRs** | `ADR-IT4-001`, `ADR-IT4-002`, `ADR-IT4-003`, `ADR-IT4-004`, `ADR-IT4-005`, `ADR-IT4-006`, `ADR-IT4-011`, `ADR-008` |
| **Elemento del paso 5** | Cuentas, alta y autenticación; Seguridad del login: [RONDA_1/ITERACION_4.md](../RONDA_1/ITERACION_4.md) |
| **Incremento (Slice)** | Slice 1 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

Hoy la identidad es el header `X-Viajero-Id`, que cualquiera puede inventar. Esta spec instala la identidad real: alta de cuenta en su región con unicidad acotada (`QA-ESC-01`), sesión con token firmado de vida corta validado en el API Gateway sin llamar a ninguna región (`ADR-IT4-004`), y contención de la ráfaga de 50 pedidos de recuperación de contraseña (`QA-SEG-01`). El Gateway pasa al Orquestador la identidad ya verificada.

## Drivers que guían el cómo

* **`QA-ESC-01`:** el 100 % de los registros se procesan (0 rechazos por saturación o timeout), la confirmación demora menos de 2 s desde cualquier continente y el nuevo usuario puede iniciar sesión de inmediato. *(Origen: LISTADO_DRIVERS_RONDA_1)*
* **`QA-SEG-01`:** el 100 % de los accesos no autorizados se rechaza y el login de los usuarios legítimos sigue disponible ante 50 pedidos simultáneos de recuperación. *(Origen: LISTADO_DRIVERS_RONDA_1)*

## Conceptos de diseño aceptados

* **Partición geográfica de las cuentas por región de origen** (`ADR-IT4-001`): el viajero escribe en su región. El identificador de cuenta lo genera la región, con el código de región como prefijo, sin coordinación entre regiones, y viaja en el token.
* **Módulo de registro y autenticación en nodos propios, con Base de cuentas propia** (`ADR-IT4-002`): nodos idénticos y sin estado; la Base de viajes no guarda cuentas, perfiles ni sesiones.
* **Enrutamiento por proximidad y unicidad acotada y reconciliada** (`ADR-IT4-003`): el alta consulta a las otras regiones en paralelo, por huella del correo y con una cota. Si una región no responde, el alta no se rechaza: la cuenta queda «unicidad pendiente» para reconciliar.
* **Sesión con token firmado de vida corta, validado en el API Gateway** (`ADR-IT4-004`): el Gateway valida la firma con las claves públicas de las regiones, sin llamar a ninguna. Cerrar sesión o completar una recuperación revoca los tokens de renovación. Los de acceso vencen solos.
* **Limitación de tasa en el Gateway y recuperación aislada** (`ADR-IT4-005`): cuenta pedidos por endpoint y por origen; lo que excede responde «demasiados pedidos» sin llegar al servicio. La recuperación tiene un cupo y recursos propios.
* **Recuperación con token de un solo uso, respuesta uniforme, un pedido vigente por cuenta y aviso al titular** (`ADR-IT4-006`): decidido con una actualización atómica en la Base de cuentas.
* **Revocación efectiva desde la operación siguiente** (`ADR-IT4-011`): ya cubierta por el control de acceso de [SPEC-REF-04](SPEC-REF-04.md).

## Relaciones Permitidas

* **Recibe llamadas de:** los clientes, por el Gateway: alta, login, renovación, cierre de sesión y recuperación.
* **Invoca:** su Base de cuentas y su pasiva, el módulo de otras regiones (solo la consulta de unicidad por huella), y la cola de notificaciones para el correo de recuperación y el aviso al titular.
* **Restricciones de frontera:** el Orquestador de viajes no lee ni escribe en ninguna Base de cuentas. Las regiones no se sincronizan entre sí; una cuenta vive en una sola. El Gateway no llama a una región para validar un token. El correo no viaja en claro entre regiones.

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `IRegistroUsuario.alta` | Cliente hacia el Gateway y el módulo de su región | Correo, contraseña, región | Cuenta con identificador `<región>-<id>` y la sesión inicial (token de acceso y de renovación) en la misma respuesta | Correo ya registrado en la región: 409. Región remota sin respuesta en la cota: el alta sigue con «unicidad pendiente». Menos de 2 s | `ADR-IT4-001`, `ADR-IT4-003` |
| `IRegistroUsuario.login` | Idem | Correo y contraseña | Sesión | Credencial inválida: 401. Límite de tasa: 429 | `ADR-IT4-004`, `ADR-IT4-005` |
| `IRegistroUsuario.renovar` | Idem | Token de renovación vigente | Nuevo token de acceso | Revocado o vencido: 401 | `ADR-IT4-004` |
| `IRegistroUsuario.cerrarSesion` | Idem | Token de renovación | Tokens de renovación revocados | — | `ADR-IT4-004` |
| `consultarUnicidad(huella)` | Entre regiones, con cota | Huella del correo | Existe o no | Sin respuesta en la cota: se omite | `ADR-IT4-003` |
| `solicitarRecuperacion(correo)` | Cliente hacia el Gateway | Correo | Respuesta uniforme exista o no la cuenta | Límite de tasa: 429 sin llegar al servicio | `ADR-IT4-005`, `ADR-IT4-006` |
| `completarRecuperacion(token, contraseña)` | Idem | Token de un solo uso y nueva contraseña | Contraseña cambiada y tokens de renovación revocados | Token usado, vencido o inexistente: 400 | `ADR-IT4-006` |
| Validación del token | API Gateway, local | Token de acceso | Identidad verificada con su región, que el Gateway pasa al Core en `X-Viajero-Id` | Firma inválida o vencido: 401 sin llamar a ninguna región | `ADR-IT4-004` |

## Reglas de Comportamiento

1. **Identidad con región:** el identificador de cuenta empieza por el código de región (`amer`, `emea`, `apac`). *(Origen: `ADR-IT4-001`)*
2. **Alta inmediata:** la respuesta del alta trae la sesión; el usuario no hace un login aparte. *(Origen: `ADR-IT4-004`, `QA-ESC-01`)*
3. **Unicidad acotada:** la consulta a las otras dos regiones es en paralelo y con cota. Una región que no responde marca la cuenta «unicidad pendiente»; un proceso de reconciliación la resuelve después. *(Origen: `ADR-IT4-003`)*
4. **Contraseñas:** se guardan con hash con sal. Nunca se devuelven ni se registran. *(Origen: `ADR-IT4-004`)*
5. **Token de acceso:** firmado, de vida corta. El Gateway lo valida con la clave pública sin llamar a nadie; el Orquestador solo recibe identidad ya verificada. Un pedido que llega al Core con un `X-Viajero-Id` sin pasar por el Gateway se rechaza. *(Origen: `ADR-IT4-004`)*
6. **Tasa:** el Gateway cuenta por endpoint y por origen, con un cupo propio para recuperación; lo excedido responde 429 sin pasar al servicio y deja el evento registrado. *(Origen: `ADR-IT4-005`)*
7. **Recuperación:** responde igual exista o no la cuenta. Admite un solo pedido vigente por cuenta: ante 50 pedidos simultáneos pasa uno. El token es aleatorio, de un solo uso, con vencimiento, guardado como hash y enviado solo al correo registrado. *(Origen: `ADR-IT4-006`)*
8. **Aviso al titular:** al superarse el cupo por cuenta se publica un aviso por ventana en la cola de notificaciones. *(Origen: `ADR-IT4-006`)*
9. **Separación de login y recuperación:** saturar la recuperación no degrada el login. *(Origen: `ADR-IT4-005`)*
10. **Región caída:** los usuarios con token vigente siguen siendo atendidos. *(Origen: `ADR-IT4-004`)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-COMP-05-01` | Las tres regiones | Se dan de alta cuentas en cada una | Cada cuenta vive en una sola región y su identificador lleva el prefijo | `ADR-IT4-001` | Test automático |
| `AC-COMP-05-02` | Un alta | Termina | La respuesta incluye la sesión y el usuario opera sin login aparte | `ADR-IT4-004` | Test automático |
| `AC-COMP-05-03` | Una región remota con demora mayor que la cota | Se hace un alta | El alta no se rechaza y la cuenta queda «unicidad pendiente» | `ADR-IT4-003` | Test automático con demora inyectada |
| `AC-COMP-05-04` | Un correo ya registrado en otra región | Se da de alta de nuevo | Se detecta por huella y se rechaza | `ADR-IT4-003` | Test automático |
| `AC-COMP-05-05` | Un token válido | Llega al Gateway con la región de la cuenta caída | El Gateway lo valida sin llamar a ninguna región | `ADR-IT4-004` | Test automático con región detenida |
| `AC-COMP-05-06` | Un token con la firma alterada o vencido | Llega al Gateway | 401 y el pedido no llega al Core | `ADR-IT4-004` | Test automático |
| `AC-COMP-05-07` | Un pedido directo al Core con `X-Viajero-Id` y sin pasar por el Gateway | Llega | Se rechaza | `ADR-IT4-004` | Test automático |
| `AC-COMP-05-08` | 50 pedidos simultáneos de recuperación contra el mismo endpoint | Se envían | Pasa uno como máximo, el resto recibe 429 o la respuesta uniforme, ningún acceso no autorizado prospera y el login sigue disponible | `QA-SEG-01` | Test automático concurrente |
| `AC-COMP-05-09` | Dos cuentas, una existente y otra no | Se pide la recuperación | La respuesta es idéntica en contenido y forma | `ADR-IT4-006` | Test automático |
| `AC-COMP-05-10` | Un token de recuperación | Se usa dos veces | El segundo uso falla | `ADR-IT4-006` | Test automático |
| `AC-COMP-05-11` | Una recuperación completada | Se usa un token de renovación anterior | Falla | `ADR-IT4-004` | Test automático |
| `AC-COMP-05-12` | Se supera el cupo de una cuenta | Pasa la ventana | Se publica un solo aviso al titular en la cola de notificaciones | `ADR-IT4-006` | Test automático |
| `AC-COMP-05-13` | 1.000 altas concurrentes repartidas en las tres regiones | Se envían | 0 rechazos por saturación y confirmación en menos de 2 s en cada una | `QA-ESC-01` | Prueba de carga |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| `vida_token_acceso` | 15 minutos | Vencimiento del token de acceso | `ADR-IT4-004` |
| `vida_token_renovacion` | 7 días | Vencimiento del token de renovación | `ADR-IT4-004` |
| `cota_unicidad_ms` | 300 | Espera máxima por región remota | `ADR-IT4-003` |
| `cupo_login` / `cupo_recuperacion` | 10 / 3 por minuto y origen | Límite de tasa | `ADR-IT4-005` |
| `cupo_recuperacion_por_cuenta` | 3 por hora | Cuándo se avisa al titular | `ADR-IT4-006` |
| `vida_token_recuperacion` | 30 minutos | Vencimiento del token de recuperación | `ADR-IT4-006` |
| `regiones` | `amer`, `emea`, `apac` | Regiones simuladas | `ADR-IT4-001` |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| Tres regiones simuladas con tres pares de bases PostgreSQL en el mismo entorno (6 bases más) | `ADR-IT4-001` | Se conservan la partición, las fronteras y el commit en dos fases dentro de cada región |
| El Gateway es un middleware de la app principal | `ADR-008`, `ADR-IT4-004` | Valida el token localmente y quita todo `X-Viajero-Id` que venga del cliente |
| Clave de firma compartida en el entorno o par de claves local | `ADR-IT4-004` | La validación sigue siendo local; el prototipo no rota claves |
| Correo de recuperación por el canal Email simulado | `ADR-IT4-006` | Usa la cola de notificaciones y `ICanal` ([SPEC-COMP-08](SPEC-COMP-08.md)) |

## Fuera de Alcance

* Doble factor, bloqueo de cuenta (`ADR-IT4-013`, rechazado), base de cuentas global con confirmación síncrona (`ADR-IT4-012`, rechazado).
* Caché de borde y su cota (ver [SPEC-COMP-06](SPEC-COMP-06.md)).
* Reconciliación fina de cuentas duplicadas más allá de marcar «unicidad pendiente».

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-23 | Versión inicial (`borrador`) | Pedido del usuario; Slice 1 sin spec |
| 2026-11-23 | Paso a `aprobada` (`OK SPEC`) | Aprobación del usuario tras resolver las decisiones de revisión |
