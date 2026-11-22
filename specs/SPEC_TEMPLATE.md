# SPEC-REF-<NN>. [Nombre del requerimiento funcional]

* **Estado:** borrador | aprobada | implementada | verificada | descartada
* **Fecha:** YYYY-MM-DD
* **Autores:** [Nombres]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `[REF de esta spec y los QA o CON que la iteración ata a esa funcionalidad]` |
| **ADRs** | `[Solo ADR en estado aceptado]` |
| **Elemento del paso 5** | `[RONDA_X/ITERACION_N.md §Subsección]` |
| **Incremento (Slice)** | `[Slice 1..5 de planes/PLAN_MAESTRO.md]` |

## Propósito y Responsabilidad

[Texto del requerimiento funcional, copiado del listado de drivers.]

## Drivers que guían el cómo

El `REF` de esta spec es el requerimiento. Cada viñeta es un `QA` o `CON` que una iteración ata a esa funcionalidad: qué restringe de la implementación, y dónde se los nombra juntos.

* **`[QA-… / CON-…]`:** [Restricción de implementación]. *(Origen: `RONDA_X/ITERACION_N.md`)*

## Conceptos de diseño aceptados

Una viñeta por táctica que quedó. Solo ADR en estado `aceptado`. La oración de restricción se copia del resultado de ese ADR.

* **`[Nombre del concepto]`** (`ADR-…`): [Restricción de implementación, copiada del resultado del ADR].

## Relaciones Permitidas

* **Recibe llamadas / mensajes de:** `[Elementos permitidos según Paso 5 §Relaciones permitidas]`
* **Invoca / publica hacia:** `[Elementos permitidos según Paso 5 §Relaciones permitidas]`
* **Restricciones de frontera:** `[Qué conexiones están prohibidas para este elemento]`

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen (ADR / Iteración) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `nombreOperacion(...)` | `[Síncrono/Asíncrono · REST/En memoria/Cola/SQL]` | `[Parámetros]` | `[Retorno]` | `[Errores / Timeout]` | `[ADR / Paso 5]` |

## Reglas de Comportamiento

1. **[Regla 1]:** [Descripción verificable]. *(Origen: `ADR-...` / `ITERACION_N`)*
2. **[Regla 2]:** [Descripción verificable]. *(Origen: `ADR-...` / `ITERACION_N`)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-REF-<NN>-01` | `[Contexto inicial]` | `[Estímulo / Acción]` | `[Resultado esperado y medible]` | `[QA-... / REF-... / ADR-...]` | `[Test automático / Carga / Demo]` |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| `[nombre_parametro]` | `[valor]` | `[efecto]` | `[ADR-...]` |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| `[Qué se simplifica]` | `[ID]` | `[Justificación de preservación de responsabilidades y contratos]` |

## Fuera de Alcance

* [Qué aspectos quedan explícitamente excluidos de esta spec.]

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| YYYY-MM-DD | Versión inicial (`borrador`) | Creación a partir de `RONDA_X/ITERACION_N.md` |
