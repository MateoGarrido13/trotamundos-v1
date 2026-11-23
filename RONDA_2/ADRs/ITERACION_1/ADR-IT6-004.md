# Interoperabilidad y Disponibilidad: Contrato `IMotorConversacional` (ACL) con cota de espera y degradación a menú guiado

* **Estado:** aceptado
* **Fecha:** 2026-11-17
* **Decisores:** Ramiro Rossi

## Contexto y Declaración del Problema
Para interpretar el lenguaje natural del viajero en el Asistente Virtual (`REF-07`), el módulo puede apoyarse en un motor conversacional o servicio de procesamiento de lenguaje natural (NLP/LLM). Igual que los proveedores de viajes y los canales, un motor conversacional externo tiene latencia variable y puede fallar o saturarse durante una disrupción masiva de viajes. Hay que decidir cómo se integra ese motor y cómo responde el Asistente si el motor tarda o no está disponible.

## Impulsores de la Decisión (Decision Drivers)
* `REF-07`: el asistente debe seguir operando como primer nivel de soporte para consultas de estado, reprogramaciones menores y derivación a la agencia.
* `QA-DIS-01`: tolerar fallos de componentes o servicios externos sin dejar inoperante el soporte al viajero.
* Reutilizar Capa Anti-Corrupción ([ADR-007](../../../RONDA_1/ADRs/ITERACION_1/ADR-007.md)), *Bound execution times* ([ADR-IT2-001](../../../RONDA_1/ADRs/ITERACION_2/ADR-IT2-001.md)) y *Graceful degradation* ([ADR-IT2-002](../../../RONDA_1/ADRs/ITERACION_2/ADR-IT2-002.md)).

## Opciones Consideradas
* Opción 1: Encapsular la interpretación de intención detrás del contrato interno `IMotorConversacional` (`interpretar(mensaje, contextoViaje)`), con una cota de espera (*Bound execution times*) y sin *Retry* bloqueante. Si el motor conversacional responde dentro de la cota, el Asistente procesa la intención en lenguaje natural. Si la cota vence o el motor falla, aplica *Graceful degradation*: presenta opciones estructuradas de primer nivel (1. Consultar estado de reserva, 2. Reprogramar fecha/datos, 3. Escalar problema complejo a mi agencia preferida) para que el viajero resuelva o escale su caso sin interrupción.
* Opción 2: Acoplar el Módulo de Asistente Virtual directamente al SDK de un proveedor de LLM específico y devolver error cuando ese proveedor falle o demore.

## Resultado de la Decisión
Opción elegida: **"Opción 1: contrato `IMotorConversacional` con cota de tiempo y degradación elegante a opciones guiadas"**, porque aplica exactamente las mismas tácticas de las iteraciones 1 y 2 (*ACL*, *Bound execution times* y *Graceful degradation*). Así se puede cambiar el motor de NLP (o usar un motor determinístico local en pruebas) tocando un solo adaptador, y una caída del motor de lenguaje nunca impide que el viajero consulte su reserva, la reprograme o escale el caso a su agencia preferida.

### Consecuencias Positivas (Beneficios)
* El soporte de primer nivel y el escalamiento a la agencia siguen funcionando al 100 % aunque el motor de lenguaje natural esté caído o lento.
* Cambiar de proveedor de NLP/LLM o usar un clasificador basado en reglas en el prototipo solo requiere implementar `IMotorConversacional`.

### Consecuencias Negativas (Trade-offs / Riesgos)
* En modo degradado la interacción pasa de texto libre a opciones guiadas, perdiendo flexibilidad conversacional a cambio de disponibilidad.
