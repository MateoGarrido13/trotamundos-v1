# SPEC-REF-04. Gestión manual

* **Estado:** borrador
* **Fecha:** 2026-11-22
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `REF-04`, `QA-SEG-02` |
| **ADRs** | `ADR-IT4-008`, `ADR-IT4-009`, `ADR-IT4-007` |
| **Elemento del paso 5** | [RONDA_1/ITERACION_4.md](../RONDA_1/ITERACION_4.md) Operaciones manuales de reserva, Módulo de control de acceso y auditoría, contrato `Reserva` |
| **Incremento (Slice)** | Slice 4 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

Los clientes deben poder agregar, actualizar o eliminar sus reservas existentes de forma manual dentro del panel.

Esas tres operaciones viven en el Orquestador de viajes, sobre el modelo polimórfico de [SPEC-REF-01](SPEC-REF-01.md). Registrar una actividad en un itinerario compartido es esta misma escritura, con autorización.

## Drivers que guían el cómo

* **`QA-SEG-02`:** antes de persistir, el sistema valida el permiso del usuario sobre ese itinerario. Con permiso, persiste la actividad, actualiza la vista para los demás miembros y registra la transacción. Sin permiso, no escribe la actividad y el cliente presenta la página «Error 401». La medida del listado pide que el 100 % de las solicitudes autorizadas se procesen, y que quienes no tengan permiso vean esa página. *(Origen: [RONDA_1/ITERACION_4.md](../RONDA_1/ITERACION_4.md): `REF-04` y `QA-SEG-02` son la misma operación de escritura)*

## Conceptos de diseño aceptados

* **Gestión manual en el Orquestador** (`ADR-IT4-008`): un único camino de escritura y de validación sobre el modelo polimórfico. Cada operación lleva una clave de operación generada por el cliente. Eliminar es una baja lógica. Una reserva editada a mano no la sobrescribe una novedad del proveedor: la novedad queda visible en «Novedades» para que el viajero decida. `ReservaActividad` es una clase más del Registro de tipos.
* **`lugar` en el contrato `Reserva`** (`ADR-IT4-009`): `lugar` forma parte del contrato `Reserva`. El viajero puede indicarlo en la carga manual. Analítica y demás consumidores lo leen del mismo contrato.
* **Autorización por itinerario y auditoría** (`ADR-IT4-007`): el Módulo de control de acceso está dentro del Orquestador. Cada operación declara el permiso que exige. Sin membresía y permiso explícitos, no hay operación. La auditoría de la decisión, permitida o denegada, se escribe en la misma transacción. El Orquestador responde acceso denegado y el cliente presenta la página «Error 401».

## Relaciones Permitidas

* **Recibe llamadas / mensajes de:** el balanceador, con la identidad del actor ya verificada por el gateway, para `agregarReserva`, `actualizarReserva(id)` y `eliminarReserva(id)`.
* **Invoca / publica hacia:** el Módulo de control de acceso, por la consulta interna `verificarPermiso(cuenta, itinerario, permisoRequerido)`. La Base de viajes, para la reserva, la membresía y el asiento de auditoría, en la misma transacción.
* **Restricciones de frontera:** la cotización no pasa por el control de acceso ni por la auditoría. El módulo de control de acceso no se consulta desde fuera del Orquestador. El cliente con GPS (`QA-USA-01`) no forma parte de esta spec. La página «Error 401» es la que nombra el escenario; el código que viaja por la red queda [sin especificar].

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen (ADR / Iteración) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `verificarPermiso(cuenta, itinerario, permisoRequerido)` | Interna al Orquestador | Cuenta, itinerario y permiso que la operación declara | Permiso concedido o denegado | Denegación por defecto | `ADR-IT4-007` |
| `agregarReserva` | Síncrono, desde el balanceador | Identidad del actor, clave de operación, reserva con `origen` manual y `lugar` | Reserva persistida, o acceso denegado | Sin permiso no se escribe. La misma clave no duplica | `ADR-IT4-008`, `ADR-IT4-009` |
| `actualizarReserva(id)` | Síncrono, desde el balanceador | Identidad del actor, clave de operación, id y cambios | Reserva actualizada, o acceso denegado | Igual que el alta | `ADR-IT4-008` |
| `eliminarReserva(id)` | Síncrono, desde el balanceador | Identidad del actor, clave de operación e id | Baja lógica, o acceso denegado | No es borrado físico | `ADR-IT4-008` |

Los roles que nombra el paso 5 son organizador y participante. Los permisos que una operación puede declarar son ver, registrar, modificar y administrar miembros.

## Reglas de Comportamiento

1. **Un solo camino:** agregar, actualizar y eliminar, vengan de la gestión manual, pasan por el Orquestador, por la validación del tipo y por el control de acceso. *(Origen: `ADR-IT4-008`, `ADR-IT4-007`)*
2. **Idempotencia:** un reintento con la misma clave de operación no duplica la reserva. *(Origen: `ADR-IT4-008`)*
3. **Baja lógica:** eliminar marca la baja y conserva el historial. *(Origen: `ADR-IT4-008`)*
4. **Precedencia:** si una novedad del proveedor llega sobre una reserva editada a mano, no la pisa. La novedad queda en «Novedades». *(Origen: `ADR-IT4-008`)*
5. **Auditoría atómica:** con permiso, la reserva y el asiento de auditoría se escriben en la misma transacción. Sin permiso, no se escribe la reserva y sí queda el asiento de la denegación. *(Origen: `ADR-IT4-007`)*
6. **Lugar:** la reserva manual puede traer `lugar`. Si no trae coordenadas, el contrato igual las tolera. *(Origen: `ADR-IT4-009`)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-REF-04-01` | El actor tiene permiso para registrar en ese itinerario | Llama a `agregarReserva` con clave de operación, `origen` manual y, si lo indica, `lugar` | La reserva queda persistida, agrupable por viaje, y el asiento de auditoría queda en la misma transacción | `REF-04`, `QA-SEG-02`, `ADR-IT4-008`, `ADR-IT4-007` | Test automático |
| `AC-REF-04-02` | La misma clave de operación ya creó esa reserva | El cliente reintenta `agregarReserva` | No aparece una segunda reserva | `REF-04`, `ADR-IT4-008` | Test automático |
| `AC-REF-04-03` | Existe una reserva manual | El actor con permiso llama a `eliminarReserva(id)` | La reserva queda en baja lógica y sigue disponible para el historial | `REF-04`, `ADR-IT4-008` | Test automático |
| `AC-REF-04-04` | Una reserva fue editada a mano y el proveedor publica una novedad de esa reserva | La novedad llega al Orquestador | La edición manual permanece y la novedad queda visible en «Novedades» | `REF-04`, `ADR-IT4-008` | Test automático |
| `AC-REF-04-05` | Un participante autenticado no tiene permiso para registrar en ese itinerario | Intenta registrar una actividad | No se persiste la actividad, queda el asiento de la denegación y el cliente presenta la página «Error 401» | `QA-SEG-02`, `ADR-IT4-007` | Test automático |
| `AC-REF-04-06` | El actor tiene permiso y registra una actividad (`ReservaActividad`) | La operación termina | Los demás miembros del itinerario ven la actualización | `QA-SEG-02` | Test automático |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| Retención de las claves de operación | [sin especificar] | Cuánto tiempo se guardan para reconocer un reintento | `ADR-IT4-008` |
| Eliminación definitiva de una baja lógica | [sin especificar] | Si una reserva dada de baja puede borrarse del almacenamiento | `ADR-IT4-008` |
| Código de estado que viaja por la red cuando falta permiso | [sin especificar] | El valor HTTP del acceso denegado. La página que ve el cliente es «Error 401» | `ADR-IT4-007` |
| Retención de la auditoría | [sin especificar] | Cuánto tiempo se conservan los asientos, incluidos los de denegación | `ADR-IT4-007` |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| Ninguna adicional | `ADR-IT4-007`, `ADR-IT4-008` | El permiso, la auditoría en la misma transacción, la clave de operación y la baja lógica se conservan. |

## Fuera de Alcance

* Geolocalización del cliente móvil (`QA-USA-01`, `ADR-IT5-003`).
* Cotización y su ausencia de control de acceso: esta spec no la redefine.
* El alta de cuenta y el token de sesión. Esta spec recibe la identidad ya verificada.
* Analítica de las cancelaciones: la baja lógica le deja el dato a [SPEC-REF-06](SPEC-REF-06.md).

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-22 | Versión inicial (`borrador`) | Creación a partir de `REF-04` y de los ADR aceptados que la iteración le asocia |
