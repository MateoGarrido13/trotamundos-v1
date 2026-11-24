# PLAN-COMP-07. Novedades de Booking

* **Spec asociada:** [SPEC-COMP-07](../specs/SPEC-COMP-07.md) (aprobada)
* **Estado:** terminado (`OK PLAN`, 2026-11-23)
* **Fecha:** 2026-11-23
* **Incremento (Slice):** Slice 3 de [PLAN_MAESTRO.md](PLAN_MAESTRO.md)

Rama `comp-07`, desde `main` (`1b35aac`). **No se mergea a `main` hasta que lo diga el usuario.** Corre en paralelo con `comp-08`.

El aviso de Booking es un **anuncio de viaje nuevo** que ven todos los viajeros en «Novedades» (spec, «Decisiones tomadas»). Recorre: Booking simulado → listener → cola `novedades` del Broker → Servicio de ingesta → Orquestador → tabla `anuncio` → `GET /novedades/anuncios`. No toca reservas.

## Decisiones Técnicas Locales

Las que completan algo que la spec deja abierto las propone el asistente por la delegación general del usuario (2026-11-23). Ninguna cambia un ADR ni agrega un elemento de arquitectura.

| # | Decisión | Elegida | Motivo | ¿Afecta driver o requiere ADR? |
| :--- | :--- | :--- | :--- | :--- |
| D1 | Dónde vive el listener | Paquete nuevo `src/trotamundos/entrada/booking/` (nodos de entrada, `ADR-IT3-010`), con `aviso.py`, `adaptador.py`, `listener.py`, `tasa.py` y `simulado.py` | Es el mismo patrón que `entrada/agencia.py` y `entrada/api_agencia.py` | No |
| D2 | Forma del aviso | `{"aviso_id", "titulo", "destino", "inicio", "fin", "proveedor"}`, modelo `pydantic` estricto (`extra="forbid"`, textos de 1 a 200 caracteres, `fin` no anterior a `inicio`). Cualquier otra cosa: 422 | La spec fija el contenido («título, destino, fechas y proveedor») pero no los nombres de los campos | No |
| D3 | Identificador | `booking:<aviso_id>`, asignado por el listener | `ADR-IT3-003`: lo asigna quien publica; un repetido se descarta en la ingesta | No |
| D4 | Clave compartida | `ConfiguracionBooking.clave_proveedor` (`TROTA_CLAVE_BOOKING`), comparada con `hmac.compare_digest`. Vacía: ningún aviso es válido, igual que `TROTA_CLAVE_AGENCIA` | Patrón de `REF-05` | No |
| D5 | Tasa del listener | Ventana deslizante de 1 s por origen (dirección del cliente), 50 por segundo. Lo que excede recibe 429. Clase propia en `entrada/booking/tasa.py` | Evita que `entrada` importe `identidad` y respeta la frontera de `ADR-IT3-010` | No |
| D6 | Orden de las comprobaciones | clave (401) → tasa (429) → traducción (422) → publicar (202 o 503) | La clave se mira antes de tocar nada; un aviso inválido no gasta cola | No |
| D7 | Cola llena | `ColaLlena` se traduce en 503 con `Retry-After: 1`. El Broker ya avisa a operaciones al fallar la publicación (`AC-03`) | `ADR-IT3-009`: la reentrega es de Booking | No |
| D8 | Cómo se mide `QA-PER-01` | El listener estampa `detectado_en` en el mensaje; el Orquestador guarda `recibido_en` al escribir. El retraso es la diferencia | La spec mide «desde que el listener detecta» | No |
| D9 | Origen en la ingesta | Un tercer valor de `origen`: `"anuncio"`. La ingesta lo entrega a un puerto nuevo `EntregaAnuncios.guardar_anuncio` (en `dominio/puertos_anuncios.py`), con el mismo límite de tasa que las reservas | Reutiliza la deduplicación, el Retry y el límite de `ADR-IT3-010` sin tocar el resto | No |
| D10 | Tabla `anuncio` | `anuncio(id PK, titulo, destino, inicio, fin, proveedor, detectado_en, recibido_en)` en el esquema nuevo `07_anuncios.sql`. `INSERT … ON CONFLICT DO NOTHING`: es idempotente | Un anuncio repetido no se muestra dos veces (`AC-04`) | No |
| D11 | Lectura | `GET /novedades/anuncios` exige `X-Viajero-Id` (401 si falta), devuelve los de los últimos 30 días ordenados por `recibido_en` descendente, hasta 100 | La spec dice «Identidad» y «retención 30 días»; el tope es de prototipo | No |
| D12 | Ruta pública en el Gateway | `/proveedores/booking/avisos` se agrega a `RUTAS_PUBLICAS` de `identidad/gateway/firma.py` | El listener **no pasa por el API Gateway**: autentica con la clave. En el prototipo comparte proceso, así que se lo declara público | No |
| D13 | Contrato `IProveedor` | Se agrega `recibir_novedad(mensaje)` a `IProveedor` (`dominio/puertos_cotizacion.py`). Los tres adaptadores de cotización de `COMP-06` heredan una implementación por defecto que lanza `NotImplementedError` | `PLAN-COMP-06`, D3, lo dejó para este plan. La cotización no recibe novedades | No |
| D14 | Ping/Echo contra Booking | `AdaptadorBooking.ping()` y `verificar_eco()`: sin eco, avisa a operaciones (logger `trotamundos.operaciones` y lista `avisos`). Tarea periódica cada 60 s (`intervalo_eco_segundos`, nuevo) | `AC-08`; el intervalo lo fija el plan | No |
| D15 | Booking simulado | `BookingSimulado` en `entrada/booking/simulado.py`: `sin_eco`, `demora_segundos`, `caida`, generador de avisos y ráfaga que reintenta con 503 como haría Booking | `CON-02` y regla 8 | No |
| D16 | Bases de prueba separadas | Las pruebas con base de esta rama usan `comp07_test` (variables `TROTA_DSN_*` apuntando a ella) | Dos sesiones sobre `trotamundos_test` produjeron `DeadlockDetected` | No |

## Estructura de Código y Mapeo Arquitectónico

| Ruta en el repositorio | Elemento del paso 5 que instancia | Dependencias permitidas (imports) | Prohibiciones explícitas |
| :--- | :--- | :--- | :--- |
| `src/trotamundos/entrada/booking/aviso.py` | Capa anti-corrupción: `AvisoBooking` y su traducción a novedad | `pydantic`, biblioteca estándar | `persistencia`, `orquestador`, `config` |
| `src/trotamundos/entrada/booking/adaptador.py` | Adaptador de anuncios (Booking): `IProveedor` (`ping`, `traducir`, `recibir_novedad`), autenticación y publicación | `broker`, `config`, `dominio`, `entrada.booking.aviso`, `entrada.booking.tasa` | `persistencia`, `orquestador`, `identidad` |
| `src/trotamundos/entrada/booking/tasa.py` | Límite de tasa del listener | Biblioteca estándar | Todo `trotamundos.*` |
| `src/trotamundos/entrada/booking/listener.py` | Listener `POST /proveedores/booking/avisos` | `fastapi`, `entrada.booking.adaptador` | `persistencia`, `orquestador` |
| `src/trotamundos/entrada/booking/simulado.py` | API de Booking simulada (`CON-02`) | Biblioteca estándar, `entrada.booking.aviso` | `persistencia`, `orquestador`, `broker` |
| `src/trotamundos/dominio/puertos_anuncios.py` | Puerto `EntregaAnuncios` entre la ingesta y el Orquestador | Solo `dominio` | `config`, `broker`, `persistencia` |
| `src/trotamundos/entrada/ingesta.py` (se modifica) | Servicio de ingesta: origen `anuncio` | lo que ya importa, `dominio.puertos_anuncios` | `persistencia`, `orquestador` |
| `src/trotamundos/orquestador/anuncios.py` | Orquestador de viajes: guarda y lista anuncios | `persistencia`, `dominio` | `entrada`, `broker` |
| `src/trotamundos/orquestador/api_anuncios.py` | `GET /novedades/anuncios` | `fastapi`, `orquestador.anuncios` | `entrada` |
| `src/trotamundos/persistencia/repositorio_anuncios.py` y `esquemas/07_anuncios.sql` | Tabla `anuncio` | `persistencia.base_viajes` | `orquestador`, `entrada` |
| `src/trotamundos/dominio/puertos_cotizacion.py` y `cotizacion/adaptadores.py` (se modifican) | `IProveedor.recibir_novedad` (D13) | — | — |
| `src/trotamundos/identidad/gateway/firma.py` (se modifica) | Ruta pública del listener (D12) | — | — |
| `src/trotamundos/config.py`, `composicion.py`, `app.py`, `tests/test_arquitectura.py` (se modifican) | `ConfiguracionBooking`, `ensamblar_booking`, montaje, reglas | — | — |

Reglas nuevas de arquitectura: `entrada/booking` sin `persistencia`, `orquestador`, `identidad`, `cotizacion` y `analitica`; `entrada/booking/tasa` y `entrada/booking/aviso` sin `trotamundos.*` salvo `dominio`; `entrada/booking/simulado` sin `broker`; `orquestador/anuncios` sin `entrada` y `broker`; `dominio/puertos_anuncios` sin `config`.

Parámetros nuevos (`ConfiguracionBooking`, variables `TROTA_*`): `clave_proveedor` (`TROTA_CLAVE_BOOKING`, sin `repr`), `tasa_avisos_por_origen` 50, `retencion_anuncios_dias` 30, `intervalo_eco_segundos` 60 (nuevo) y `tope_listado_anuncios` 100 (nuevo). El `limite_entrega_ingesta` es el que ya fija `ConfiguracionIngesta.tasa_por_segundo`.

## Tareas de Implementación

| ID | Descripción de la tarea | Archivos a crear / modificar | AC que cubre | Depende de | Criterio de terminado (Done) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `T-COMP-07-01` | `ConfiguracionBooking`, reglas de arquitectura, `IProveedor.recibir_novedad` con su valor por defecto en la cotización, y la ruta pública del Gateway | `config.py`, `tests/test_arquitectura.py`, `dominio/puertos_cotizacion.py`, `cotizacion/adaptadores.py`, `identidad/gateway/firma.py` | `AC-COMP-07-09` | — | Los tests de arquitectura y los de `COMP-06` siguen en verde |
| `T-COMP-07-02` | Modelo `AvisoBooking`, traducción a novedad y `BookingSimulado` (eco, demora, caída, ráfaga con reentrega) | `entrada/booking/aviso.py`, `entrada/booking/simulado.py`, `tests/test_comp07_aviso.py` | `AC-COMP-07-10` | 01 | Un aviso mal formado no se traduce; el simulado reproduce las fallas |
| `T-COMP-07-03` | `AdaptadorBooking` y listener: clave, tasa, traducción, publicación, 202/401/422/429/503 y aviso a operaciones | `entrada/booking/adaptador.py`, `entrada/booking/tasa.py`, `entrada/booking/listener.py`, `tests/test_comp07_listener.py` | `AC-COMP-07-01`, `AC-COMP-07-02`, `AC-COMP-07-03`, `AC-COMP-07-10` | 02 | Cada código de respuesta responde a su caso y solo el 202 publica |
| `T-COMP-07-04` | Ping/Echo contra Booking y tarea periódica | `entrada/booking/adaptador.py`, `tests/test_comp07_eco.py` | `AC-COMP-07-08` | 03 | Sin eco hay un aviso a operaciones |
| `T-COMP-07-05` | Tabla `anuncio`, repositorio, `ServicioAnuncios`, puerto `EntregaAnuncios`, origen `anuncio` en la ingesta y `GET /novedades/anuncios` | `persistencia/esquemas/07_anuncios.sql`, `persistencia/repositorio_anuncios.py`, `orquestador/anuncios.py`, `orquestador/api_anuncios.py`, `dominio/puertos_anuncios.py`, `entrada/ingesta.py`, `tests/test_comp07_anuncios.py` | `AC-COMP-07-04`, `AC-COMP-07-05` | 03 | El aviso llega a la lista; repetido, aparece una vez |
| `T-COMP-07-06` | Composición: `ensamblar_booking`, consumidor ya existente de `novedades`, montaje en `app.py` y tarea del eco | `composicion.py`, `app.py`, `tests/test_comp07_punta_a_punta.py` | `AC-COMP-07-05` (extremo a extremo), `AC-COMP-07-09` | 04, 05 | Con la app armada, un aviso por HTTP termina en `GET /novedades/anuncios` y el retraso medio es de segundos |
| `T-COMP-07-07` | Ráfaga de las 8 am: la ingesta respeta su límite y la cotización no se degrada | `tests/test_comp07_rafaga.py` (marca `carga`) | `AC-COMP-07-06`, `AC-COMP-07-07` | 06 | El ritmo de entrega no supera `tasa_por_segundo`; el p90 de la cotización con ráfaga no empeora más del 10 % respecto de sin ráfaga |

## Matriz de Cobertura de Criterios de Aceptación

| Criterio de Aceptación (Spec) | Tarea(s) del Plan | Nombre del test automatizado | Estado |
| :--- | :--- | :--- | :--- |
| `AC-COMP-07-01` | `T-COMP-07-03` | `test_AC_COMP_07_01_un_aviso_valido_queda_en_la_cola_con_su_identificador` | `[x] Verde` |
| `AC-COMP-07-02` | `T-COMP-07-03` | `test_AC_COMP_07_02_clave_invalida_es_401_y_no_publica` | `[x] Verde` |
| `AC-COMP-07-03` | `T-COMP-07-03` | `test_AC_COMP_07_03_cola_llena_es_503_y_avisa_a_operaciones` | `[x] Verde` |
| `AC-COMP-07-04` | `T-COMP-07-05` | `test_AC_COMP_07_04_el_mismo_aviso_dos_veces_se_muestra_una_sola_vez` | `[x] Verde` |
| `AC-COMP-07-05` | `T-COMP-07-05`, `T-COMP-07-06` | `test_AC_COMP_07_05_el_anuncio_llega_a_novedades_con_retraso_menor_a_5_minutos` | `[x] Verde` |
| `AC-COMP-07-06` | `T-COMP-07-07` | `test_AC_COMP_07_06_la_rafaga_no_supera_el_limite_de_entrega` | `[x] Verde` |
| `AC-COMP-07-07` | `T-COMP-07-07` | `test_AC_COMP_07_07_la_cotizacion_no_se_degrada_con_la_rafaga` | `[x] Verde` |
| `AC-COMP-07-08` | `T-COMP-07-04` | `test_AC_COMP_07_08_sin_eco_se_avisa_a_operaciones` | `[x] Verde` |
| `AC-COMP-07-09` | `T-COMP-07-01`, `T-COMP-07-06` | `test_AC_COMP_07_09_el_listener_solo_importa_el_broker` | `[x] Verde` |
| `AC-COMP-07-10` | `T-COMP-07-02`, `T-COMP-07-03` | `test_AC_COMP_07_10_un_aviso_que_no_se_traduce_es_422_y_no_entra_a_la_cola` | `[x] Verde` |

Notas: `AC-04` y `AC-05` necesitan las bases (marca `db`). `AC-06` usa un reloj y una espera inyectables en `LimitadorTasa`, así que no espera tiempo real. Además de lo anterior hay tests de la clave (comparación de tiempo constante), de la tasa (429) y de la ruta pública del Gateway con `exigir_gateway=True`.

Cambios respecto de lo planeado al implementar:
* El listener lee el cuerpo **después** de autenticar la clave (con `request.json()` y no con `Body`), así un aviso con clave inválida es siempre 401 aunque su cuerpo sea ilegible (D6). `AdaptadorBooking.autenticar` y `cuerpo_valido` son públicos por eso.
* `BookingSimulado.enviar` y `rafaga` reentregan ante 429 y 503 con una espera inicial configurable. Las ráfagas de los tests usan 0,3 s y 6 reintentos: con 90 avisos desde un solo origen y 50 por segundo permitidos, la reentrega tiene que dejar pasar la ventana de 1 s del listener.
* `tests/conftest.py`: `limpiar_base` también borra la tabla `anuncio`.
* Tests agregados además de la matriz: `test_comp07_gateway.py` (D12, sin base) y varios de la lista, la tasa, el tope y la retención.
* Suite completa con la base aislada `comp07_test`: 796 pasan y 2 fallan (`test_AC_COMP_01_10…` y `test_ref06_modelo::…analitica_es_una_base_distinta…`) solo porque comparan el nombre de la base con `trotamundos_test`; con la base por defecto pasan (verificado). Una primera corrida mostró errores sueltos de `test_ref05_reportar` que no se repitieron (el archivo pasa solo, 17 tests); eran contención con otra sesión.
* `AC-COMP-07-07` mide el p90 de 200 cotizaciones en oleadas, con y sin la ráfaga de 90 avisos corriendo (ingesta con su límite real de 20 por segundo y escritura real en la base): 0,306 s en las dos.

## Estrategia de Pruebas y Simulación de Fallos

* **Archivos:** `tests/test_comp07_*.py` y `tests/comp07_util.py` (la app armada, el cliente HTTP sobre `ASGITransport`, Booking simulado y los avisos de ejemplo).
* **Inyección de fallos:** cola llena (`Broker` con tamaño 1 o 2), Booking sin eco, caída y demora, aviso mal formado, clave errónea y ráfaga por encima de la tasa.
* **Retraso de `QA-PER-01`:** se leen `detectado_en` y `recibido_en` de la tabla y se promedia; el criterio es menos de 300 s (en el test serán fracciones de segundo).
* **Cotización con ráfaga (`AC-07`):** el p90 de 200 cotizaciones con la ráfaga corriendo en el mismo bucle de eventos contra el p90 sin ráfaga; es la forma de comprobar el desacople que pide `ADR-IT3-010`.
* **Bases:** `comp07_test`, creada una sola vez en los tres contenedores (`createdb` por los puertos 5433, 5434 y 5435), con `TROTA_DSN_VIAJES_PRIMARIA`, `TROTA_DSN_VIAJES_PASIVA` y `TROTA_DSN_ANALITICA` apuntando a ella.
* **Comando de ejecución:** `pytest tests/test_comp07_*.py tests/test_arquitectura.py`. Antes de terminar, la suite completa, con ninguna otra sesión corriendo sobre las mismas bases.

## Riesgos Técnicos del Plan

* **Choque con `comp-08`, y con lo que suba el compañero, en `config.py`, `composicion.py`, `app.py` y `test_arquitectura.py`:** son los mismos archivos. Mitigación: bloques nuevos y aislados, y un `git merge main` solo cuando el usuario lo indique. No se mergea a `main` desde esta rama.
* **El modelo de la cola de novedades es compartido con `REF-03` y `REF-05`:** un tercer `origen` no debe romper a los otros dos. Mitigación: tests de la ingesta existentes y uno nuevo que mezcla los tres orígenes en la misma cola.
* **La ráfaga contra la cotización depende de la máquina:** el criterio es relativo (no más del 10 % sobre la línea base medida en la misma corrida), no un valor absoluto.
* **El listener público comparte proceso con el resto:** en el prototipo un fallo del listener es un fallo de la app. Es la simplificación que la spec ya acepta para el despliegue.
* **Cambio en `IProveedor` (D13):** toca archivos de `COMP-06`. Mitigación: es solo agregar un método con valor por defecto, y los tests de `COMP-06` corren completos en `T-COMP-07-01`.
