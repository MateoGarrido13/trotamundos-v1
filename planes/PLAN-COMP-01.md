# PLAN-COMP-01. Sistema ejecutable de punta a punta

* **Estado:** terminado
* **Spec:** [SPEC-COMP-01](../specs/SPEC-COMP-01.md) (aprobada)
* **Slice:** transversal a 3, 4 y 5

## Decisiones de implementación (tomadas con la opción recomendada)

| # | Decisión | Elegida | Por qué |
| :--- | :--- | :--- | :--- |
| D1 | Cómo se arman los routers de las sub-apps | Cada sub-app expone `crear_router(...)`; su `create_app` lo usa y `app.py` lo incluye | Los tests de cada módulo siguen intactos y no se duplica código |
| D2 | Dónde viven los consumidores | `src/trotamundos/consumidores.py`: `Supervisor` con una tarea por cola | Un solo lugar, probado aparte de FastAPI |
| D3 | Claves de cifrado vacías en desarrollo | Si `TROTA_CLAVE_TOKENS`, `TROTA_CLAVE_ASISTENTE` o `TROTA_CLAVE_AGENCIA` faltan, se generan claves efímeras y se avisa en el log | Que `uvicorn` arranque sin configurar; en producción se exigen por entorno |
| D4 | Bases de desarrollo y de test | Bases `trotamundos_dev` y `trotamundos_test` dentro de los mismos tres contenedores, creadas por `scripts/crear_bases.py` (idempotente). `conftest.py` fija las variables de entorno de test antes de importar la configuración | Los volúmenes ya existen, y un `CREATE DATABASE` es lo único que los vuelve a usar |
| D5 | Protección contra borrado | `limpiar_base` se niega a borrar una base cuyo nombre no termine en `_test` | Cumple AC-COMP-01-10 de forma estructural |
| D6 | Esquemas al arrancar | La app aplica los `.sql` (todos usan `IF NOT EXISTS`) al arrancar | Una base nueva funciona sin pasos manuales |
| D7 | Id de viaje | `viaje-<uuid4 hex[:12]>`, calculado antes de la operación 2PC | La operación corre en ambas bases: el valor no puede ser distinto en cada una |
| D8 | Cola de notificaciones | Sin consumidor: no hay spec que la use (`QA-INT-02`) | Se deja documentado |

## Estructura de código

| Archivo | Rol |
| :--- | :--- |
| `src/trotamundos/consumidores.py` | `Supervisor`: tarea por cola, reinicio con espera creciente, parada ordenada |
| `src/trotamundos/orquestador/alta_viajes.py` | `ServicioViajes`: `crearViaje`, `agregarMiembro`, `quitarMiembro`, `listarMiembros` con permiso, auditoría y clave de operación |
| `src/trotamundos/orquestador/api_miembros.py` | Endpoints `POST /viajes`, `GET/POST/DELETE /itinerarios/{id}/miembros` |
| `src/trotamundos/{analitica,asistente}/app.py`, `entrada/app.py` | Se agrega `crear_router(...)` |
| `src/trotamundos/app.py` | Monta todo, arranca los consumidores y el sondeo, aplica esquemas |
| `src/trotamundos/orquestador/api_gestion.py`, `api.py` | `tipo` con el código del registro |
| `scripts/crear_bases.py` | Crea `trotamundos_dev` y `trotamundos_test` |
| `tests/test_comp01_*.py` | Un test por criterio |

Imports prohibidos: sin cambios. `tests/test_arquitectura.py` sigue vigente y se amplía para exigir que `consumidores.py` y `app.py` sean los únicos que conectan módulos.

## Tareas

| Tarea | Cubre |
| :--- | :--- |
| T-COMP-01-01 | Bases dev/test, `crear_bases.py`, protección de `limpiar_base`, esquemas al arrancar (AC-10) |
| T-COMP-01-02 | `Supervisor` de consumidores y su ciclo de vida (AC-01, 02, 03, 12) |
| T-COMP-01-03 | `crear_router` en las sub-apps y montaje en `app.py` (AC-04, 05) |
| T-COMP-01-04 | Alta de viajes y membresías (AC-06, 07, 08, 11, 13) |
| T-COMP-01-05 | `tipo` uniforme (AC-09) |

## Tests por archivo

`test_comp01_consumidores.py` (AC-03, 12 y la regla de arquitectura), `test_comp01_sistema.py` (AC-01, 02, 04, 05, 09, 10) y `test_comp01_alta_viajes.py` (AC-06, 07, 08, 11, 13, más la validación de nombre y rol). Suite completa: 583 tests en verde.

## Lo que se agregó al implementar (fijado también en la spec)

* Columna `viaje.nombre` (`06_alta_viajes.sql`) y `GET /itinerarios`, para que un cliente descubra sus itinerarios y muestre el nombre del viaje.
* La cola de notificaciones no tiene consumidor (D8): no hay spec que la use.
* `test_ref06_modelo` esperaba el nombre `analitica` para la base; ahora espera la de test, porque la separación que verifica es el DSN.

## Matriz de cobertura

| AC | Tarea | Test | Estado |
| :--- | :--- | :--- | :--- |
| AC-COMP-01-01 | 02 | `test_AC_COMP_01_01_caso_avanza_sin_invocar_procesar_uno` | [x] Verde |
| AC-COMP-01-02 | 02 | `test_AC_COMP_01_02_reserva_llega_al_informe` | [x] Verde |
| AC-COMP-01-03 | 02 | `test_AC_COMP_01_03_consumidor_se_reinicia_y_los_otros_siguen` | [x] Verde |
| AC-COMP-01-04 | 03 | `test_AC_COMP_01_04_openapi_expone_todos_los_endpoints` | [x] Verde |
| AC-COMP-01-05 | 03 | `test_AC_COMP_01_05_analitica_caida_no_impide_operar` | [x] Verde |
| AC-COMP-01-06 | 04 | `test_AC_COMP_01_06_crear_viaje_sin_itinerario_hace_organizador` | [x] Verde |
| AC-COMP-01-07 | 04 | `test_AC_COMP_01_07_participante_no_agrega_miembros` | [x] Verde |
| AC-COMP-01-08 | 04 | `test_AC_COMP_01_08_no_se_quita_al_ultimo_organizador` | [x] Verde |
| AC-COMP-01-09 | 05 | `test_AC_COMP_01_09_tipo_uniforme` | [x] Verde |
| AC-COMP-01-10 | 01 | `test_AC_COMP_01_10_los_tests_no_tocan_la_base_de_desarrollo` | [x] Verde |
| AC-COMP-01-11 | 04 | `test_AC_COMP_01_11_clave_repetida_no_duplica_viaje` | [x] Verde |
| AC-COMP-01-12 | 02 | `test_AC_COMP_01_12_cierre_sin_tareas_colgadas` | [x] Verde |
| AC-COMP-01-13 | 04 | `test_AC_COMP_01_13_itinerario_ajeno_igual_que_inexistente` | [x] Verde |
