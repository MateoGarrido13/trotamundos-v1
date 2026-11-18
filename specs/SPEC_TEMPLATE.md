# SPEC-<AREA>-<NN>. [Nombre exacto del elemento del paso 5]

* **Estado:** borrador | aprobada | implementada | verificada | descartada
* **Fecha:** YYYY-MM-DD
* **Autores:** [Nombres]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `[Rótulos de LISTADO_DRIVERS.md]` |
| **ADRs** | `[ADR-XXX, ADR-IT2-XXX, ADR-IT3-XXX, ADR-IT4-XXX]` |
| **Elemento del paso 5** | `[ITERACION_N.md §Subsección]` |
| **Incremento (Slice)** | `[Slice 1..5 de planes/PLAN_MAESTRO.md]` |

## Propósito y Responsabilidad

[Transcripción fiel de la responsabilidad asignada al elemento en el paso 5 de la iteración correspondiente.]

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
| `AC-<AREA>-<NN>-01` | `[Contexto inicial]` | `[Estímulo / Acción]` | `[Resultado esperado y medible]` | `[QA-... / REF-... / ADR-...]` | `[Test automático / Carga / Demo]` |

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
| YYYY-MM-DD | Versión inicial (`borrador`) | Creación a partir de `ITERACION_N.md` |
