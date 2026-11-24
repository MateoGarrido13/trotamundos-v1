# PLAN-COMP-02. Cliente web

* **Spec asociada:** [SPEC-COMP-02](../specs/SPEC-COMP-02.md) (aprobada)
* **Estado:** terminado (suite `tests/test_comp02_web.py`: 13 passed)
* **Fecha:** 2026-11-23
* **Incremento (Slice):** Transversal, slices 2 a 5 de [PLAN_MAESTRO.md](PLAN_MAESTRO.md)

El cliente no contiene reglas de negocio. Habla solo con la app principal, que ya es el API Gateway. El ingreso es el login real de COMP-05.

## Decisiones Técnicas Locales

Ninguna agrega arquitectura ni cambia un ADR.

| # | Decisión | Elegida | Motivo | ¿Afecta driver o requiere ADR? |
| :--- | :--- | :--- | :--- | :--- |
| D1 | Forma del cliente | Una página en `src/trotamundos/web/`. La app la monta en `/web` con `StaticFiles` | PLAN_MAESTRO §2: HTML, CSS y JS sin framework ni compilación. `/web` ya es ruta pública del Gateway | No |
| D2 | Sesión | `sessionStorage` guarda `cuenta_id`, `token_acceso` y `token_renovacion`. Cada pedido lleva `Authorization: Bearer` | `ADR-IT4-004`. El Gateway traduce el token a `X-Viajero-Id` | No |
| D3 | Clave de operación | Una clave por acción de escritura (`crypto.randomUUID`). Se reutiliza si la red falla o la respuesta es 503 o 504. Una respuesta terminada suelta la clave | `ADR-IT4-008` | No |
| D4 | Error 401 | Un 403 con `{"error":"acceso_denegado"}` abre la sección «Error 401» | `QA-SEG-02`. El HTTP es 403; la página se llama «Error 401» | No |
| D5 | Servicio no disponible | Ante 503, 504 o fallo de red no se borra lo ya pintado. Hay un aviso y el botón Reintentar | `ADR-IT2-002` | No |
| D6 | Texto del backend | Se inserta con `textContent`. No hay `innerHTML` | `QA-SEG-03*` | No |
| D7 | Vista principal | Mis viajes pinta `GET /itinerarios` + `GET /itinerarios/{id}` y, aparte, los viajes de `GET /viajes` que no estén ya en un itinerario | El correo incorpora la reserva con `itinerario_id` igual a la cuenta, sin membresía. Sin `GET /viajes` no se vería en el panel (`AC-COMP-02-08`, `REF-01`) | No |
| D8 | Novedades | Al abrir la sección y cada 60 s (`meta trotamundos-refresco-novedades`) se piden novedades y casos. La sección Anuncios queda vacía | `QA-PER-01`. El listado de Booking es COMP-07 y ese plan queda para después | No |
| D9 | Asistente | El contexto firmado se devuelve en el turno siguiente. Confirmar es un botón aparte. Un 503 de `/asistente/` muestra el menú guiado | `ADR-IT6-001` | No |
| D10 | Correo | El usuario pega el token y el cliente llama `POST` o `DELETE /correo/autorizacion`. No abre la API de Gmail | El contrato de la spec. `CON-01` | No |
| D11 | Pruebas | Playwright contra Chromium, un test por `AC-COMP-02-*`, con la app real y las bases de test | Decisión de la spec | No |

## Estructura de Código y Mapeo Arquitectónico

| Ruta en el repositorio | Elemento del paso 5 que instancia | Dependencias permitidas | Prohibiciones explícitas |
| :--- | :--- | :--- | :--- |
| `src/trotamundos/web/index.html` | Cliente web, pantallas | El documento mismo | No llama a otro host |
| `src/trotamundos/web/estilos.css` | Presentación | — | — |
| `src/trotamundos/web/app.js` | Cliente web | `fetch` a la misma app | No importa el backend. No usa `innerHTML` con datos del servidor |
| `src/trotamundos/app.py` (se modifica) | La app principal sirve `/web` | `StaticFiles` | No mueve reglas de negocio al cliente |
| `tests/test_comp02_web.py` | Verificación de los `AC` | Playwright, la app | — |

## Tareas de Implementación

| ID | Descripción de la tarea | Archivos | AC que cubre | Depende de | Criterio de terminado |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `T-COMP-02-01` | Servir el cliente en `/web` e ingreso con token | `web/`, `app.py` | `AC-COMP-02-12` | — | Los pedidos de la página van a la app |
| `T-COMP-02-02` | Mis viajes, alta de viaje y de reserva, clave y reintento | `web/app.js` | `AC-COMP-02-01`, `AC-COMP-02-03`, `AC-COMP-02-04`, `AC-COMP-02-06` | 01 | Agrupadas, una sola reserva al reintentar, el texto con `<script>` no se ejecuta |
| `T-COMP-02-03` | Miembros, novedades, casos, agencia, revisión, correo | `web/app.js` | `AC-COMP-02-02`, `AC-COMP-02-05`, `AC-COMP-02-07`, `AC-COMP-02-08`, `AC-COMP-02-13` | 02 | Error 401, caso reintentado, consentimiento, Lisboa en el panel, novedad a los 60 s |
| `T-COMP-02-04` | Asistente y cotización | `web/app.js` | `AC-COMP-02-09`, `AC-COMP-02-10`, `AC-COMP-02-11` | 02 | Sin confirmar no hay efecto; el menú no es un error; la grilla parcial nombra quién no respondió |

## Matriz de Cobertura de Criterios de Aceptación

| Criterio de Aceptación (Spec) | Tarea(s) del Plan | Nombre del test automatizado | Estado |
| :--- | :--- | :--- | :--- |
| `AC-COMP-02-01` | `T-COMP-02-02` | `test_AC_COMP_02_01_mis_viajes_muestra_las_reservas_agrupadas` | `[x] Verde` |
| `AC-COMP-02-02` | `T-COMP-02-03` | `test_AC_COMP_02_02_quitar_un_miembro_sin_permiso_muestra_error_401` | `[x] Verde` |
| `AC-COMP-02-03` | `T-COMP-02-02` | `test_AC_COMP_02_03_el_reintento_reutiliza_la_clave_y_la_reserva_queda_una_vez` | `[x] Verde` |
| `AC-COMP-02-04` | `T-COMP-02-02` | `test_AC_COMP_02_04_si_la_vista_falla_se_conserva_lo_mostrado` | `[x] Verde` |
| `AC-COMP-02-05` | `T-COMP-02-03` | `test_AC_COMP_02_05_reintentar_un_caso_sin_entregar_lo_vuelve_a_en_tramite` | `[x] Verde` |
| `AC-COMP-02-06` | `T-COMP-02-02` | `test_AC_COMP_02_06_un_script_del_backend_se_muestra_como_texto` | `[x] Verde` |
| `AC-COMP-02-07` | `T-COMP-02-03` | `test_AC_COMP_02_07_sin_agencia_reportar_pide_el_consentimiento` | `[x] Verde` |
| `AC-COMP-02-08` | `T-COMP-02-03` | `test_AC_COMP_02_08_aprobar_un_remitente_lo_saca_de_revision_y_entra_al_itinerario` | `[x] Verde` |
| `AC-COMP-02-09` | `T-COMP-02-04` | `test_AC_COMP_02_09_sin_confirmar_el_asistente_no_ejecuta_la_accion` | `[x] Verde` |
| `AC-COMP-02-10` | `T-COMP-02-04` | `test_AC_COMP_02_10_si_el_asistente_degrada_se_muestra_el_menu` | `[x] Verde` |
| `AC-COMP-02-11` | `T-COMP-02-04` | `test_AC_COMP_02_11_una_grilla_parcial_muestra_quien_respondio` | `[x] Verde` |
| `AC-COMP-02-12` | `T-COMP-02-01` | `test_AC_COMP_02_12_los_pedidos_van_solo_a_la_app` | `[x] Verde` |
| `AC-COMP-02-13` | `T-COMP-02-03` | `test_AC_COMP_02_13_una_novedad_aparece_sin_recargar` | `[x] Verde` |

## Estrategia de Pruebas y Simulación de Fallos

* **Navegador:** Chromium vía Playwright. Cada `AC` es un test en `tests/test_comp02_web.py`, contra `create_app` con las bases de test.
* **Corte de red (`AC-COMP-02-03`):** el primer `POST` de la reserva se aborta. El reintento sale con la misma `X-Clave-Operacion`.
* **Base no disponible (`AC-COMP-02-04`):** el `GET /itinerarios` siguiente responde 503. El árbol ya pintado sigue.
* **Grilla parcial (`AC-COMP-02-11`):** la respuesta de `GET /cotizaciones` trae un origen `ok` y otro `no_respondio`.
* **Novedad a los 60 s (`AC-COMP-02-13`):** el reloj del navegador avanza 60 s. No hay recarga del documento.
* **Comando:** `.venv/bin/pytest tests/test_comp02_web.py -m navegador`

## Riesgos Técnicos del Plan

* **El correo no crea membresía.** Por eso Mis viajes también lee `GET /viajes`. Si esa incorporación cambia de itinerario, D7 se revisa.
* **Anuncios.** Hasta COMP-07 la sección existe y no tiene ítems.
* **`AC-COMP-04-10`** sigue siendo la demo manual de Gmail. Este plan no la automatiza.
