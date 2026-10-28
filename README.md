# trotamundos-v1

Trotamundos es un panel de gestión de viajes. El viajero ve todas sus reservas organizadas por viaje, desde la web o desde el móvil. Hoteles, autos, vuelos, trenes y autobuses quedan en un único punto de verdad, en una interfaz simple centrada en el viaje, para no tener que rastrear varias aplicaciones y bandejas de correo.

Aqui se desarollan los procesos de identificar, capturar y documentar las decisiones de diseño y construir la arquitectura con el método ADD, junto con un prototipo que demuestre su viabilidad.
Esta wiki registra las iteraciones, los ADRs, las vistas y los contratoa; a lo largo de 4 iteraciones

**Objetivo de esta ronda.** Diseñar desde cero la arquitectura del panel de viajes en web y móvil para satisfacer los drivers de [LISTADO_DRIVERS.md](LISTADO_DRIVERS.md): `QA-PER-01`, `QA-PER-02`, `QA-PER-03`, `QA-PER-04*`, `QA-DIS-01`, `QA-ESC-01`, `QA-INT-01`, `QA-INT-02`, `QA-SEG-01`, `QA-SEG-02`, `QA-SEG-03*`, `QA-EVO-01` y `QA-USA-01`.

## Paso 1. Revisar las entradas

**Purpose de la ronda.** Arquitectura greenfield del panel de viajes en web y móvil, guiada por los escenarios de [LISTADO_DRIVERS.md](LISTADO_DRIVERS.md).

Los drivers de la arquitectura son los de [LISTADO_DRIVERS.md](LISTADO_DRIVERS.md). No hay otro.

### Entradas

| Clase | Ids vigentes | Hueco o supuesto de esta ronda |
| :--- | :--- | :--- |
| Design purpose | Ronda 1, incremento greenfield | Satisfacer los escenarios de [LISTADO_DRIVERS.md](LISTADO_DRIVERS.md). |
| Escenarios de QA | Los de [LISTADO_DRIVERS.md](LISTADO_DRIVERS.md) | El texto de cada escenario es el del listado. La nota del backlog dice dónde ese texto se aparta de su propio rótulo. |

Los picos de domingo a lunes, de jueves a viernes y los de una disrupción de viajes (clima) son el ambiente de `QA-DIS-01` y `QA-ESC-01`. No forman un driver aparte.

### Backlog al abrir la ronda

Letras del Utility Tree: (importancia de negocio, riesgo técnico). Estado inicial de todos: `Not Yet`.

| Id | Prioridad | Estado | Nota |
| :--- | :--- | :--- | :--- |
| `QA-PER-01` | `(H, H)` | Not Yet | Actualización de una API externa. El escenario mide el promedio desde que el listener la detecta, nombra un módulo asíncrono y una sección "Novedades". |
| `QA-PER-02` | `(H, M)` | Not Yet | Nueva cotización desde la web. El escenario lo fija en el percentil 90, agrega 250.000 usuarios concurrentes y la respuesta incluye una consulta distribuida. |
| `QA-PER-03` | `(H, M)` | Not Yet | El usuario abre la aplicación móvil. Supuesto del escenario: red 3G en un aeropuerto, percentil 90, y la primera pintura es el login. |
| `QA-PER-04*` | `(M, H)` | Not Yet | Consulta de tendencias, destinos y cancelaciones. |
| `QA-DIS-01` | `(H, H)` | Not Yet | Caída de un nodo de cotización. La medida es menos de 5 minutos de inactividad al mes. La respuesta enumera health checks, aislamiento y redirección. |
| `QA-ESC-01` | `(H, H)` | Not Yet | 100.000 altas diarias, con confirmación en menos de 2 segundos. |
| `QA-INT-01` | `(H, H)` | Not Yet | Alta de una cadena hotelera en menos de 2 semanas, en un solo módulo de frontera. La respuesta ya describe el conector. |
| `QA-INT-02` | `(M, M)` | Not Yet | Canal de Instagram para propuestas a leads. Mezcla el esfuerzo de integración con la latencia de los canales ya existentes. |
| `QA-SEG-01` | `(M, H)` | Not Yet | Ráfaga de recuperación de contraseña. La medida no tiene ventana de tiempo y mezcla la disponibilidad del login. |
| `QA-SEG-02` | `(H, M)` | Not Yet | Registrar una actividad en el itinerario compartido. La medida no se puede testear, y el 401 es un mecanismo. |
| `QA-SEG-03*` | alta | Not Yet | El titular autoriza la lectura de su correo. |
| `QA-EVO-01` | `(H, M)` | Not Yet | Modificabilidad. Integrar un medio de transporte que el panel todavía no agrupa. |
| `QA-USA-01` | sin priorizar | Not Yet | Usabilidad. El viajero consulta su viaje en el móvil y la interfaz aprovecha una capacidad nativa, como el GPS. |

Estados del Kanban: `Not Yet`, `Partially`, `Completely`, `Discarded`.

El paso 2, en la primera iteración, elige un goal entre estos ids. Esta revisión no lo elige.
