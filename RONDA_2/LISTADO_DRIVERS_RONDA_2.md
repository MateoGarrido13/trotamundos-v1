# Listado de drivers — Ronda 2

Drivers de la ronda 2. El esquema y las etiquetas son los de [../RONDA_1/LISTADO_DRIVERS_RONDA_1.md](../RONDA_1/LISTADO_DRIVERS_RONDA_1.md). Los de la ronda 1 no se repiten acá.

## Índice

| Rótulo | Atributo | Estímulo |
| :--- | :--- | :--- |
| `QA-PER-05` | Performance(Latencia) | El viajero envía una consulta al asistente virtual |
| `QA-DIS-02` | Disponibilidad | Ningún proveedor de modelo de IA está disponible |
| `QA-SEG-04` | Seguridad y Privacidad (Security) | Inyección de prompt o consulta fuera del propósito de `REF-07` |
| `REF-07` | Requerimiento funcional | El viajero realiza consultas de estado, reprogramaciones o reporta problemas a través del asistente virtual integrado. |

## Escenario de Atributo de Calidad: Performance(Latencia) — QA-PER-05

**Rótulo:** `QA-PER-05`

| Campo | Descripción / Redacción Técnica |
| :--- | :--- |
| **Atributo:** | Performance(Latencia) |
| **Origen:** | Viajero, desde la web o el móvil |
| **Estímulo:** | Envía una consulta al asistente virtual |
| **Artefacto:** | Asistente virtual |
| **Contexto:** | El asistente está en operación y hay un proveedor de modelo de IA disponible |
| **Respuesta:** | El viajero recibe la respuesta a su consulta |
| **Medida de respuesta:** | La latencia hasta esa respuesta es como máximo 35 segundos |

## Escenario de Atributo de Calidad: Disponibilidad — QA-DIS-02

**Rótulo:** `QA-DIS-02`

| Campo | Descripción / Redacción Técnica |
| :--- | :--- |
| **Atributo:** | Disponibilidad |
| **Origen:** | Proveedor de modelo de IA |
| **Estímulo:** | Ningún proveedor de modelo de IA está disponible |
| **Artefacto:** | Asistente virtual |
| **Contexto:** | El viajero acaba de enviar una consulta |
| **Respuesta:** | El asistente muestra el número de contacto de la agencia de viajes preferida del usuario, para que pueda contactarla directamente |
| **Medida de respuesta:** | En el 100% de las consultas en esa condición, el viajero recibe el número de la agencia de viajes preferida |

## Escenario de Atributo de Calidad: Seguridad y Privacidad (Security) — QA-SEG-04

**Rótulo:** `QA-SEG-04`

| Campo | Descripción / Redacción Técnica |
| :--- | :--- |
| **Atributo:** | Seguridad y Privacidad (Security) |
| **Origen:** | Viajero que escribe en el asistente |
| **Estímulo:** | El mensaje intenta una inyección de prompt, o pide algo distinto de una reprogramación, una consulta de estado, un problema menor o la delegación de un caso complejo a la agencia de viajes preferida |
| **Artefacto:** | Asistente virtual |
| **Contexto:** | Conversación en curso con el asistente |
| **Respuesta:** | El asistente no obedece la instrucción inyectada y no responde fuera del propósito de `REF-07`. Como alternativa, ofrece el número de contacto de la agencia de viajes preferida del usuario para delegar los casos complejos |
| **Medida de respuesta:** | En el 100% de esos intentos, la respuesta permanece dentro de ese alcance y brinda el número de la agencia de viajes preferida |

## Requerimientos funcionales

**Rótulo:** `REF-07` — Asistente virtual (Chatbot)

Implementar un bot conversacional integrado que actúe como primer nivel de soporte interactivo para gestionar reprogramaciones, consultas de estado y problemas menores, delegando a la agencia de viajes preferida del usuario únicamente aquellos casos complejos.
