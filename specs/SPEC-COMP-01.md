# SPEC-COMP-01. Sistema ejecutable de punta a punta

* **Estado:** implementada
* **Fecha:** 2026-11-23
* **Autores:** [sin especificar]

> **Nomenclatura.** `COMP-01` es un código propio de las specs de composición del prototipo. No es un driver ni un `REF`: esta spec no introduce un requerimiento, **cierra huecos de composición** de `REF-01` a `REF-07` hallados en la prueba de humo. La lista de drivers sigue cerrada.

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `REF-01`, `REF-04`, `REF-05`, `REF-06`, `REF-07`, `CON-01` |
| **ADRs** | `ADR-IT3-001`, `ADR-IT3-002`, `ADR-IT3-003`, `ADR-IT4-007`, `ADR-IT4-008`, `ADR-IT4-010`, `ADR-IT5-001` |
| **Elemento del paso 5** | Broker y sus consumidores (RONDA_1/ITERACION_3.md); Orquestador de viajes y control de acceso (ITERACION_4.md); Proyector analítico (ITERACION_5.md) |
| **Incremento (Slice)** | Transversal a los Slices 3, 4 y 5 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

Que `uvicorn trotamundos.app:app` levante **un solo sistema completo**: que las operaciones que dejan un mensaje en una cola lo vean procesado, que todos los endpoints de `REF-01` a `REF-07` estén expuestos, y que un viajero pueda empezar a usarlo sin sembrar la base a mano. No cambia ninguna decisión de arquitectura: instancia lo que los ADRs ya fijaron.

## Hallazgos que origina

| Id | Hallazgo (prueba de humo del 2026-11-23) |
| :--- | :--- |
| H1 | Ningún proceso consume las colas del Broker fuera de los tests |
| H2 | La app principal no monta el asistente, la analítica, `POST /correo/autorizacion` ni `POST /agencia/{agencia}/avisos` |
| H3 | No hay endpoint para crear un viaje, un itinerario ni una membresía |
| H4 | `tipo` se serializa distinto al crear (`hotel`) y al listar (`ReservaHotel`) |
| H5 | Las bases de desarrollo y de los tests son las mismas |

## Drivers que guían el cómo

* **`CON-01`:** los clientes web y móvil hablan con un único punto de entrada HTTP. *(Origen: [PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) §2)*
* **`REF-05` y `REF-06`:** el caso «en trámite» solo avanza si el Adaptador de agencia consume la cola, y la analítica solo existe si el Proyector consume la quinta cola. *(Origen: [SPEC-REF-05](SPEC-REF-05.md), [SPEC-REF-06](SPEC-REF-06.md))*

## Conceptos de diseño aceptados

* **Broker con colas acotadas y consumidores propios** (`ADR-IT3-001`, `ADR-IT3-002`): cada cola tiene su consumidor. Un consumidor que falla no detiene a los demás, y los reintentos y la cola de mensajes muertos se mantienen.
* **Autorización y auditoría** (`ADR-IT4-007`) **y clave de operación** (`ADR-IT4-008`): toda operación nueva de esta spec declara su permiso, deja su asiento en la misma transacción y acepta clave de operación.
* **Aislamiento de la analítica** (`ADR-IT5-001`): la Base analítica no se lee ni se escribe desde el camino del viajero. El montaje conjunto no rompe esa frontera.

## Relaciones Permitidas

* **Recibe llamadas de:** los clientes web y móvil, por HTTP.
* **Invoca:** los módulos ya existentes de `REF-01` a `REF-07`, a través de `composicion.py`. Es el único lugar donde se conectan.
* **Restricciones de frontera:** el test de arquitectura (`tests/test_arquitectura.py`) sigue vigente. Montar todo en una app **no** autoriza a un módulo a importar a otro. El asistente sigue sin importar bases ni al Orquestador, y la analítica sigue separada de la persistencia de viajes.

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `crearViaje(nombre, itinerario_id?)` (`POST /viajes`) | Síncrono, cliente hacia el Orquestador | Identidad, clave de operación, nombre del viaje y, opcional, itinerario existente | Viaje creado, con un identificador que **asigna el sistema** y el nombre que dio quien lo crea (hasta 100 caracteres). Si no se indica itinerario, se crea uno nuevo y el actor queda como **organizador** | Sin permiso `registrar` sobre el itinerario indicado: acceso denegado con asiento. Itinerario inexistente o ajeno: acceso denegado, sin revelar cuál de los dos es | `ADR-IT4-007`, `ADR-IT4-008` |
| `agregarMiembro(itinerario, cuenta, rol)` | Síncrono | Identidad, clave de operación, cuenta y rol | Membresía guardada | Exige `administrar_miembros`: solo el organizador. Rol fuera de la matriz: 422 | `ADR-IT4-007` |
| `quitarMiembro(itinerario, cuenta)` | Síncrono | Idem | Membresía eliminada | No se puede quitar al último organizador: 409 | `ADR-IT4-007` |
| `listarItinerarios()` | Síncrono, solo lectura | Identidad | Los itinerarios en los que la cuenta es miembro, con su rol. Lo necesita cualquier cliente para empezar | Sin membresías: lista vacía | `ADR-IT4-007` |
| `listarMiembros(itinerario)` | Síncrono, solo lectura | Identidad | Cuentas y roles | Sin permiso `ver`: acceso denegado | `ADR-IT4-007` |
| Sondeo de correo | Interno, ciclo de vida de la app | Configuración | El `ProgramadorSondeo` de `REF-02` arranca con el mock de `ApiCorreo` hasta que exista el adaptador real (spec propia). Sin tokens vigentes no lee nada | Falla de un sondeo no detiene a los demás | `REF-02` |
| Arranque de consumidores | Interno, ciclo de vida de la app | Configuración | Un consumidor por cola con consumidor posible: novedades, correo, casos de ayuda y eventos analíticos. La de notificaciones queda sin consumidor hasta que exista la spec de `QA-INT-02` | Un consumidor que falla se reinicia con espera creciente y no detiene a los demás | `ADR-IT3-002` |
| Montaje de routers | HTTP | — | `/asistente/*`, `/analitica/informe`, `/correo/autorizacion`, `/agencia/{agencia}/avisos` quedan en la misma app | Ver reglas 4 y 5 | `REF-05`, `REF-06`, `REF-07` |

## Reglas de Comportamiento

1. **Consumo continuo:** al arrancar, la app lanza un consumidor por cada cola y los detiene en orden al cerrar. El consumidor sondea su cola: si está vacía, espera un intervalo corto y reintenta (`Broker.procesar_uno` devuelve `VACIA` sin bloquear). *(Origen: `ADR-IT3-001`)*
2. **Aislamiento de consumidores:** el Broker ya reintenta un handler que falla y manda el mensaje a muertos al agotar los reintentos (`ADR-IT3-002`, `ADR-IT3-003`). Esta regla cubre lo que queda fuera del handler, por ejemplo la base caída al tomar el mensaje: el consumidor registra el error, se reinicia con espera creciente y los demás siguen. *(Origen: `ADR-IT3-002`)*
3. **Una app, un `create_app`:** `trotamundos.app:app` expone los endpoints de `REF-01` a `REF-07`. Las sub-apps existentes se conservan solo para los tests de cada módulo. *(Origen: `CON-01`)*
4. **Analítica no bloquea:** con la Base analítica caída, la app principal arranca y atiende. Solo `/analitica/informe` responde 503. *(Origen: `ADR-IT5-001`, `SPEC-REF-06`)*
5. **Asistente con motor simulado:** el montaje usa `MotorSimulado` por configuración. Cambiar de motor es otro adaptador. *(Origen: `SPEC-REF-07`)*
6. **Alta de viaje:** crear un viaje sin itinerario crea un itinerario propio y hace organizador al actor, con su asiento de auditoría, en la misma transacción. *(Origen: `ADR-IT4-007`)*
7. **Membresías:** solo el organizador agrega y quita miembros, y cualquier miembro los lista. Siempre queda al menos un organizador. La cuenta indicada **no se valida** contra ninguna base de cuentas: eso es de la spec de identidad (Slice 1). *(Origen: matriz de [SPEC-REF-04](SPEC-REF-04.md))*
8. **`tipo` uniforme:** toda respuesta de la API serializa `tipo` con el código del tipo registrado (`hotel`, `auto`, `vuelo`, `tren`, `autobus`, `actividad`), nunca con el nombre de la clase. *(Origen: `REF-01`, registro de tipos)*
9. **Bases separadas:** la configuración de desarrollo y la de tests usan bases distintas. Los tests nunca vacían la base de desarrollo. *(Origen: higiene del prototipo)*
10. **Datos de demo:** `scripts/sembrar_demo.py` queda como utilitario, sin importancia para la arquitectura. *(Origen: prototipo)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-COMP-01-01` | La app principal arrancó con todo montado | Un viajero reporta un caso y la agencia mock lo acepta | El caso pasa de «en trámite» a «abierto» sin que el test invoque ningún `procesar_uno` | `REF-05`, `ADR-IT3-001` | Test automático |
| `AC-COMP-01-02` | La app arrancó | Se agrega una reserva | El Proyector la suma a los contadores y el informe la refleja | `REF-06` | Test automático |
| `AC-COMP-01-03` | Falla una operación del consumidor fuera del handler (por ejemplo, la lectura de la cola) | Llega el siguiente mensaje | El consumidor se reinicia con la espera creciente, los otros cuatro siguen vivos y el mensaje se procesa | `ADR-IT3-002` | Test automático con falla inyectada |
| `AC-COMP-01-04` | La app arrancó | Se consulta `/openapi.json` | Figuran los endpoints del asistente, la analítica, la autorización de correo y los avisos de agencia | `CON-01` | Test automático |
| `AC-COMP-01-05` | La Base analítica está caída | Se arranca la app y se agrega una reserva | La app atiende, la reserva se guarda e `informe` responde 503 | `ADR-IT5-001` | Test automático |
| `AC-COMP-01-06` | Un viajero sin itinerarios | Crea un viaje sin indicar itinerario | Queda creado, el viajero es organizador y existe el asiento de auditoría | `ADR-IT4-007` | Test automático |
| `AC-COMP-01-07` | Un participante | Intenta agregar un miembro | Acceso denegado, con asiento | `ADR-IT4-007` | Test automático |
| `AC-COMP-01-08` | Un itinerario con un solo organizador | Se intenta quitarlo | 409 y la membresía no cambia | `ADR-IT4-007` | Test automático |
| `AC-COMP-01-09` | Una reserva creada | Se la lee al crear, al listar y en el itinerario | `tipo` es el mismo código en las tres respuestas | `REF-01` | Test automático |
| `AC-COMP-01-10` | Se corre la suite completa | Termina | Las bases de desarrollo conservan sus datos | Higiene | Test automático |
| `AC-COMP-01-11` | Una clave de operación repetida en `crearViaje` | Se reenvía la misma petición | Devuelve el primer resultado sin crear un segundo viaje | `ADR-IT4-008` | Test automático |
| `AC-COMP-01-13` | Un viajero ajeno a un itinerario | Crea un viaje indicando ese itinerario | Acceso denegado, y la respuesta es idéntica a la de un itinerario inexistente | `ADR-IT4-007` | Test automático |
| `AC-COMP-01-12` | La app cierra | Se detiene el ciclo de vida | Los consumidores terminan sin dejar tareas colgadas | `ADR-IT3-001` | Test automático |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| `espera_reinicio_consumidor` | 1, 2, 4 s, tope 30 s | Espera antes de reiniciar un consumidor caído. Valor de prototipo propio, no lo fija un ADR | — |
| `intervalo_sondeo_cola` | 0,2 s | Espera de un consumidor ante una cola vacía. Valor de prototipo propio | — |
| `bases_desarrollo` | puertos 5433/5434/5435, base `trotamundos_dev` | Datos de demo | — |
| `bases_tests` | mismos puertos, base `trotamundos_test` | Datos de test | — |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| Un solo proceso ejecuta los consumidores y la API | `ADR-IT3-001` | El Broker ya es en proceso. Los consumidores siguen siendo tareas separadas, con su propio ciclo de vida |
| La identidad sigue siendo el header `X-Viajero-Id` | Slice 1 sin spec | El login y el token firmado quedan para su propia spec |

## Fuera de Alcance

* Validar que una cuenta exista, login, emisión y validación de token firmado, y registro regional (Slice 1).
* Cotización, novedades de Booking y notificaciones por `ICanal`.
* Cliente web, cliente móvil y correo real: cada uno con su spec.

## Decisiones tomadas

1. **Nomenclatura:** el código es `COMP-01`, para distinguirla de los `REF`.
2. **Membresías:** la precarga que `REF-04` trataba como dato de prueba pasa a ser operación real (reglas 6 y 7). `REF-04` sigue valiendo: la matriz de permisos no cambia.
3. **Base de desarrollo:** se agrega `trotamundos_dev` separada de la de tests. Es necesaria: sin ella `pytest` borra los datos de demo (H5), y el alta de viajes por API haría que esa pérdida fuera visible para el usuario.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-23 | Versión inicial (`borrador`) | Hallazgos H1 a H5 de la prueba de humo |
| 2026-11-23 | Renombrada de `SPEC-REF-08` a `SPEC-COMP-01`; decisiones 1 a 3 cerradas | Respuesta del usuario |
| 2026-11-23 | Se agregan `listarItinerarios` (`GET /itinerarios`) y el nombre del viaje (`viaje.nombre`). Se aclara que la cola de notificaciones no tiene consumidor. La spec queda implementada: 13 de 13 criterios en verde | Lo necesita cualquier cliente para empezar; se descubrió al implementar |
