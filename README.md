# trotamundos-v1

Trotamundos es un panel de gestión de viajes. El viajero ve todas sus reservas organizadas por viaje, desde la web o desde el móvil. Hoteles, autos, vuelos, trenes y autobuses quedan en un único punto de verdad, en una interfaz simple centrada en el viaje, para no tener que rastrear varias aplicaciones y bandejas de correo.

Aquí se desarrollan los procesos de identificar, capturar y documentar las decisiones de diseño y construir la arquitectura con el método ADD, junto con un prototipo que demuestre su viabilidad.
Esta wiki registra las iteraciones, los ADRs, las vistas y los contratos a lo largo de 6 iteraciones.

**Objetivo de esta ronda.** Diseñar desde cero la arquitectura del panel de viajes en web y móvil para satisfacer los drivers de [LISTADO_DRIVERS.md](LISTADO_DRIVERS.md): `QA-PER-01`, `QA-PER-02`, `QA-PER-03`, `QA-PER-04*`, `QA-DIS-01`, `QA-ESC-01`, `QA-INT-01`, `QA-INT-02`, `QA-SEG-01`, `QA-SEG-02`, `QA-SEG-03*`, `QA-EVO-01`, `QA-USA-01`, `REF-01`, `REF-02`, `REF-03`, `REF-04`, `REF-05`, `REF-06`, `REF-07`, `CON-01` y `CON-02`.

## Paso 1. Revisar las entradas

**Purpose de la ronda.** Arquitectura greenfield del panel de viajes en web y móvil, guiada por los escenarios de [LISTADO_DRIVERS.md](LISTADO_DRIVERS.md).

Los drivers de la arquitectura son los de [LISTADO_DRIVERS.md](LISTADO_DRIVERS.md). No hay otro.

**Criterio sobre los escenarios.** A partir de la narrativa general del enunciado se instanciaron en [LISTADO_DRIVERS.md](LISTADO_DRIVERS.md) escenarios de atributos de calidad más específicos —como la cotización web bajo carga concurrente (`QA-PER-02`), la ingesta de novedades de proveedores en pico horario (`QA-PER-01`), el alta masiva en tres continentes (`QA-ESC-01`) o la salida por canales como Instagram (`QA-INT-02`)— para bajar los objetivos de calidad a un caso real y acotado que guíe las decisiones de diseño. Esos escenarios se fijaron en el análisis inicial y operan como drivers inmutables durante todo el proceso ADD.

### Entradas

| Clase | Ids vigentes | Hueco o supuesto de esta ronda |
| :--- | :--- | :--- |
| Design purpose | Ronda 1 + 2da entrega, incremento greenfield | Satisfacer los escenarios y requerimientos de [LISTADO_DRIVERS.md](LISTADO_DRIVERS.md). |
| Escenarios de QA | Los de [LISTADO_DRIVERS.md](LISTADO_DRIVERS.md) | El texto de cada escenario es el del listado. La nota del backlog dice dónde ese texto se aparta de su propio rótulo. |
| Requerimientos funcionales | `REF-01` … `REF-07` | El texto está en [LISTADO_DRIVERS.md](LISTADO_DRIVERS.md) (`REF-07` incorpora la Opción B — Asistente virtual / Chatbot de la segunda entrega). |
| Restricciones | `CON-01`, `CON-02` | `CON-01`: las dos versiones, web y móvil, son necesarias. `CON-02`: la integración con aerolíneas, hoteles, arrendadoras y correo es por APIs. |

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
| `REF-07` | 2da entrega | Not Yet | Asistente virtual (Chatbot) de primer nivel con delegación de casos complejos a la agencia preferida. |

Estados del Kanban: `Not Yet`, `Partially`, `Completely`, `Discarded`.

El paso 2, en la primera iteración, elige un goal entre estos ids. Esta revisión no lo elige.

## Cómo se trabajó

Cada iteración sigue los siete pasos del ADD sobre la plantilla [ITERACION_ADD_TEMPLATE.md](ITERACION_ADD_TEMPLATE.md). El paso 1 es este README. Los pasos 2 a 7 están en `ITERACION_N.md`: el goal, los elementos a refinar, los conceptos de diseño comparados, los componentes e interfaces, las vistas con sus ADRs y la verificación final de cada driver.

Las decisiones se tomaron así:

- **Se comparan alternativas.** En el paso 4 cada estilo o táctica se registra con lo que beneficia, lo que perjudica y si queda o no. Las descartadas también tienen ADR (`rechazado`), con su motivo y la condición para reabrirlas.
- **Un ADR por decisión, en formato MADR** ([ADR_TEMPLATE.md](ADR_TEMPLATE.md)): contexto, impulsores, opciones, resultado y consecuencias positivas y negativas.
- **Cada iteración cierra con una verificación por driver.** Cada uno queda en `Not Yet`, `Partially`, `Completely` o `Discarded`, con una oración que lo justifica y enlaza a los ADRs. Lo que queda parcial vuelve como entrada de la iteración siguiente.
- **Los trade-offs se declaran.** El paso 7 lista lo que se sacrificó y los riesgos que quedan abiertos.
- **Cada iteración tiene una justificación** que revisa sus ADRs: por qué se eligió cada uno, qué se pagó y qué alternativa quedó más cerca de ganar.
- **Enfoque spec-driven.** Los escenarios usan una plantilla fija ([ESCENARIO_QA_TEMPLATE.md](ESCENARIO_QA_TEMPLATE.md)), las especificaciones y planes se rigen por [POLITICAS_SPECS_Y_PLANES.md](POLITICAS_SPECS_Y_PLANES.md) y los identificadores de drivers, ADRs, specs (`SPEC-*`) y planes (`PLAN-*`) son estables para poder rastrear cada línea de código hasta el escenario que la motivó.

## Evolución de las iteraciones

| Iteración | Goal | Drivers en el goal | ADRs | Documentos |
| :--- | :--- | :--- | :--- | :--- |
| **1** | Topología global del Core | `REF-01`, `CON-01`, `CON-02`, `QA-PER-02`, `QA-PER-03`, `QA-ESC-01` | 13 (7 aceptados, 1 propuesto, 5 rechazados) | [Iteración](ITERACION_1.md) · [ADRs](ADRs/ITERACION_1/) |
| **2** | Caché, interacción con APIs y sincronización de copias | `QA-PER-02`, `QA-PER-03`, `QA-DIS-01` | 6 (5 aceptados, 1 rechazado) | [Iteración](ITERACION_2.md) · [ADRs](ADRs/ITERACION_2/) |
| **3** | Entrada y salida de información externa y extensibilidad del Core | `QA-PER-01`, `QA-INT-01`, `QA-INT-02`, `QA-EVO-01`, `QA-SEG-03*`, `REF-02`, `REF-03` | 15 (10 aceptados, 5 rechazados) | [Iteración](ITERACION_3.md) · [ADRs](ADRs/ITERACION_3/) |
| **4** | Identidad regional, seguridad de login e itinerarios, gestión manual y agencia preferida | `QA-ESC-01`, `QA-SEG-01`, `QA-SEG-02`, `REF-04`, `REF-05`, `QA-PER-04*`, `REF-06`, `QA-USA-01` | 14 (11 aceptados, 3 rechazados) | [Iteración](ITERACION_4.md) · [ADRs](ADRs/ITERACION_4/) |
| **5** | Camino de lectura analítico y experiencia móvil con GPS | `QA-PER-04*`, `REF-06`, `QA-USA-01` | 5 (3 aceptados, 2 rechazados) | [Iteración](ITERACION_5.md) · [ADRs](ADRs/ITERACION_5/) |
| **6** | Asistente virtual / Chatbot de primer nivel y delegación a la agencia preferida | `REF-07` | 5 (4 aceptados, 1 rechazado) | [Iteración](ITERACION_6.md) · [ADRs](ADRs/ITERACION_6/) |

**Iteración 1: la topología del Core.** Se descompuso el sistema en tres tiers (N-Tier), con un componente de integración dentro del tier de negocio. Se eligió N-Tier sobre Microservicios y Micro-kernel porque separa presentación, lógica y datos sin sumar la complejidad operativa de los servicios distribuidos. Sobre esa base se aceptaron caché de borde y Scatter-Gather para la latencia, una capa anti-corrupción con un adaptador por proveedor y un API Gateway como única entrada para la interoperabilidad, y Redundant spare con Ping/Echo para la disponibilidad. `REF-01`, `CON-01` y `CON-02` quedaron `Completely`. Los demás quedaron `Partially`, con huecos explícitos: las cotas de tiempo, qué hacer cuando una API no responde y cómo sincronizar las bases.

**Iteración 2: cotas de tiempo, degradación y consistencia.** La latencia dominante es la de los proveedores externos, que el sistema no controla, así que la única forma de garantizar 800 ms y 1,4 s es que la caché de borde corte la espera y responda igual. Se combinaron *Bound execution times* y *Graceful degradation*, y se sacrificó completitud y frescura a cambio de cumplir el tiempo. Cada adaptador tiene su propia cota de espera y se rechazó *Retry* en esa ruta. Para la caída de un nodo, el goal prioriza la consistencia sobre la latencia: *Transactions* (commit en dos fases) entre Base primaria y Base pasiva, y *Reconfiguration* para promover la pasiva. `QA-PER-02`, `QA-PER-03` y `QA-DIS-01` quedaron `Completely`.

**Iteración 3: ingesta externa y extensibilidad.** Las novedades de Booking, el correo y las notificaciones no tienen un usuario esperando y no deben competir con la cotización en el pico de las 8 am. Se introdujo un Broker con tres colas acotadas, con ingesta en nodos propios y *Retry* con identificador único solo en las rutas asíncronas, lo que reabre con motivo el rechazo de la iteración 2. Se abstrajeron proveedores y canales detrás de contratos comunes (`IProveedor`, `ICanal`) y se modeló `Reserva` de forma polimórfica, para que un hotel, un canal o un medio de transporte nuevos sean una implementación más. Para el correo se eligió acceso delegado con revocación, parseo aislado del contenido y una whitelist con cola de revisión en lugar de descartar mensajes. Los siete drivers del goal quedaron `Completely`.

**Iteración 4: identidad regional, seguridad, gestión manual y agencia preferida.** Para el alta masiva en tres continentes (`QA-ESC-01`) se particionaron las cuentas por región de origen en nodos propios y Bases de cuentas separadas de la Base de viajes, con unicidad acotada y sesión por token firmado validado en el API Gateway. La ráfaga de recuperación (`QA-SEG-01`) se contuvo con rate limit por origen, aislamiento de recursos y un único pedido vigente por cuenta decidido de forma atómica. El acceso a itinerarios compartidos (`QA-SEG-02`) y la gestión manual (`REF-04`) se unificaron en el Orquestador con membresías, auditoría en la misma transacción, idempotencia, baja lógica y el atributo `lugar` en `Reserva`. La agencia preferida (`REF-05`) se integró de forma asíncrona con una cuarta cola del Broker y `IAgencia`.

**Iteración 5: analítica desacoplada y experiencia móvil con GPS.** Cerró los tres drivers que la iteración 4 dejó preparados en el modelo: una quinta cola acotada del Broker proyecta eventos anonimizados hacia una Base analítica separada con vistas preagregadas y cota de 10 s (`QA-PER-04*`, `REF-06`), y el Cliente móvil lee el GPS nativo de forma diferida tras el login para calcular distancia y ruta sobre `Reserva.lugar` con degradación elegante (`QA-USA-01`).

**Iteración 6: asistente virtual (Chatbot) de primer nivel.** Incorporó el requerimiento avanzado obligatorio de la segunda entrega (`REF-07`, Opción B): un Módulo de Asistente Virtual en nodos propios detrás de `IMotorConversacional` con cota de tiempo y degradación a menú guiado, que resuelve consultas de estado y reprogramaciones menores invocando las operaciones autorizadas e idempotentes del Orquestador (`REF-04`, `QA-SEG-02`) y delega únicamente los casos complejos a la agencia preferida por la cola de casos de ayuda e `IAgencia` (`REF-05`).

## Estado de los drivers

Al cierre de la iteración 6:

| Estado | Drivers |
| :--- | :--- |
| `Completely` | `REF-01`, `REF-02`, `REF-03`, `REF-04`, `REF-05`, `REF-06`, `REF-07`, `CON-01`, `CON-02`, `QA-PER-01`, `QA-PER-02`, `QA-PER-03`, `QA-PER-04*`, `QA-DIS-01`, `QA-ESC-01`, `QA-INT-01`, `QA-INT-02`, `QA-SEG-01`, `QA-SEG-02`, `QA-SEG-03*`, `QA-EVO-01`, `QA-USA-01` |
| `Partially` | — |
| `Not Yet` | — |

## Contenido del repositorio

- **`ADRs/`**: los registros de decisión de cada iteración (`ITERACION_1` a `ITERACION_6`), más un documento de justificación por iteración.
- **`vistas/`**: las vistas de componentes y conectores y los diagramas de secuencia, en SVG (además de las vistas Mermaid en cada iteración).
- **`ITERACION_N.md`**: el desarrollo de cada iteración (`ITERACION_1.md` a `ITERACION_6.md`), del paso 2 al 7.
- **`LISTADO_DRIVERS.md`**: los escenarios, requerimientos y restricciones que guían el diseño.
- **`POLITICAS_SPECS_Y_PLANES.md`, `specs/` y `planes/`**: políticas de Spec-Driven Development, plantillas (`SPEC_TEMPLATE.md`, `PLAN_TEMPLATE.md`) y [Plan Maestro del prototipo](planes/PLAN_MAESTRO.md).
- **Plantillas ADD** (`ADR_TEMPLATE.md`, `ESCENARIO_QA_TEMPLATE.md`, `ITERACION_ADD_TEMPLATE.md`): los formatos que usan los documentos de arquitectura.
- **`TPE - Diseño de Sistemas de Software.pdf`**: el enunciado.

## Segunda Parte

Con las iteraciones 5 y 6 quedan cerrados los 22 drivers (incluyendo la Opción B — Asistente Virtual / Chatbot) con 58 decisiones de arquitectura registradas y justificadas. A partir de [POLITICAS_SPECS_Y_PLANES.md](POLITICAS_SPECS_Y_PLANES.md) y [planes/PLAN_MAESTRO.md](planes/PLAN_MAESTRO.md) se desarrollan las especificaciones contractuales en `specs/` y los planes de implementación en `planes/` para el prototipo trazable.
