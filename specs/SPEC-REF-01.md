# SPEC-REF-01. Ciclo de vida del viaje

* **Estado:** aprobada
* **Fecha:** 2026-11-23
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `REF-01`, `CON-01`, `QA-EVO-01`, `QA-DIS-01` |
| **ADRs** | `ADR-001`, `ADR-IT3-005`, `ADR-IT2-004`, `ADR-IT2-005` |
| **Elemento del paso 5** | [RONDA_1/ITERACION_1.md](../RONDA_1/ITERACION_1.md) Orquestador de viajes y Base de datos principal; [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md) `Reserva` y Registro de tipos; [RONDA_1/ITERACION_2.md](../RONDA_1/ITERACION_2.md) Base primaria y Base pasiva |
| **Incremento (Slice)** | Slice 4 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

Los elementos en el panel de control deben poder agruparse por viaje y, una vez que el viaje se completa, archivarse o eliminarse automáticamente de la vista principal.

El Orquestador de viajes agrupa las reservas por viaje y, cuando el viaje se completa, lo archiva o lo saca de la vista principal. La Base primaria persiste los viajes activos y el archivo de viajes completados.

## Drivers que guían el cómo

* **`CON-01`:** la consulta del panel se pide desde el cliente web y desde el cliente móvil. *(Origen: [RONDA_1/ITERACION_1.md](../RONDA_1/ITERACION_1.md), secuencia «Consulta del panel»)*
* **`QA-EVO-01`:** un medio de transporte nuevo queda agrupado en el viaje junto con las reservas ya existentes, sin modificar la agrupación. La medida del listado es un plazo de 3 meses de esfuerzo de desarrollo. *(Origen: [RONDA_1/ITERACION_3.md](../RONDA_1/ITERACION_3.md))*
* **`QA-DIS-01`:** entra solo como persistencia del viaje y del archivo. La copia pasiva queda igual que la primaria en cada escritura confirmada, y si la primaria deja de atender, el Orquestador conmuta a la pasiva. El estímulo de caída de un nodo de cotización y el Ping/Echo quedan fuera de esta spec. *(Origen: [RONDA_1/ITERACION_4.md](../RONDA_1/ITERACION_4.md), asignación de la Base de viajes a `REF-01` y `QA-DIS-01`; [ADR-IT2-004](../RONDA_1/ADRs/ITERACION_2/ADR-IT2-004.md), [ADR-IT2-005](../RONDA_1/ADRs/ITERACION_2/ADR-IT2-005.md))*

## Conceptos de diseño aceptados

* **N-Tier** (`ADR-001`): el Orquestador, en la capa de lógica de negocio, agrupa las reservas por viaje y archiva o saca de la vista principal el viaje completado. La presentación queda en los clientes y los datos en la base.
* **Polymorphism con Registro de tipos por configuration-time binding** (`ADR-IT3-005`): la agrupación trabaja contra `Reserva` (identificador, viaje, fechas, estado y resumen) y no conoce los tipos concretos. Un medio nuevo es una clase más que extiende `Reserva` y se registra, sin cambios en la agrupación.
* **Transactions, commit en dos fases** (`ADR-IT2-004`): el Orquestador escribe en la Base primaria; la primaria no confirma éxito hasta que la Base pasiva acuerda.
* **Reconfiguration** (`ADR-IT2-005`): cuando la Base primaria deja de atender, el acceso del Orquestador conmuta a la Base pasiva, que pasa a ser la copia que atiende. El traspaso no es inmediato.

## Relaciones Permitidas

* **Recibe llamadas / mensajes de:** Cliente web y Cliente móvil, a través del gateway y del balanceador, piden la vista principal de un viajero.
* **Invoca / publica hacia:** Base primaria de viajes, con acuerdo de la Base pasiva en cada escritura confirmada. Ante la caída de la primaria, la pasiva.
* **Restricciones de frontera:** la Base de viajes no guarda cuentas, perfiles ni sesiones. La agrupación no depende del tipo concreto de `Reserva`. Esta spec no incluye la cotización ni el Ping/Echo de sus nodos.

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen (ADR / Iteración) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Vista principal de un viajero | Síncrono, desde el cliente por el gateway | Identidad del viajero ya encaminada al Orquestador | Viajes que siguen en la vista principal, con sus reservas agrupadas | Sin viajes activos: lista vacía, no error. Sin ninguna base disponible: error de servicio no disponible. No se fija cota de tiempo, porque ningún driver la pide | [RONDA_1/ITERACION_1.md](../RONDA_1/ITERACION_1.md) |
| Archivado automático del viaje completado | Interna al Orquestador, escritura en base. La dispara un proceso periódico por fecha (invocable a demanda en las pruebas) | Viaje cuya última reserva ya terminó | Viaje marcado como archivado y fuera de la vista principal | La escritura no confirma hasta el acuerdo de la pasiva | `ADR-IT2-004`, [RONDA_1/ITERACION_1.md](../RONDA_1/ITERACION_1.md) |
| Viajes archivados de un viajero | Síncrono, desde el cliente por el gateway, solo lectura | Identidad del viajero ya encaminada al Orquestador | Viajes archivados, con sus reservas agrupadas | Sin viajes archivados: lista vacía, no error. Sin ninguna base disponible: error de servicio no disponible | `REF-01` |
| Alta de un tipo de `Reserva` | Configuration-time binding en el Registro de tipos, al arrancar | Clase que extiende `Reserva` | El tipo queda registrado y la agrupación lo trata como `Reserva` | Tipo duplicado, o clase que no extiende `Reserva`: el sistema rechaza el arranque con un error que lo explica | `ADR-IT3-005` |

## Reglas de Comportamiento

1. **Agrupación:** el Orquestador agrupa las reservas por viaje y devuelve en la vista principal solo las que no fueron archivadas ni sacadas de esa vista. *(Origen: [RONDA_1/ITERACION_1.md](../RONDA_1/ITERACION_1.md))*
2. **Cierre del viaje:** un viaje está completo cuando termina su última reserva. Un proceso periódico lo detecta por fecha y lo archiva automáticamente: queda marcado como archivado, no se elimina, y sale de la vista principal. El archivo se puede consultar. *(Origen: `REF-01`)*
3. **Extensión:** un medio de transporte nuevo se incorpora como clase que extiende `Reserva` y se registra en el Registro de tipos al arrancar. La agrupación no se modifica. Un tipo duplicado o una clase que no extiende `Reserva` impiden el arranque. *(Origen: `ADR-IT3-005`)*
4. **Dos copias:** una escritura de viaje o de archivo confirmada está en la primaria y en la pasiva. Si la primaria deja de atender, la pasiva atiende. *(Origen: `ADR-IT2-004`, `ADR-IT2-005`)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-REF-01-01` | Hay reservas de un mismo viaje, activas en la vista principal | El cliente web o el cliente móvil pide la vista principal | La respuesta agrupa esas reservas por viaje | `REF-01`, `CON-01` | Test automático |
| `AC-REF-01-02` | Un viaje tiene todas sus reservas terminadas y sigue en la vista principal | Corre el proceso periódico de archivado | El viaje queda archivado y una consulta posterior no lo muestra en la vista principal | `REF-01` | Test automático |
| `AC-REF-01-06` | Hay viajes archivados de un viajero | El cliente pide los viajes archivados | La respuesta los devuelve con sus reservas agrupadas, y un viajero sin viajes archivados recibe una lista vacía | `REF-01` | Test automático |
| `AC-REF-01-07` | Un viajero no tiene viajes activos | El cliente pide la vista principal | La respuesta es una lista vacía, no un error | `REF-01` | Test automático |
| `AC-REF-01-08` | Se intenta registrar un tipo duplicado, o una clase que no extiende `Reserva` | El sistema arranca | El arranque se rechaza con un error que explica la causa | `ADR-IT3-005` | Test automático |
| `AC-REF-01-03` | El panel ya agrupa hoteles, autos, vuelos, trenes y autobuses | Se registra una clase nueva que extiende `Reserva` | Las reservas de ese medio quedan agrupadas en el viaje sin cambiar la agrupación | `QA-EVO-01`, `ADR-IT3-005` | Test automático |
| `AC-REF-01-04` | La Base primaria guarda viajes activos y el archivo | La primaria confirma una escritura de viaje o de archivo | La pasiva acordó esa escritura antes de la confirmación | `QA-DIS-01`, `ADR-IT2-004` | Test automático |
| `AC-REF-01-05` | La Base primaria deja de atender | El Orquestador escribe o lee el viaje o el archivo | La pasiva es la copia que atiende | `QA-DIS-01`, `ADR-IT2-005` | Test automático |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| Mecanismo de detección de la caída y de promoción de la Base pasiva | Error de conexión de la primaria al escribir o leer | Cómo el Orquestador detecta que la primaria dejó de atender y promueve la pasiva | `ADR-IT2-005` |
| Umbral de fallos consecutivos para conmutar | [sin especificar], configurable | Cuántos errores de conexión seguidos disparan la conmutación, para no conmutar por un fallo transitorio | `ADR-IT2-005` |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| Conector SQL del lenguaje elegido en lugar de JDBC nominal | `ADR-IT2-004` | Se mantienen la transacción y el coordinador de commit en dos fases. Lo permite [POLITICAS_SPECS_Y_PLANES.md](../POLITICAS_SPECS_Y_PLANES.md) §4.6. |
| Tras la conmutación, la primaria anterior queda marcada como no escribible hasta que se la resincronice a mano | `ADR-IT2-005` | Evita el *split-brain* que advierte el ADR (dos copias aceptando escrituras). No se automatiza la reincorporación de la primaria, que el ADR no decide. |

## Fuera de Alcance

* El evento analítico que el Orquestador publica al archivar un viaje es de `REF-06` ([SPEC-REF-06](SPEC-REF-06.md)), no de esta spec.

* Cotización, caché de borde, Scatter-Gather y Ping/Echo del nodo de cotización.
* Cliente con GPS (`QA-USA-01`).
* El plazo de 3 meses de `QA-EVO-01` es la medida del escenario de desarrollo. Esta spec verifica que la agrupación no cambia al registrar el tipo. No mide el calendario del equipo.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-22 | Versión inicial (`borrador`) | Creación a partir de `REF-01` y de los ADR aceptados que la iteración le asocia |
| 2026-11-23 | Decisiones de revisión y paso a `aprobada` (`OK SPEC`) | Cierre por fecha y archivado sin eliminar; consulta del archivo; lista vacía sin viajes; rechazo del arranque con tipo inválido; detección por error de conexión con umbral configurable y primaria vieja bloqueada |
