# PLAN-COMP-03. Cliente móvil con GPS

* **Spec asociada:** [SPEC-COMP-03](../specs/SPEC-COMP-03.md) (aprobada)
* **Estado:** terminado (suite `tests/test_comp03_movil.py`: 11 passed)
* **Fecha:** 2026-11-23
* **Incremento (Slice):** Slice 4 de [PLAN_MAESTRO.md](PLAN_MAESTRO.md)

El cliente móvil no contiene reglas de negocio. El GPS se usa en el dispositivo y las coordenadas del viajero no viajan al Gateway.

## Decisiones Técnicas Locales

| # | Decisión | Elegida | Motivo | ¿Afecta driver o requiere ADR? |
| :--- | :--- | :--- | :--- | :--- |
| D1 | Forma de `lugar` | `Lugar` con nombre, destino y latitud/longitud opcionales. Un texto sigue siendo un nombre solo | `ADR-IT4-009`. Las reservas ya guardadas y los tests que mandan un nombre siguen válidos | No |
| D2 | Persistencia | La columna `lugar` sigue siendo texto. Solo el nombre se guarda como antes; si hay destino o coordenadas, se guarda el JSON | No hace falta una migración que rompa las filas existentes | No |
| D3 | Respuesta HTTP | Si el lugar es solo un nombre, la API lo devuelve como texto. Si tiene destino o coordenadas, devuelve el objeto | El cliente móvil lee las dos formas. El cliente web sigue mostrando el nombre | No |
| D4 | Destino analítico | El evento usa el destino del lugar o, si no tiene, el nombre | La columna analítica es texto. Un lugar que era un nombre sigue publicando ese nombre | No |
| D5 | Cliente | PWA en `src/trotamundos/movil/`, servida en `/movil`, con manifiesto y service worker | `QA-PER-03` y `ADR-IT2-001`. `/movil` es ruta pública del Gateway | No |
| D6 | Distancia | Haversine en el dispositivo, en metros. El enlace de ruta es `geo:lat,lon`. La más cercana lleva la clase `cercana` | `ADR-IT5-003`. No hay mapa embebido | No |
| D7 | GPS | `watchPosition` recién al abrir el viaje. Si falla, la lista queda en orden cronológico, sin aviso de error | `ADR-IT5-003` | No |
| D8 | Pantallas | Ingreso, mis viajes, viaje, novedades, agencia, revisión y asistente. Sin cotización ni miembros | Regla 10 de la spec | No |

## Estructura de Código y Mapeo Arquitectónico

| Ruta | Elemento del paso 5 | Dependencias | Prohibiciones |
| :--- | :--- | :--- | :--- |
| `src/trotamundos/dominio/reserva.py` | Contrato `Reserva.lugar` | `pydantic` | No envía la posición del dispositivo |
| `src/trotamundos/movil/` | Cliente móvil, service worker y manifiesto | La app principal | No llama a otro host. No manda coordenadas del dispositivo |
| `src/trotamundos/app.py` | Sirve `/movil` | `StaticFiles` | — |
| `src/trotamundos/identidad/gateway/firma.py` | `/movil` es público, como `/web` | — | — |
| `tests/test_comp03_movil.py` | Los `AC-COMP-03-*` | Playwright | — |

## Tareas de Implementación

| ID | Descripción | AC | Depende de | Hecho cuando |
| :--- | :--- | :--- | :--- | :--- |
| `T-COMP-03-01` | `Lugar` en el contrato, la base y la analítica, aceptando el texto histórico | — | — | Un nombre solo se comporta como antes; con coordenadas se guarda y se lee el objeto |
| `T-COMP-03-02` | PWA: login, viajes, viaje, novedades, agencia, revisión, asistente, «Error 401» | `AC-COMP-03-09`, `AC-COMP-03-10`, `AC-COMP-03-11` | 01 | Manifiesto instalable y menú del asistente |
| `T-COMP-03-03` | Service worker y medición de pintura | `AC-COMP-03-01`, `AC-COMP-03-02` | 02 | FCP menor a 1,4 s y la segunda apertura sale de la copia local |
| `T-COMP-03-04` | Distancia, ruta y degradación, sin sacar las coordenadas del dispositivo | `AC-COMP-03-03` a `AC-COMP-03-08` | 02 | La más cercana se destaca; sin permiso no hay distancia ni error |

## Matriz de Cobertura de Criterios de Aceptación

| Criterio | Tarea | Test | Estado |
| :--- | :--- | :--- | :--- |
| `AC-COMP-03-01` | `T-COMP-03-03` | `test_AC_COMP_03_01_el_login_se_pinta_en_menos_de_1_4_s` | `[x] Verde` |
| `AC-COMP-03-02` | `T-COMP-03-03` | `test_AC_COMP_03_02_la_segunda_apertura_sale_de_la_copia_local` | `[x] Verde` |
| `AC-COMP-03-03` | `T-COMP-03-04` | `test_AC_COMP_03_03_el_login_no_pide_el_gps` | `[x] Verde` |
| `AC-COMP-03-04` | `T-COMP-03-04` | `test_AC_COMP_03_04_con_permiso_muestra_distancia_ruta_y_la_mas_cercana` | `[x] Verde` |
| `AC-COMP-03-05` | `T-COMP-03-04` | `test_AC_COMP_03_05_sin_permiso_muestra_el_itinerario_sin_distancia_ni_error` | `[x] Verde` |
| `AC-COMP-03-06` | `T-COMP-03-04` | `test_AC_COMP_03_06_la_reserva_sin_coordenadas_no_muestra_distancia` | `[x] Verde` |
| `AC-COMP-03-07` | `T-COMP-03-04` | `test_AC_COMP_03_07_las_coordenadas_del_dispositivo_no_salen_en_la_red` | `[x] Verde` |
| `AC-COMP-03-08` | `T-COMP-03-04` | `test_AC_COMP_03_08_sin_red_la_distancia_se_recalcula` | `[x] Verde` |
| `AC-COMP-03-09` | `T-COMP-03-02` | `test_AC_COMP_03_09_sin_permiso_muestra_error_401` | `[x] Verde` |
| `AC-COMP-03-10` | `T-COMP-03-02` | `test_AC_COMP_03_10_el_manifiesto_permite_instalar` | `[x] Verde` |
| `AC-COMP-03-11` | `T-COMP-03-02` | `test_AC_COMP_03_11_el_menu_del_asistente_no_es_un_error` | `[x] Verde` |

## Estrategia de Pruebas y Simulación de Fallos

* Chromium con Playwright. Red 3G simulada: 150 ms y 1,6 Mbit/s. Posición simulada con la geolocalización del navegador.
* Sin permiso, el viaje se ve en orden cronológico y la pantalla no dice «error».
* Con la red cortada, un cambio de posición recalcula la distancia sin un pedido nuevo.
* Comando: `.venv/bin/pytest tests/test_comp03_movil.py -m navegador`

## Riesgos Técnicos del Plan

* Un lugar que es solo un nombre se sigue viendo como texto en la API. El cliente móvil acepta las dos formas.
* La columna no cambió de tipo. Un lugar con coordenadas ocupa el mismo campo, en JSON.
