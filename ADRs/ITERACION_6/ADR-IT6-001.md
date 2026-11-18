# Performance: Módulo de Asistente Virtual en nodos propios, desacoplado de los nodos de cotización

* **Estado:** aceptado
* **Fecha:** 2026-11-17
* **Decisores:** Mateo Garrido

## Contexto y Declaración del Problema
`REF-07` pide implementar un bot conversacional integrado que actúe como primer nivel de soporte interactivo para gestionar reprogramaciones, consultas de estado y problemas menores, delegando a la agencia de viajes preferida del usuario únicamente aquellos casos complejos. Las consultas al asistente virtual se disparan con más fuerza durante picos de interrupciones de viajes (por ejemplo, disrupciones climáticas), el mismo contexto en el que el sistema debe sostener 250.000 usuarios concurrentes cotizando en menos de 800 ms (`QA-PER-02`) y menos de 5 minutos de inactividad al mes (`QA-DIS-01`). Hay que decidir dónde se despliega el Módulo de Asistente Virtual y cómo recibe los mensajes desde el Cliente web y el Cliente móvil.

## Impulsores de la Decisión (Decision Drivers)
* `REF-07`: bot conversacional integrado como primer nivel de soporte interactivo.
* `QA-PER-02`: la cotización desde la web debe responder en menos de 800 ms en el percentil 90 y no puede competir por CPU o hilos con sesiones conversacionales ni con llamadas a motores de lenguaje.
* `CON-01`: disponible tanto en la versión web como en la móvil a través del único punto de entrada ([ADR-008](../ITERACION_1/ADR-008.md)).
* Reutilizar la separación por despliegue aplicada a la ingesta ([ADR-IT3-010](../ITERACION_3/ADR-IT3-010.md)) y al registro ([ADR-IT4-002](../ITERACION_4/ADR-IT4-002.md)).

## Opciones Consideradas
* Opción 1: Desplegar el **Módulo de Asistente Virtual** en nodos propios sin estado, separados de los nodos del Orquestador de viajes. Los clientes (web y móvil) envían los mensajes del chat al API Gateway, que valida la firma del token de sesión ([ADR-IT4-004](../ITERACION_4/ADR-IT4-004.md)), aplica limitación de tasa ([ADR-IT4-005](../ITERACION_4/ADR-IT4-005.md)) y encamina el turno conversacional al Módulo de Asistente Virtual. Para ejecutar una consulta o acción sobre el viaje, el Asistente invoca al Orquestador de viajes por su interfaz interna.
* Opción 2: Ejecutar el Asistente Virtual dentro de los mismos nodos del Orquestador de viajes.
* Opción 3: Ejecutar toda la lógica del bot en el cliente (web y móvil) sin componente de servidor propio.

## Resultado de la Decisión
Opción elegida: **"Opción 1: Módulo de Asistente Virtual en nodos propios, detrás del API Gateway"**, porque aísla el costo de interpretar el diálogo y mantener el turno conversacional de los nodos que resuelven la cotización en 800 ms (`QA-PER-02`). Durante una disrupción climática, una oleada de viajeros abriendo el chat de soporte puede escalar o saturar los nodos del Asistente sin tumbar ni demorar las cotizaciones ni el resto del Core. La opción 2 hace que el chat compita por recursos con la cotización. La opción 3 duplica las reglas de decisión entre web y móvil (`CON-01`) y expone credenciales o reglas del clasificador en el cliente.

### Consecuencias Positivas (Beneficios)
* Los nodos del Orquestador de viajes y la ruta de 800 ms de `QA-PER-02` quedan aislados de la carga conversacional.
* Un único Módulo de Asistente Virtual sirve por igual a Cliente web y Cliente móvil (`CON-01`).
* Reutiliza la validación de firma JWT y el límite de tasa del API Gateway ([ADR-IT4-004](../ITERACION_4/ADR-IT4-004.md), [ADR-IT4-005](../ITERACION_4/ADR-IT4-005.md)).

### Consecuencias Negativas (Trade-offs / Riesgos)
* Un grupo más de nodos para desplegar y monitorear.
* Cada acción de primer nivel suma un salto HTTP interno desde el Módulo de Asistente Virtual hacia el Orquestador de viajes.
