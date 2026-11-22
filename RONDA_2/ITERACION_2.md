# Trotamundos — iteración 2

| Campo | Valor |
| --- | --- |
| **Ronda** | 2 |
| **Arranque** | Refinamiento. Se retoma el Asistente Virtual desplegado en ITERACION_1 y se cierran los drivers de tiempo de respuesta y seguridad que quedaron pendientes. |
| **Qué toma esta iteración** | `QA-PER-05` (respuesta al viajero en como máximo 35 segundos) y `QA-SEG-04` (no obedecer una inyección de prompt y responder solo dentro del propósito de `REF-07`). Ambos quedan resueltos por completo. |

El paso 1 de la ronda está en [RONDA_1/ITERACION_1.md](../RONDA_1/ITERACION_1.md). El cierre de la iteración anterior está en [ITERACION_1.md](ITERACION_1.md).

## Paso 2. Establecer el goal

| Id | En el goal o afuera |
| --- | --- |
| `QA-PER-05` | En el goal. Con un proveedor de modelo de IA disponible, la respuesta del asistente al viajero llega en como máximo 35 segundos. Queda resuelto por completo. |
| `QA-SEG-04` | En el goal. El asistente no obedece una inyección de prompt y no responde fuera del propósito de `REF-07`. Como alternativa, ofrece el número de contacto de la agencia de viajes preferida del usuario para delegar los casos complejos. Queda resuelto por completo. |

**Goal.** Cerrar los dos drivers pendientes de la Ronda 2: garantizar que el Asistente Virtual responda al viajero dentro de los 35 segundos (`QA-PER-05`) y que no acepte inyecciones de prompt ni responda fuera del propósito de `REF-07` (`QA-SEG-04`). Con esto quedan cubiertos todos los drivers de la Ronda 2.

## Paso 3. Elegir los elementos a refinar

| Elemento | Por qué este | Movimiento |
| --- | --- | --- |
| Contrato `IMotorConversacional` | Es la ACL del motor de lenguaje natural y el lugar donde se fija la cota de espera y el filtrado de intenciones. | Refinar |
| Módulo de Asistente Virtual | Orquesta la interpretación, el fallback ante fallos del motor y la aplicación del menú guiado cuando se supera la cota. | Refinar |
| Orquestador de viajes | Sigue siendo el único dueño de escritura; el Asistente no toca los datos directamente. | Ninguno (ya existente) |

## Paso 4. Elegir los conceptos de diseño

### 4.1 Cómo se separan los problemas menores de los casos complejos y cómo se delega a la agencia

| Alternativa | Tipo | Beneficia | Perjudica | Queda |
| --- | --- | --- | --- | --- |
| Clasificación en dos niveles: 1) Primer nivel (consultas de estado/novedades y reprogramaciones o bajas sobre reservas editables) resuelto contra el Orquestador; 2) Caso complejo (reembolsos, disputas, tramos con penalidad, proveedor caído o pedido explícito del viajero) delegado invocando la apertura de caso en el Orquestador con el resumen del diálogo, que sale por la cola de casos de ayuda hacia el Adaptador de agencia | Táctica (interoperabilidad: Use an intermediary + ACL) | Cumple `REF-07` y `QA-SEG-04` reutilizando sin cambios la cola de casos de ayuda y el Adaptador de agencia. Filtra el ruido antes de llegar a la agencia y envía el contexto estructurado cuando escala. Como alternativa, ofrece el número de contacto de la agencia de viajes preferida para delegar los casos complejos. | Requiere ofrecer siempre una opción explícita ("derivar a mi agencia") por si el viajero quiere escalar manualmente. | Sí |
| Llamada síncrona directa del Asistente Virtual a la API de la agencia preferida | — | Respuesta inmediata si la agencia contesta rápido. | Viola el rechazo de llamada síncrona a terceros y pierde el reclamo si la agencia está caída. | No |

### 4.2 Cómo se protege el soporte si el motor de lenguaje natural se demora o falla

| Alternativa | Tipo | Beneficia | Perjudica | Queda |
| --- | --- | --- | --- | --- |
| Encapsular el clasificador/LLM detrás del contrato `IMotorConversacional` (ACL) con cota de espera y degradación elegante a un menú guiado de opciones de primer nivel y escalamiento | Tácticas (interoperabilidad + disponibilidad) | Si el motor de NLP/LLM falla o supera la cota, el viajero sigue pudiendo consultar estado, reprogramar o derivar a su agencia mediante opciones guiadas. Permite además intercambiar el motor sin tocar el Asistente. | En modo degradado se reemplaza el texto libre por opciones estructuradas. | Sí |
| Acoplar el Asistente a un proveedor de LLM sin degradación | — | Menos código en el módulo. | La caída del proveedor externo deja al viajero sin primer nivel y sin forma de escalar desde el asistente. | No |

### 4.3 Qué pasa si el proveedor de modelo de IA no responde

| Alternativa | Tipo | Beneficia | Perjudica | Queda |
| --- | --- | --- | --- | --- |
| Time-out sobre la llamada al proveedor, con cota interior a los 35 segundos de `QA-PER-05`. Al agotarse, se libera el hilo y se muestra el número de contacto de la agencia de viajes preferida (`QA-DIS-02`). Si ese time-out ocurre cinco veces seguidas, Circuit Breaker pasa a Abierto, corta las llamadas a ese proveedor y muestra el mismo número en 0 ms hasta que el proveedor se recupere | Tácticas (disponibilidad: Time-out, detección de fallas; Circuit Breaker, prevención de fallas) | El viajero recibe el número de contacto de la agencia de viajes preferida antes de los 35 segundos. Con el cortacircuitos abierto no vuelve a esperar la cota del proveedor. | Mientras el circuito está abierto, no hay respuesta generativa de ese proveedor. | Sí |
| Esperar en cada petición hasta los 35 segundos y recién entonces mostrar el número de contacto | — | Aprovecha toda la cota por si el proveedor contesta al final. | Cada falla paga 35 segundos de latencia y retiene el hilo. | No |
| Reintentar la llamada al proveedor dentro de la misma petición del viajero | — | Podría obtener respuesta si la falla es transitoria. | Suma esperas dentro de los 35 segundos y compite con la cota del viajero. | No |

**Tácticas que quedan:** Clasificación en dos niveles con delegación asíncrona por la cola de casos de ayuda hacia el Adaptador de agencia (incluyendo el número de contacto de la agencia como alternativa para casos complejos); Capa Anti-Corrupción (`IMotorConversacional`) con cota de espera; Time-out hacia el proveedor de modelo, con el número de contacto de `QA-DIS-02` antes de los 35 segundos; y Circuit Breaker que, tras cinco time-out consecutivos, corta esas llamadas y entrega ese número en 0 ms.

**Tácticas reutilizadas de la Ronda 1:**

- Capa Anti-Corrupción / Adaptadores: el motor de lenguaje natural se trata como cualquier otro tercero, detrás de `IMotorConversacional`.
- Cota de espera y degradación elegante: cota de espera al motor conversacional y degradación a opciones guiadas.
- Broker con colas acotadas y Retry con identificador único, y el Adaptador de agencia sobre la cola de casos de ayuda: el escalamiento del bot usa el canal asíncrono que ya existía.

**Justificación de la selección:**

- **La frontera entre primer nivel y caso complejo es una decisión de diseño, no de producto.** `REF-07` habla de problemas menores y de casos complejos sin enumerarlos, así que la iteración fija el criterio explícito: lo que se resuelve con las operaciones ya existentes sobre el itinerario es primer nivel; lo que involucra dinero, penalidades de proveedor o un tercero que no responde se delega.
- **El escalamiento pasa por el Orquestador y no directo al Broker.** El Orquestador es el dueño del estado del caso y quien valida el permiso sobre ese itinerario, así que encolar desde el Asistente habría dejado casos sin estado persistido ni autorización.
- **El motor de lenguaje es reemplazable y prescindible.** El sistema no admite que el soporte quede fuera de línea porque un tercero de NLP se demore, y el prototipo necesita poder correr con un clasificador determinístico. Las dos cosas se resuelven con el mismo contrato y la misma degradación.
- **Rechazo de Retry contra el motor conversacional.** Hay un usuario esperando en una conversación interactiva, así que la cota vence hacia la respuesta por defecto en lugar de reintentar.
- **El proveedor que no responde no consume los 35 segundos.** Time-out detecta la falla, libera el hilo y muestra el texto de `QA-DIS-02` antes de esa cota. Circuit Breaker, a la quinta falla consecutiva, pasa a Abierto y esa misma respuesta sale en 0 ms hasta que el proveedor se recupere ([ADR-IT2-004](ADRs/ITERACION_2/ADR-IT2-004.md)).

Prototipo throwaway: ninguno por ahora.

## Paso 5. Instanciar, asignar y definir interfaces

Cuatro decisiones fijan este paso:

- **El Módulo de Asistente Virtual mantiene nodos propios sin estado**, detrás del API Gateway. No comparte nodos con la cotización ni accede de forma directa a ninguna base de datos.
- **El primer nivel reusa las operaciones del Orquestador de viajes.** Consultar el estado de un viaje/reserva o aplicar una reprogramación menor por chat ejecuta exactamente los mismos métodos, permisos, clave de idempotencia y auditoría transaccional de la Ronda 1.
- **Los casos complejos se delegan por la ruta asíncrona del Adaptador de agencia.** Cuando el Asistente detecta un caso complejo o el viajero pide hablar con su agencia, registra el caso en el Orquestador adjuntando el resumen estructurado del diálogo; el Orquestador lo publica en la cola de casos de ayuda y el Adaptador de agencia lo entrega con Retry.
- **La interpretación de lenguaje natural se aísla detrás de `IMotorConversacional`.** Si el proveedor de modelo no responde, el time-out muestra el texto de `QA-DIS-02` antes de los 35 segundos. Tras cinco time-out consecutivos, el Circuit Breaker corta las llamadas y ese texto sale en 0 ms ([ADR-IT2-004](ADRs/ITERACION_2/ADR-IT2-004.md)).

### Qué se agrega y dónde va

| Elemento | ¿Nuevo o existente? | Dónde va | Para qué driver |
| --- | --- | --- | --- |
| Reglas de filtrado de inyección de prompt | Nuevo | Tier 2, dentro del módulo de filtrado del Asistente Virtual | `QA-SEG-04` |
| Cota de ejecución de 35 segundos en `IMotorConversacional` | Refinado | Tier 2, contrato `IMotorConversacional` | `QA-PER-05` |
| Time-out y Circuit Breaker hacia el proveedor de modelo | Nuevo | Tier 2, llamada de `IMotorConversacional` al proveedor | `QA-PER-05`, `QA-DIS-02` |
| Menú guiado de opciones de primer nivel | Nuevo | Tier 2, dentro del Módulo de Asistente Virtual | `QA-PER-05`, `QA-SEG-04` |

### Cierre de `QA-PER-05` y `QA-SEG-04`

| Driver | Cómo se cierra |
| --- | --- |
| `QA-PER-05` | El contrato `IMotorConversacional` aplica una cota de espera. Si el motor no responde dentro de la cota, el Asistente muestra el número de contacto de la agencia de viajes preferida (`QA-DIS-02`) y degrada al menú guiado, garantizando que el viajero reciba una respuesta dentro de los 35 segundos. |
| `QA-SEG-04` | El módulo de filtrado de inyección de prompt intercepta cualquier mensaje que intente instrucciones distintas a reprogramaciones, consultas de estado, problemas menores o delegación a la agencia. El asistente responde solo dentro del propósito de `REF-07`, ofreciendo el número de contacto de la agencia de viajes preferida como alternativa para delegar los casos complejos. |

### Relaciones permitidas

- Cliente web y Cliente móvil → API Gateway → Módulo de Asistente Virtual.
- Módulo de Asistente Virtual → `IMotorConversacional` (con cota de tiempo y sin Retry).
- Módulo de Asistente Virtual → Orquestador de viajes (con la identidad verificada del viajero y clave de operación).
- El Módulo de Asistente Virtual nunca se conecta a ninguna base de datos, ni llama de forma directa a la API de la agencia.

### Secuencia

**Consulta con respuesta dentro de la cota (`QA-PER-05`).** El viajero envía una consulta al asistente. El API Gateway valida la firma del token y entrega el turno al Módulo de Asistente Virtual. El Asistente invoca a `IMotorConversacional.interpretar` dentro de su cota de 35 segundos. Si el motor responde a tiempo, el Asistente ejecuta la acción de primer nivel contra el Orquestador y responde al viajero. Si el motor supera la cota, el Asistente muestra el número de contacto de la agencia de viajes preferida (`QA-DIS-02`) y degrada al menú guiado, respondiendo dentro de la cota de todos modos.

**Rechazo de inyección de prompt (`QA-SEG-04`).** El viajero escribe un mensaje que intenta inyectar instrucciones ajenas al propósito de `REF-07`. El módulo de filtrado de inyección de prompt intercepta el mensaje antes de que llegue al motor de lenguaje natural. El Asistente responde que no puede atender esa solicitud, ofrece únicamente las opciones de primer nivel (consultar estado, reprogramar, derivar a la agencia preferida) y brinda el número de contacto de la agencia de viajes preferida como alternativa para delegar los casos complejos.

## Paso 6. Bosquejar y registrar la decisión

### Catálogo

Decisiones de diseño registradas en [ADRs/ITERACION_1](ADRs/ITERACION_2/), justificadas en [Justificación_ADRs_iteración_2.md](ADRs/ITERACION_2/Justificación_ADRs_iteración_2.md).

| ID | Decisión | Estado |
| --- | --- | --- |
| ADR-IT2-001 | Filtrado de inyección de prompt y alcance acotado al propósito de `REF-07` | aceptado |
| ADR-IT2-002 | Cota de ejecución de 35 segundos en `IMotorConversacional` con degradación a menú guiado | aceptado |
| ADR-IT2-003 | Clasificación en dos niveles y delegación asíncrona de casos complejos al Adaptador de agencia | aceptado |
| ADR-IT2-004 | Time-out y Circuit Breaker hacia los proveedores de modelo de IA, con el texto de `QA-DIS-02` antes de los 35 segundos | aceptado |

## Paso 7. Analizar y revisar el purpose

| Id del goal | Estado | Una oración |
| --- | --- | --- |
| `QA-PER-05` | Completely | El time-out hacia el proveedor de modelo muestra el texto de `QA-DIS-02` y libera el hilo antes de los 35 segundos. Tras cinco time-out consecutivos, el Circuit Breaker corta esas llamadas y el mismo texto sale en 0 ms hasta que el proveedor se recupere ([ADR-IT2-004](ADRs/ITERACION_2/ADR-IT2-004.md), [ADR-IT2-002](ADRs/ITERACION_2/ADR-IT2-002.md)). |
| `QA-SEG-04` | Completely | El módulo de filtrado de inyección de prompt intercepta mensajes fuera del propósito de `REF-07` y ofrece el número de contacto de la agencia de viajes preferida como alternativa para delegar los casos complejos ([ADR-IT2-001](ADRs/ITERACION_2/ADR-IT2-001.md)). |

### Justificación del estado

| Id | Qué estaba abierto al inicio de esta iteración | Cómo lo cierra la iteración 7 |
| --- | --- | --- |
| `QA-PER-05` | La cota de 35 segundos no estaba garantizada para tareas complejas como reprogramaciones. | Time-out con el texto de `QA-DIS-02` antes de los 35 segundos, y Circuit Breaker en 0 ms tras cinco fallas consecutivas ([ADR-IT2-004](ADRs/ITERACION_2/ADR-IT2-004.md)). |
| `QA-SEG-04` | El asistente podía obedecer inyecciones de prompt o responder fuera del propósito de `REF-07`. | Filtrado de inyección de prompt, alcance acotado al propósito de `REF-07`, y oferta del número de contacto de la agencia de viajes preferida como alternativa ([ADR-IT2-001](ADRs/ITERACION_2/ADR-IT2-001.md)). |

### Trade-offs aceptados

| Driver | Qué se sacrifica | A cambio de |
| --- | --- | --- |
| `QA-PER-05` | Si el proveedor no responde, el viajero recibe el texto de `QA-DIS-02` en lugar de una respuesta generativa. Con el cortacircuitos abierto, ese texto sale sin consultar al proveedor. | La respuesta llega antes de los 35 segundos, y en 0 ms cuando el circuito ya está abierto. |
| `QA-SEG-04` | El asistente no atiende consultas fuera del propósito de `REF-07`, incluso si el usuario insiste. | El viajero nunca recibe respuestas fuera del alcance del asistente virtual ni es vulnerable a inyecciones de prompt. |

### Riesgos residuales

| Riesgo | Registrado en | Por qué no cambia el estado |
| --- | --- | --- |
| El menú guiado puede no cubrir una necesidad legítima del viajero que no encaje en las opciones de primer nivel. | [ADR-IT2-002](ADRs/ITERACION_2/ADR-IT2-002.md) | El usuario siempre puede optar por "derivar a mi agencia" para escalar a un caso complejo. |

### Cierre

| Pregunta | Respuesta |
| --- | --- |
| ¿Se cumplió el goal? | Sí. `QA-PER-05` y `QA-SEG-04` quedan en `Completely`. |
| Purpose de la ronda | Con esta iteración quedan cubiertos todos los drivers de la Ronda 2: `REF-07` (Completely en ITERACION_1), `QA-DIS-02` (Completely en ITERACION_1), `QA-PER-05` (Completely) y `QA-SEG-04` (Completely). |
| ¿Hace falta otra iteración? | No. Todos los drivers de la Ronda 2 están en `Completely`. |

### Estado de los drivers de esta ronda

| Estado | Drivers |
| --- | --- |
| `Completely` | `QA-PER-05`, `QA-SEG-04` |
| `Partially` | — |
| `Not Yet` | — |
