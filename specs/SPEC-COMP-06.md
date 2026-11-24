# SPEC-COMP-06. Cotización resiliente

* **Estado:** aprobada
* **Fecha:** 2026-11-23
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `QA-PER-02`, `QA-PER-03`, `QA-DIS-01`, `QA-INT-01`, `CON-02` |
| **ADRs** | `ADR-004`, `ADR-005`, `ADR-006`, `ADR-007`, `ADR-008`, `ADR-IT2-001`, `ADR-IT2-002`, `ADR-IT2-003`, `ADR-IT3-004`, `ADR-IT2-004`, `ADR-IT2-005` |
| **Elemento del paso 5** | Caché de borde, Orquestador de viajes y adaptadores de cotización, Balanceador: [RONDA_1/ITERACION_2.md](../RONDA_1/ITERACION_2.md) |
| **Incremento (Slice)** | Slice 2 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

El viajero elige fecha, hospedaje y compañía y recibe una grilla de precios consolidada de tres proveedores externos, dentro de **800 ms** para el 90 % de las peticiones (`QA-PER-02`), aunque alguno de ellos no responda. La caída de un nodo de cotización no se nota (`QA-DIS-01`) y un proveedor nuevo se suma tocando un solo módulo (`QA-INT-01`).

## Drivers que guían el cómo

* **`QA-PER-02`:** tiempo total de 800 ms para el 90 % de las peticiones, con 250.000 usuarios concurrentes. *(Origen: LISTADO_DRIVERS_RONDA_1)*
* **`QA-PER-03`:** el primer contenido móvil sale de la caché de borde en menos de 1,4 s. Se verifica en [SPEC-COMP-03](SPEC-COMP-03.md).
* **`QA-DIS-01`:** un nodo de cotización caído se detecta, se aísla y se reenvía lo que estaba en vuelo, con menos de 5 minutos de inactividad al mes. *(Origen: LISTADO_DRIVERS_RONDA_1)*
* **`QA-INT-01`:** un proveedor nuevo requiere menos de 2 semanas y cambia un único módulo de frontera. *(Origen: LISTADO_DRIVERS_RONDA_1)*
* **`CON-02`:** los proveedores se integran por API. En el prototipo, mocks configurables. *(Origen: PLAN_MAESTRO §1.3)*

## Conceptos de diseño aceptados

* **Múltiples copias de datos, caché** (`ADR-005`): guarda cotizaciones previas.
* **Procesamiento concurrente, Scatter-Gather** (`ADR-006`): las consultas a los tres adaptadores salen en paralelo y las latencias no se suman.
* **Bound execution times en la Caché de borde** (`ADR-IT2-001`): la cota de 800 ms se abre al recibir el pedido; al vencer se aplica la respuesta por defecto.
* **Graceful degradation en dos niveles** (`ADR-IT2-002`): si la cota vence, la caché entrega la copia almacenada; si no la tiene, entrega la grilla parcial que el Orquestador ya armó y, si no hay ninguno, un aviso de «cotización en curso». El resultado fresco, cuando llega, actualiza la caché.
* **Cota de espera en cada adaptador, sin Retry** (`ADR-IT2-003`): cada adaptador verifica con Ping/Echo y, con eco, pide el precio. Sin eco o vencida su cota informa «origen no respondió». La cota de cada adaptador es menor que la del goal.
* **Ping/Echo** (`ADR-004`) y **Capa anti-corrupción** (`ADR-007`).
* **`IProveedor` e interfaces específicas** (`ADR-IT3-004`): `ping()`, `traducir(mensaje)` y `recibirNovedad(mensaje)`; los contratos `ICotizadorHotel`, `IProveedorInventario` e `IProveedorArrendadora` la extienden.
* **Balanceador con health check y Reconfiguration** (`ADR-IT2-005`, `QA-DIS-01`) y **commit en dos fases** (`ADR-IT2-004`) ya cubiertos por [SPEC-REF-01](SPEC-REF-01.md).

## Relaciones Permitidas

* **Recibe llamadas de:** el Cliente web (y el móvil) por la Caché de borde, el API Gateway y el Balanceador.
* **Invoca:** los tres adaptadores de cotización en paralelo y en memoria (aerolíneas, hoteles, arrendadoras); cada uno llama a su API externa.
* **Restricciones de frontera:** la cotización **no usa el Broker** y no paga las validaciones de permiso ni la auditoría de los itinerarios. Los adaptadores de cotización se despliegan con el Orquestador. El cliente no llama a un proveedor.

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /cotizaciones?fecha=&hospedaje=&compania=` | Cliente hacia la caché y el Gateway | Fecha, hospedaje, compañía | Grilla `{origenes: [{proveedor, estado, precios}], completa, copia}` | 800 ms. Parámetros inválidos: 422 | `ADR-IT2-001` |
| `ICotizadorHotel.cotizar(criterios)` | Orquestador hacia el adaptador, en memoria | Criterios | Precios traducidos al modelo interno, o «origen no respondió» | Cota propia del adaptador, menor que 800 ms. Sin Retry | `ADR-IT2-003` |
| `IProveedorInventario.cotizar(criterios)` | Idem, aerolíneas | Idem | Idem | Idem | `ADR-IT2-003` |
| `IProveedorArrendadora.cotizar(criterios)` | Idem, arrendadoras | Idem | Idem | Idem | `ADR-IT2-003` |
| `IProveedor.ping()` | Adaptador hacia su API | — | Eco | Sin eco: no pide precio | `ADR-004` |
| Health check del nodo | Balanceador hacia el Orquestador | — | Eco | Sin eco: el nodo sale de rotación | `QA-DIS-01` |

## Reglas de Comportamiento

1. **Cota del borde:** se abre al recibir el pedido, 800 ms. Si hay copia de esos criterios y la respuesta fresca no llega, se entrega la copia. *(Origen: `ADR-IT2-001`)*
2. **Primera consulta:** sin copia y con cota vencida, se entrega la grilla parcial del Orquestador o, sin ningún origen, «cotización en curso». *(Origen: `ADR-IT2-002`)*
3. **Actualización de la caché:** la respuesta fresca que llega después de la cota guarda la copia para la próxima consulta. *(Origen: `ADR-IT2-001`)*
4. **Scatter-Gather:** los tres adaptadores se consultan a la vez; la grilla se arma con los que responden. *(Origen: `ADR-006`)*
5. **Ping antes del precio:** sin eco no se pide el precio. *(Origen: `ADR-004`)*
6. **Sin Retry:** un adaptador no reintenta dentro del pedido. *(Origen: `ADR-IT2-003`)*
7. **Aislamiento de fallas:** un proveedor lento o caído solo afecta a su origen. *(Origen: `ADR-IT2-003`)*
8. **Marca de la grilla:** cada origen figura con su estado (`ok`, `no_respondio`) y la grilla indica si es completa y si viene de la copia. *(Origen: `ADR-IT2-002`)*
9. **Proveedor nuevo:** se agrega como un módulo que implementa `IProveedor` y el contrato de cotización; no modifica al Orquestador. *(Origen: `ADR-IT3-004`, `QA-INT-01`)*
10. **Nodo caído:** el Balanceador lo aísla y reenvía los pedidos en vuelo a un nodo sano dentro de la cota, y avisa a operaciones. Repetir una cotización no duplica nada. *(Origen: `QA-DIS-01`)*
11. **Mocks:** cada proveedor simulado admite demora y caída inyectadas. *(Origen: PLAN_MAESTRO §1.3)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-COMP-06-01` | Los tres proveedores responden en 300 ms cada uno | Se pide una cotización | Responde en menos de 800 ms con la grilla completa; el tiempo no es la suma de los tres | `QA-PER-02` | Test automático |
| `AC-COMP-06-02` | Un proveedor sin respuesta | Se pide una cotización | La grilla sale parcial, marca ese origen `no_respondio` y llega en menos de 800 ms | `ADR-IT2-002` | Test automático con caída inyectada |
| `AC-COMP-06-03` | Un proveedor con demora mayor que su cota | Se pide | Se corta en su cota y el resto responde | `ADR-IT2-003` | Test automático |
| `AC-COMP-06-04` | Hay copia en la caché y la respuesta fresca demora más que la cota | Se pide | Se entrega la copia dentro de 800 ms y se marca `copia` | `ADR-IT2-001` | Test automático |
| `AC-COMP-06-05` | La respuesta fresca llegó después | Se vuelve a pedir lo mismo | Se entrega la grilla actualizada | `ADR-IT2-001` | Test automático |
| `AC-COMP-06-06` | Primera consulta y ningún proveedor responde | Se pide | Responde «cotización en curso» en menos de 800 ms | `ADR-IT2-002` | Test automático |
| `AC-COMP-06-07` | Un proveedor sin eco | Se pide | No se le pide precio | `ADR-004` | Test automático |
| `AC-COMP-06-08` | Cualquier falla de un proveedor | Se pide | No hay reintento dentro del pedido | `ADR-IT2-003` | Test automático |
| `AC-COMP-06-09` | Un proveedor hotelero nuevo | Se agrega | Cambia un solo módulo y el Orquestador no se modifica | `QA-INT-01` | Test automático de arquitectura |
| `AC-COMP-06-10` | Dos nodos y uno deja de dar eco | Llegan pedidos | El nodo sale de rotación, lo que estaba en vuelo se reenvía y se avisa a operaciones | `QA-DIS-01` | Test automático |
| `AC-COMP-06-11` | Carga de 1.000 pedidos concurrentes con proveedores simulados | Se envían | El 90 % responde en 800 ms o menos | `QA-PER-02` | Prueba de carga |
| `AC-COMP-06-12` | La cotización | Se revisan sus dependencias | No usa el Broker ni escribe en una base | `ADR-IT3-001` | Test de arquitectura |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| `cota_cotizacion_ms` | 800 | Cota del borde | `ADR-IT2-001` |
| `cota_adaptador_ms` | 600 (aerolíneas), 500 (hoteles), 500 (arrendadoras) | Cota de cada adaptador, menor que 800 | `ADR-IT2-003` |
| `vigencia_copia_segundos` | 300 | Cuánto se sirve una copia como válida | `ADR-005` (invalidación) |
| `nodos_cotizacion` | 2 | Nodos simulados detrás del Balanceador | `QA-DIS-01` |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| Caché de borde y Balanceador simulados en el proceso de la app | `ADR-IT2-001`, `QA-DIS-01` | Cada uno es un componente con su contrato y sus cotas; solo cambia el despliegue |
| Proveedores simulados | `CON-02` | Permite inyectar demora y caída para demostrar las tácticas |
| Los 250.000 usuarios concurrentes no se reproducen | `QA-PER-02` | Se verifica el percentil 90 con la carga que soporta el entorno local |

## Fuera de Alcance

* Reserva efectiva en el proveedor a partir de la cotización.
* Novedades de los proveedores ([SPEC-COMP-07](SPEC-COMP-07.md)).
* Tiempo real de red de borde y CDN reales.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-23 | Versión inicial (`borrador`) | Pedido del usuario; Slice 2 sin spec |
| 2026-11-23 | Paso a `aprobada` (`OK SPEC`) | Aprobación del usuario tras resolver las decisiones de revisión |
