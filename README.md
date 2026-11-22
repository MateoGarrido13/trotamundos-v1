# trotamundos-v1

Trotamundos es un panel de gestión de viajes. El viajero ve todas sus reservas organizadas por viaje, desde la web o desde el móvil. Hoteles, autos, vuelos, trenes y autobuses quedan en un único punto de verdad, en una interfaz simple centrada en el viaje, para no tener que rastrear varias aplicaciones y bandejas de correo.

Aquí se desarrollan los procesos de identificar, capturar y documentar las decisiones de diseño y construir la arquitectura con el método ADD, junto con un prototipo que demuestre su viabilidad.
Esta wiki registra las iteraciones y los ADRs a lo largo de las rondas de arquitectura.

## Ronda 1 — Diseño greenfield del panel de viajes

La **Ronda 1** abarca el diseño desde cero (greenfield) de la arquitectura del panel de viajes en web y móvil, guiada por los escenarios de [RONDA_1/LISTADO_DRIVERS_RONDA_1.md](RONDA_1/LISTADO_DRIVERS_RONDA_1.md). Durante esta ronda se resuelven los drivers `QA-PER-01`, `QA-PER-02`, `QA-PER-03`, `QA-PER-04*`, `QA-DIS-01`, `QA-ESC-01`, `QA-INT-01`, `QA-INT-02`, `QA-SEG-01`, `QA-SEG-02`, `QA-SEG-03*`, `QA-EVO-01`, `QA-USA-01`, `REF-01`, `REF-02`, `REF-03`, `REF-04`, `REF-05`, `REF-06`, `CON-01` y `CON-02`.

El paso 1 de la ronda está registrado en [RONDA_1/ITERACION_1.md](RONDA_1/ITERACION_1.md).

## Ronda 2 — Asistente virtual (diseño brownfield)

La **Ronda 2** incorpora el asistente virtual / chatbot de primer nivel (`REF-07`) como una funcionalidad posterior a la Ronda 1. Es un diseño **brownfield**: se extiende sobre la arquitectura ya cerrada de la Ronda 1 sin reabrir ninguno de sus drivers ni modificar su propósito greenfield. El asistente virtual es independiente del resto del sistema y se delega únicamente los casos complejos a la agencia de viajes preferida.

El desarrollo de la Ronda 2 se encuentra en [RONDA_2/ITERACION_1.md](RONDA_2/ITERACION_1.md).

## Cómo se trabajó

Cada iteración sigue los siete pasos del ADD sobre la plantilla [ITERACION_ADD_TEMPLATE.md](ITERACION_ADD_TEMPLATE.md). El paso 1 se registra una vez por ronda en `RONDA_1/ITERACION_1.md`. Los pasos 2 a 7 están en cada `RONDA_X/ITERACION_N.md`: el goal, los elementos a refinar, los conceptos de diseño comparados, los componentes e interfaces, las vistas con sus ADRs y la verificación final de cada driver.

Las decisiones se tomaron así:

- **Se comparan alternativas.** En el paso 4 cada estilo o táctica se registra con lo que beneficia, lo que perjudica y si queda o no. Las descartadas también tienen ADR (`rechazado`), con su motivo y la condición para reabrirlas.
- **Un ADR por decisión, en formato MADR** ([ADR_TEMPLATE.md](ADR_TEMPLATE.md)): contexto, impulsores, opciones, resultado y consecuencias positivas y negativas.
- **Cada iteración cierra con una verificación por driver.** Cada uno queda en `Not Yet`, `Partially`, `Completely` o `Discarded`, con una oración que lo justifica y enlaza a los ADRs. Lo que queda parcial vuelve como entrada de la iteración siguiente.
- **Los trade-offs se declaran.** El paso 7 lista lo que se sacrificó y los riesgos que quedan abiertos.
- **Cada iteración tiene una justificación** que revisa sus ADRs: por qué se eligió cada uno, qué se pagó y qué alternativa quedó más cerca de ganar.
- **Enfoque spec-driven.** Los escenarios usan una plantilla fija ([ESCENARIO_QA_TEMPLATE.md](ESCENARIO_QA_TEMPLATE.md)), las especificaciones y planes se rigen por [POLITICAS_SPECS_Y_PLANES.md](POLITICAS_SPECS_Y_PLANES.md) y los identificadores de drivers, ADRs, specs (`SPEC-*`) y planes (`PLAN-*`) son estables para poder rastrear cada línea de código hasta el escenario que la motivó.

## Evolución de las iteraciones

| Iteración | Ronda | Goal | Drivers en el goal | ADRs | Documentos |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | 1 | Topología global del Core | `REF-01`, `CON-01`, `CON-02`, `QA-PER-02`, `QA-PER-03`, `QA-ESC-01` | 13 (7 aceptados, 1 propuesto, 5 rechazados) | [Iteración](RONDA_1/ITERACION_1.md) · [ADRs](RONDA_1/ADRs/ITERACION_1/) |
| **2** | 1 | Caché, interacción con APIs y sincronización de copias | `QA-PER-02`, `QA-PER-03`, `QA-DIS-01` | 6 (5 aceptados, 1 rechazado) | [Iteración](RONDA_1/ITERACION_2.md) · [ADRs](RONDA_1/ADRs/ITERACION_2/) |
| **3** | 1 | Entrada y salida de información externa y extensibilidad del Core | `QA-PER-01`, `QA-INT-01`, `QA-INT-02`, `QA-EVO-01`, `QA-SEG-03*`, `REF-02`, `REF-03` | 15 (10 aceptados, 5 rechazados) | [Iteración](RONDA_1/ITERACION_3.md) · [ADRs](RONDA_1/ADRs/ITERACION_3/) |
| **4** | 1 | Identidad regional, seguridad de login e itinerarios, gestión manual y agencia preferida | `QA-ESC-01`, `QA-SEG-01`, `QA-SEG-02`, `REF-04`, `REF-05`, `QA-PER-04*`, `REF-06`, `QA-USA-01` | 14 (11 aceptados, 3 rechazados) | [Iteración](RONDA_1/ITERACION_4.md) · [ADRs](RONDA_1/ADRs/ITERACION_4/) |
| **5** | 1 | Camino de lectura analítico y experiencia móvil con GPS | `QA-PER-04*`, `REF-06`, `QA-USA-01` | 5 (3 aceptados, 2 rechazados) | [Iteración](RONDA_1/ITERACION_5.md) · [ADRs](RONDA_1/ADRs/ITERACION_5/) |
| **6** | 2 | Asistente virtual / Chatbot de primer nivel y delegación a la agencia preferida | `REF-07`, `QA-DIS-02` | 5 (4 aceptados, 1 rechazado) | [Iteración](RONDA_2/ITERACION_1.md) · [ADRs](RONDA_2/ADRs/ITERACION_1/) |
| **7** | 2 | Tiempo de respuesta y seguridad del asistente virtual | `QA-PER-05`, `QA-SEG-04` | 3 (3 aceptados, 0 rechazados) | [Iteración](RONDA_2/ITERACION_2.md) · [ADRs](RONDA_2/ADRs/ITERACION_2/) |

## Contenido del repositorio

- **`RONDA_1/ADRs/`** y **`RONDA_2/ADRs/`**: los registros de decisión de cada iteración, más un documento de justificación por iteración.
- **`RONDA_1/vistas/`**: las vistas de componentes y conectores y los diagramas de secuencia, en SVG (además de las vistas Mermaid en cada iteración).
- **`RONDA_X/ITERACION_N.md`**: el desarrollo de cada iteración (`RONDA_1/ITERACION_1.md` a `RONDA_1/ITERACION_5.md`, `RONDA_2/ITERACION_1.md` y `RONDA_2/ITERACION_2.md`), del paso 2 al 7.
- **`RONDA_1/LISTADO_DRIVERS_RONDA_1.md`**: los escenarios, requerimientos y restricciones de la Ronda 1.
- **`RONDA_2/LISTADO_DRIVERS_RONDA_2.md`**: los drivers de la Ronda 2.
- **`POLITICAS_SPECS_Y_PLANES.md`, `specs/` y `planes/`**: políticas de Spec-Driven Development, plantillas (`SPEC_TEMPLATE.md`, `PLAN_TEMPLATE.md`) y [Plan Maestro del prototipo](planes/PLAN_MAESTRO.md).
- **Plantillas ADD** (`ADR_TEMPLATE.md`, `ESCENARIO_QA_TEMPLATE.md`, `ITERACION_ADD_TEMPLATE.md`): los formatos que usan los documentos de arquitectura.
- **`TPE - Diseño de Sistemas de Software.pdf`**: el enunciado.

## Segunda parte

Con las iteraciones 1 a 5 de la Ronda 1 quedan cerrados los 21 drivers iniciales. La Ronda 2 incorpora el requerimiento avanzado obligatorio de la segunda entrega (`REF-07` — Asistente virtual / Chatbot) junto con los escenarios de [RONDA_2/LISTADO_DRIVERS_RONDA_2.md](RONDA_2/LISTADO_DRIVERS_RONDA_2.md) (`QA-PER-05`, `QA-DIS-02`, `QA-SEG-04`) como una feature posterior sobre el diseño brownfield ya cerrado, sin reabrir ningún driver de la Ronda 1. `REF-07` y `QA-DIS-02` se cierran en ITERACION_1; `QA-PER-05` y `QA-SEG-04` se cierran en ITERACION_2. A partir de [POLITICAS_SPECS_Y_PLANES.md](POLITICAS_SPECS_Y_PLANES.md) y [planes/PLAN_MAESTRO.md](planes/PLAN_MAESTRO.md) se desarrollan las especificaciones contractuales en `specs/` y los planes de implementación en `planes/` para el prototipo trazable.
