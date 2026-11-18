# PLAN-<AREA>-<NN>. [Nombre del plan]

* **Spec asociada:** `[SPEC-<AREA>-<NN>](../specs/SPEC-<AREA>-<NN>.md)` *(debe estar en estado `aprobada`)*
* **Estado:** borrador | aprobado | en curso | terminado
* **Fecha:** YYYY-MM-DD
* **Incremento (Slice):** `[Slice 1..5 de PLAN_MAESTRO.md]`

## Decisiones Técnicas Locales

| Decisión | Alternativa elegida | Motivo | ¿Afecta algún driver o requiere ADR? |
| :--- | :--- | :--- | :--- |
| `[Ej. Librería / estructura]` | `[Opción]` | `[Simplicidad / trazabilidad]` | `No` *(si fuera Sí, detener y registrar ADR)* |

## Estructura de Código y Mapeo Arquitectónico

Cada módulo o archivo debe corresponder a un elemento del paso 5 y respetar las *Relaciones permitidas*.

| Ruta en el repositorio | Elemento del paso 5 que instancia | Dependencias permitidas (imports) | Prohibiciones explícitas |
| :--- | :--- | :--- | :--- |
| `src/...` | `[Nombre exacto del elemento]` | `[Módulos/contratos permitidos]` | `[Ej. No importar Base de cuentas desde Orquestador]` |

## Tareas de Implementación

Cada tarea debe ser acotada, verificable y cubrir al menos un Criterio de Aceptación (`AC-*`) de la spec.

| ID | Descripción de la tarea | Archivos a crear / modificar | AC que cubre | Depende de | Criterio de terminado (Done) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `T-<AREA>-<NN>-01` | `[Descripción]` | `src/...`, `tests/...` | `AC-<AREA>-<NN>-01` | `—` | `[Test en verde / contrato verificado]` |

## Matriz de Cobertura de Criterios de Aceptación

Ningún `AC` de la spec puede quedar sin tarea ni sin test asociado.

| Criterio de Aceptación (Spec) | Tarea(s) del Plan | Nombre del test automatizado | Estado |
| :--- | :--- | :--- | :--- |
| `AC-<AREA>-<NN>-01` | `T-<AREA>-<NN>-01` | `test_AC_<AREA>_<NN>_01_...` | `[ ] Pendiente / [x] Verde` |

## Estrategia de Pruebas y Simulación de Fallos

* **Tests unitarios / contractuales:** [Cómo se verifican los contratos e invariantes].
* **Inyección de fallos / latencia (si aplica):** [Cómo se simulan demoras de proveedores, caída de nodo o caída de base primaria para probar las tácticas].
* **Comando de ejecución:** `pytest tests/...`

## Riesgos Técnicos del Plan

* [Riesgo local de implementación y cómo se mitiga.]
