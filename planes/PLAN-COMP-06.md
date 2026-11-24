# PLAN-COMP-06. Cotización resiliente

* **Spec asociada:** [SPEC-COMP-06](../specs/SPEC-COMP-06.md) (aprobada)
* **Estado:** terminado (`OK PLAN`, 2026-11-23)
* **Fecha:** 2026-11-23
* **Incremento (Slice):** Slice 2 de [PLAN_MAESTRO.md](PLAN_MAESTRO.md)

La cotización no usa el Broker ni ninguna base (`AC-COMP-06-12`). Todos sus tests corren sin Docker.

## Decisiones Técnicas Locales

Ninguna agrega un elemento de arquitectura ni cambia un ADR. Las decisiones D4, D5, D7, D10, D12, D13 y D14 completan algo que la spec deja abierto. **El usuario delegó esas decisiones en el asistente (2026-11-23)** y quedan registradas en la tabla de abajo, con la alternativa que se descartó.

### Decisiones tomadas por delegación del usuario

| # | Qué dejaba abierto la spec | Alternativa descartada | Por qué la elegida |
| :--- | :--- | :--- | :--- |
| D4 | Qué significa que una copia sea «vigente» | Consultar siempre al Orquestador y usar la copia solo si vence la cota | El Paso 5 dice que la Caché, si tiene la grilla, la devuelve. Consultar siempre anularía la caché y no ayudaría a `QA-PER-02` |
| D5 | Cómo se presenta «cotización en curso» | Un `404` o un texto libre en lugar de la grilla | Un campo más mantiene una sola forma de respuesta para el cliente y no obliga a ramificar por código de estado |
| D7 | Qué grillas se guardan | Guardar solo las completas | Con un proveedor caído (el caso que se quiere resistir) nunca habría copia que servir |
| D10 | Intervalo del eco y reingreso del nodo | Que el nodo caído no vuelva hasta reiniciar | Un nodo que se recupera debe volver (`QA-DIS-01`: menos de 5 minutos de inactividad al mes). 1 s es la mitad de la cota del borde |
| D12 | Cómo se avisa a operaciones | Publicar en una cola del Broker | La cotización no usa el Broker (`AC-12`). Un log y una lista leíble bastan para demostrarlo |
| D13 | Valores válidos de los parámetros | Listas cerradas de hospedajes y compañías | La spec no las define y una lista cerrada sería inventar datos de negocio |
| D14 | Tope de la caché | Sin tope | Evita que el prototipo crezca sin límite en la prueba de carga |

| # | Decisión | Elegida | Motivo | ¿Afecta driver o requiere ADR? |
| :--- | :--- | :--- | :--- | :--- |
| D1 | Concurrencia | `asyncio`: `asyncio.gather` para el Scatter-Gather y `asyncio.wait_for` para la cota de cada adaptador | Es el stack del PLAN_MAESTRO §2 | No |
| D2 | Paquete | `src/trotamundos/cotizacion/` nuevo; contratos y modelo en `dominio/`. Solo `composicion.py` conecta las piezas | Replica el patrón de `asistente/` y `analitica/` | No |
| D3 | Contrato `IProveedor` | Declara `ping()` y `traducir(mensaje)`. **`recibirNovedad` lo agrega COMP-07**, que corre en paralelo | Evita que dos ramas editen el mismo `Protocol` a la vez | No. Punto de coordinación con COMP-07 |
| D4 | Qué es «vigencia» de la copia | Copia con edad ≤ `vigencia_copia_segundos` (300): **hit directo**, se devuelve sin llamar al Orquestador, con `copia: true` (el Paso 5 dice «si tiene la grilla, la devuelve»). Copia más vieja: se pide la fresca y, **si la cota vence, se entrega la vieja** (`ADR-IT2-001`) | Es la única lectura donde `AC-04` y `AC-05` tienen sentido a la vez | No |
| D5 | «Cotización en curso» | La grilla lleva además `en_curso: bool`. Una grilla sin ningún origen `ok` (todos `no_respondio` o ninguno armado al vencer la cota) se presenta como `en_curso: true` y `origenes` con lo que haya. No se guarda en la caché | La spec exige ese aviso pero no define su forma. Agregar un campo no quita ninguno de los tres del contrato | No |
| D6 | Grilla parcial al vencer la cota | El Orquestador escribe cada origen que responde en un objeto `ProgresoGrilla`, que le pasa la Caché de borde. Al vencer la cota la Caché toma lo que haya | Es «la grilla parcial que el Orquestador ya armó» (`ADR-IT2-002`) sin acoplar la caché al servicio | No |
| D7 | Qué se guarda en la caché | Toda grilla fresca con al menos un origen `ok`, completa o parcial, con su marca `completa`. Una copia parcial vence igual a los 300 s | La spec no distingue. Guardar solo completas dejaría sin copia a la mayoría de los casos con un proveedor caído | No |
| D8 | Respuesta fresca tardía | La Caché lanza la consulta como tarea, espera hasta la cota con `asyncio.wait` (sin cancelar) y deja un `done_callback` que guarda la copia (`AC-05`). El callback lee la excepción para que no quede sin retirar | `asyncio.wait_for` cancelaría la consulta y perdería la actualización | No |
| D9 | Reloj | La Caché recibe `reloj: Callable[[], float]` (por defecto `time.monotonic`) | Envejecer una copia en un test sin esperar 300 s | No |
| D10 | Health check | Tarea periódica del Balanceador cada `intervalo_eco_ms` (1000, nuevo). Un nodo que vuelve a dar eco **reingresa** a la rotación | La spec no da el intervalo ni dice si el nodo vuelve | No |
| D11 | Pedido en vuelo hacia un nodo que cae | El nodo lanza `NodoCaido`. El Balanceador lo marca caído, avisa a operaciones y reenvía a otro sano, dentro de la cota del borde (no tiene cota propia). El `ProgresoGrilla` se reinicia en el reenvío | Es de solo lectura: repetir no duplica nada (`QA-DIS-01`) | No |
| D12 | «Avisa a operaciones» | `logging` en el logger `trotamundos.operaciones` (nivel `ERROR`) y una lista `avisos` en el Balanceador que los tests leen | La spec no define el canal. Se evita usar el Broker (`AC-12`) | No |
| D13 | Parámetros del `GET` | `fecha` en `YYYY-MM-DD`; `hospedaje` y `compania` cadenas no vacías de hasta 100 caracteres, sin lista cerrada. Otro caso: 422 | La spec no define los valores válidos | No |
| D14 | Tope de la caché | `max_copias = 1000` (nuevo), se descarta la más antigua | Sin tope la caché del prototipo crece sin límite | No |
| D15 | Formato de cada API simulada | La de aerolíneas responde un texto SOAP/XML (lo interpreta `xml.etree` de la biblioteca estándar). Hoteles y arrendadoras responden JSON con claves distintas entre sí | Hace real el trabajo de la Capa anti-corrupción (`ADR-007`) | No |
| D16 | Tiempos de los tests | Reales, sin escala. Los de demora usan 100 a 300 ms | Las cotas son de 500 a 800 ms. Toda la suite de COMP-06 debería tardar menos de 15 s | No |

## Estructura de Código y Mapeo Arquitectónico

| Ruta en el repositorio | Elemento del paso 5 que instancia | Dependencias permitidas (imports) | Prohibiciones explícitas |
| :--- | :--- | :--- | :--- |
| `src/trotamundos/dominio/cotizacion.py` | Modelo interno: `Criterios`, `Precio`, `ResultadoOrigen`, `Grilla`, `ProgresoGrilla` | Solo la biblioteca estándar | `config`, `broker`, `persistencia`, `orquestador` |
| `src/trotamundos/dominio/puertos_cotizacion.py` | `IProveedor`, `ICotizadorHotel`, `IProveedorInventario`, `IProveedorArrendadora`; `INodo`, `IDespachador` | `dominio.cotizacion` | `config`, `orquestador` |
| `src/trotamundos/cotizacion/apis_simuladas.py` | API Proveedor 2 (SOAP), API de hoteles, API de arrendadoras (`CON-02`) | Biblioteca estándar | Todo `trotamundos.*` salvo `dominio` |
| `src/trotamundos/cotizacion/adaptadores.py` | Adaptador de aerolíneas, de hoteles y de arrendadoras (Capa anti-corrupción, Ping/Echo, cota) | `dominio`, `config` | `servicio`, `borde`, `balanceador`, `broker`, `persistencia` |
| `src/trotamundos/cotizacion/servicio.py` | Orquestador de viajes, en su rol de cotización (Scatter-Gather, Graceful degradation) | `dominio` | **`cotizacion.adaptadores`** (recibe los cotizadores por contrato: `AC-09`), `broker`, `persistencia` |
| `src/trotamundos/cotizacion/nodo.py` | Nodo del Orquestador de viajes (Redundant spare) | `dominio`, `cotizacion.servicio` | `broker`, `persistencia` |
| `src/trotamundos/cotizacion/balanceador.py` | Balanceador de Carga (health check, Reconfiguration, reenvío) | `dominio`, `config` | `cotizacion.borde`, `cotizacion.nodo`, `broker`, `persistencia` |
| `src/trotamundos/cotizacion/borde.py` | Caché de borde (CDN): cota de 800 ms, copia, degradación | `dominio`, `config` | `cotizacion.balanceador` (recibe un `IDespachador`), `broker`, `persistencia` |
| `src/trotamundos/cotizacion/api.py` | Entrada `GET /cotizaciones` (API Gateway) | `dominio`, `fastapi` | `broker`, `persistencia`, `orquestador` |
| `src/trotamundos/config.py` (se modifica) | Parámetros de la spec | — | — |
| `src/trotamundos/composicion.py` (se modifica) | `ensamblar_cotizacion(...)`: único lugar que conecta las piezas | todo `cotizacion` | — |
| `src/trotamundos/app.py` (se modifica) | Monta el router y la tarea de health check | — | — |
| `tests/test_arquitectura.py` (se modifica) | Reglas de frontera de este plan | — | — |

Reglas nuevas para `tests/test_arquitectura.py`: todo `cotizacion` sin `broker`, `persistencia`, `psycopg`, `orquestador`, `entrada`, `analitica`, `asistente` y `composicion`; `orquestador` sin `cotizacion`; `cotizacion/servicio` sin `cotizacion.adaptadores`; `cotizacion/borde` y `cotizacion/balanceador` sin importarse entre sí; `dominio/cotizacion` y `dominio/puertos_cotizacion` sin `config`.

Parámetros nuevos en `ConfiguracionCotizacion` (`config.py`, variables `TROTA_*`): `cota_cotizacion_ms` 800, `cota_aerolineas_ms` 600, `cota_hoteles_ms` 500, `cota_arrendadoras_ms` 500, `vigencia_copia_segundos` 300, `nodos_cotizacion` 2, y los dos propuestos `intervalo_eco_ms` 1000 y `max_copias` 1000.

## Tareas de Implementación

| ID | Descripción de la tarea | Archivos a crear / modificar | AC que cubre | Depende de | Criterio de terminado (Done) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `T-COMP-06-01` | Modelo y contratos del dominio, `ConfiguracionCotizacion` y las reglas de arquitectura | `dominio/cotizacion.py`, `dominio/puertos_cotizacion.py`, `config.py`, `tests/test_arquitectura.py` | `AC-COMP-06-12` | — | `test_arquitectura.py` en verde con las reglas nuevas; la config se lee por entorno |
| `T-COMP-06-02` | Las tres APIs simuladas (demora, caída, sin eco, contador de llamadas) y los tres adaptadores: traducción, ping antes del precio, cota propia, sin Retry | `cotizacion/apis_simuladas.py`, `cotizacion/adaptadores.py`, `tests/comp06_util.py` | `AC-COMP-06-03`, `AC-COMP-06-07`, `AC-COMP-06-08` | 01 | Sin eco no se pide precio; con demora mayor que la cota se corta; cada falla produce una sola llamada |
| `T-COMP-06-03` | `ServicioCotizacion`: Scatter-Gather sobre los cotizadores registrados, `ProgresoGrilla`, marca de origen (`ok`, `no_respondio`), `completa` y `en_curso` | `cotizacion/servicio.py` | `AC-COMP-06-01`, `AC-COMP-06-02`, `AC-COMP-06-09` | 02 | Tres de 300 ms tardan menos de 800 ms. Un caído sale parcial. Un hotel nuevo registrado sin tocar `servicio.py` aparece en la grilla |
| `T-COMP-06-04` | `NodoCotizacion` y `Balanceador`: eco periódico, salida y reingreso de la rotación, reenvío del pedido en vuelo, aviso a operaciones | `cotizacion/nodo.py`, `cotizacion/balanceador.py` | `AC-COMP-06-10` | 03 | Un nodo sin eco sale de rotación; el pedido en vuelo se reenvía a otro y llega a tiempo; hay un aviso |
| `T-COMP-06-05` | `CacheBorde`: cota de 800 ms desde que recibe el pedido, hit con copia vigente, copia vencida como respuesta por defecto, grilla parcial, «en curso» y actualización con la respuesta tardía | `cotizacion/borde.py` | `AC-COMP-06-04`, `AC-COMP-06-05`, `AC-COMP-06-06` | 03, 04 | Los tres escenarios responden en menos de 800 ms; la respuesta tardía actualiza la copia |
| `T-COMP-06-06` | `GET /cotizaciones` con validación (422), `ensamblar_cotizacion` y montaje en `app.py` junto con la tarea de health check | `cotizacion/api.py`, `composicion.py`, `app.py`, `tests/test_comp06_api.py` | `AC-COMP-06-01` (extremo a extremo), `AC-COMP-06-12` | 05 | El endpoint devuelve `{origenes, completa, copia, en_curso}`; los tests de `COMP-01` siguen en verde |
| `T-COMP-06-07` | Prueba de carga: 1.000 pedidos concurrentes, criterios distintos para no usar la caché | `tests/test_comp06_carga.py` (marca `carga`) | `AC-COMP-06-11` | 06 | El percentil 90 es de 800 ms o menos |

## Matriz de Cobertura de Criterios de Aceptación

| Criterio de Aceptación (Spec) | Tarea(s) del Plan | Nombre del test automatizado | Estado |
| :--- | :--- | :--- | :--- |
| `AC-COMP-06-01` | `T-COMP-06-03`, `T-COMP-06-06` | `test_AC_COMP_06_01_tres_proveedores_en_paralelo_no_suman` | `[x] Verde` |
| `AC-COMP-06-02` | `T-COMP-06-03` | `test_AC_COMP_06_02_proveedor_caido_da_grilla_parcial` | `[x] Verde` |
| `AC-COMP-06-03` | `T-COMP-06-02` | `test_AC_COMP_06_03_demora_mayor_que_la_cota_se_corta` | `[x] Verde` |
| `AC-COMP-06-04` | `T-COMP-06-05` | `test_AC_COMP_06_04_cota_vencida_entrega_la_copia` | `[x] Verde` |
| `AC-COMP-06-05` | `T-COMP-06-05` | `test_AC_COMP_06_05_respuesta_tardia_actualiza_la_copia` | `[x] Verde` |
| `AC-COMP-06-06` | `T-COMP-06-05` | `test_AC_COMP_06_06_sin_copia_y_sin_origenes_responde_en_curso` | `[x] Verde` |
| `AC-COMP-06-07` | `T-COMP-06-02` | `test_AC_COMP_06_07_sin_eco_no_se_pide_precio` | `[x] Verde` |
| `AC-COMP-06-08` | `T-COMP-06-02` | `test_AC_COMP_06_08_sin_reintento_dentro_del_pedido` | `[x] Verde` |
| `AC-COMP-06-09` | `T-COMP-06-03` | `test_AC_COMP_06_09_hotel_nuevo_no_modifica_el_orquestador` | `[x] Verde` |
| `AC-COMP-06-10` | `T-COMP-06-04` | `test_AC_COMP_06_10_nodo_sin_eco_sale_y_se_reenvia_lo_que_estaba_en_vuelo` | `[x] Verde` |
| `AC-COMP-06-11` | `T-COMP-06-07` | `test_AC_COMP_06_11_percentil_90_en_800_ms_con_mil_pedidos` | `[x] Verde` |
| `AC-COMP-06-12` | `T-COMP-06-01`, `T-COMP-06-06` | `test_AC_COMP_06_12_cotizacion_no_usa_broker_ni_base` | `[x] Verde` |

`AC-09` tiene dos partes: el test funcional (un hotel nuevo registrado aparece en la grilla) y la regla de `test_arquitectura.py` (`cotizacion/servicio` no importa `cotizacion.adaptadores`). `AC-12` se verifica con la regla de arquitectura de `T-COMP-06-01`, que también cubre los módulos agregados en `T-COMP-06-06`.

## Estrategia de Pruebas y Simulación de Fallos

* **Archivos:** `tests/test_comp06_adaptadores.py`, `_servicio.py`, `_balanceador.py`, `_borde.py`, `_api.py` y `_carga.py`, más `tests/comp06_util.py` (fábricas de proveedores, nodos y reloj controlable).
* **Inyección de demora y caída:** cada API simulada tiene `demora_segundos`, `caida` y `sin_eco`, y cuenta sus llamadas de `ping` y de precio (para `AC-07` y `AC-08`). El nodo tiene `demora_segundos`, `sin_eco` y `caer_en_vuelo`.
* **Tiempos:** se mide con `time.perf_counter()` y se compara contra 800 ms. Los márgenes son de al menos 100 ms para no depender de la máquina.
* **`AC-04` y `AC-05`:** el reloj inyectable envejece la copia más allá de los 300 s, y el nodo con demora hace que la respuesta fresca pase de los 800 ms. Después se espera la tarea tardía y se vuelve a pedir.
* **`AC-11`:** pedidos con fechas distintas, sin repetir criterios. Corre con el marcador `carga`, igual que la prueba de carga de REF-06.
* **Comando de ejecución:** `pytest tests/test_comp06_*.py tests/test_arquitectura.py` (sin Docker). Antes de terminar, la suite completa.

## Riesgos Técnicos del Plan

* **Choque con COMP-05 en `config.py`, `composicion.py` y `app.py`:** los dos planes tocan esos archivos. Mitigación: los cambios de este plan son bloques nuevos y aislados (`ConfiguracionCotizacion`, `ensamblar_cotizacion`, un `include_router`), y se hace un `git merge main` antes de cerrar `T-COMP-06-06`.
* **`IProveedor` compartido con COMP-07:** si COMP-07 declara `recibirNovedad` en otro archivo, hay que unificar. Mitigación: avisar la ruta `dominio/puertos_cotizacion.py` al implementar COMP-07.
* **Tests sensibles al tiempo:** una máquina lenta puede romper `AC-01` y `AC-11`. Mitigación: márgenes de 100 ms o más y proveedores simulados de 300 ms como máximo; `AC-11` mide el percentil 90 y no el máximo.
* **Tareas en segundo plano de la Caché (D8):** si la consulta tardía falla, no debe dejar una excepción sin leer ni una tarea colgada al cerrar. Mitigación: `done_callback` que lee la excepción y un `cerrar()` que espera las tareas pendientes, con test.
* **Los 250.000 usuarios concurrentes no se reproducen:** es una simplificación aprobada en la spec; `AC-11` verifica el percentil 90 con 1.000 pedidos.
