# ADR-IT7-001 — Filtrado de inyección de prompt y alcance acotado al propósito de REF-07

## Contexto

El Asistente Virtual de primera ronda (ITERACION_1) interpreta intenciones del viajero a través de `IMotorConversacional`. Un usuario malintencionado o un mensaje ambiguo podría intentar inyectar instrucciones ajenas al propósito de `REF-07` (reprogramaciones, consultas de estado, problemas menores, delegación de casos complejos a la agencia preferida).

## Impulsores

- `QA-SEG-04`: El asistente no obedece una inyección de prompt y no responde fuera del propósito de `REF-07`.
- `REF-07`: El asistente actúa como primer nivel de soporte interactivo con delegación de casos complejos a la agencia de viajes preferida.

## Opciones

| Opción | Descripción |
| --- | --- |
| Opción 1 | Módulo de filtrado de inyección de prompt antes de `IMotorConversacional`. Intercepta y rechaza mensajes fuera del propósito. |
| Opción 2 | Ningún filtrado; confiar en que el motor de lenguaje natural rechace instrucciones ajenas. |

## Decisión

**Opción 1 elegida.** Se implementa un módulo de filtrado de inyección de prompt que intercepta cualquier mensaje que intente instrucciones distintas a reprogramaciones, consultas de estado, problemas menores o delegación a la agencia. El asistente responde solo dentro del propósito de `REF-07`, ofreciendo el número de contacto de la agencia de viajes preferida del usuario como alternativa para delegar los casos complejos.

## Consecuencias

- Positivo: Cumple `QA-SEG-04`. El asistente nunca responde fuera de su alcance ni es vulnerable a inyecciones de prompt. Como alternativa, brinda el número de contacto de la agencia de viajes preferida para que el usuario pueda contactarla directamente.
- Negativo: Suma un componente de filtrado adicional. El usuario puede recibir un rechazo si su consulta no encaja estrictamente en el propósito de `REF-07`, pero siempre puede optar por "derivar a mi agencia" para escalar.

## Relación con otros ADRs

- `ADR-IT6-003`: Clasificación en dos niveles y delegación asíncrona al Adaptador de agencia. El filtrado de este ADR ocurre antes de la clasificación.
- `ADR-IT7-002`: Cota de ejecución de 35 segundos en `IMotorConversacional`. El filtrado ocurre antes de la cota de espera.
