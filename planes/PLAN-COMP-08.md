# PLAN-COMP-08. Notificaciones por canales (`ICanal`)

* **Spec asociada:** [SPEC-COMP-08](../specs/SPEC-COMP-08.md) (aprobada)
* **Estado:** terminado
* **Fecha:** 2026-11-23
* **Incremento (Slice):** Slice 3 de [PLAN_MAESTRO.md](PLAN_MAESTRO.md)

Rama `comp-08`, desde `main` (`1b35aac`). **No se mergea a `main` hasta que lo diga el usuario.** Corre en paralelo con `comp-07`.

Hoy la cola `notificaciones` existe y [SPEC-COMP-05](../specs/SPEC-COMP-05.md) ya publica en ella el correo de recuperación y el aviso al titular (`{"id", "canal": "email", "destinatario", "propuesta": {"asunto", "cuerpo"}}`), pero **no tiene consumidor** y la publicación no reintenta con la cola llena. Este plan agrega ambas cosas, más los tres canales simulados.

## Decisiones Técnicas Locales

Las que completan algo que la spec deja abierto las propone el asistente por la delegación general del usuario (2026-11-23). Ninguna cambia un ADR ni agrega un elemento de arquitectura.

| # | Decisión | Elegida | Motivo | ¿Afecta driver o requiere ADR? |
| :--- | :--- | :--- | :--- | :--- |
| D1 | Contrato | `ICanal` en `dominio/puertos_notificaciones.py`: `nombre: str` y `async enviar(destinatario, propuesta)`. `Propuesta` es `{asunto, cuerpo}`. La spec dice «síncrona»; en el prototipo es `async` porque todo el sistema corre sobre `asyncio` | Una espera de red no puede bloquear el bucle | No |
| D2 | Un consumidor por canal | `Broker.procesar_uno(cola, handler, *, donde=None)` gana un parámetro opcional: toma el primer mensaje que cumple `donde`. El servicio registra **un consumidor por canal** (cada uno solo toma sus pedidos) y uno más para los pedidos sin canal registrado | Así el Retry, los muertos y el aviso son los del Broker (`ADR-IT3-003`) y un canal lento solo atrasa a su propio consumidor (`AC-04`, `AC-10`). Reintentar dentro de un único consumidor atrasaría a los demás durante 1, 2 y 4 s | No. Cambio aditivo en `broker/broker.py`, sin efecto sobre quien no lo usa |
| D3 | Canal nuevo = un archivo | Cada canal vive en `notificaciones/canales/<nombre>.py` y se registra con el decorador `@canal("<nombre>")`. `canales/__init__.py` descubre e importa todos los módulos del paquete. La configuración `canales` por defecto es «todos los descubiertos» | `AC-02`: sumar Instagram es crear `instagram.py`; no cambia ni la composición ni la configuración ni Email ni WhatsApp | No |
| D4 | Pedido sin canal registrado | El consumidor «sin canal» lo manda **directo** a mensajes muertos (`Broker.enviar_a_muertos`, que avisa a operaciones), sin reintentos | `AC-08`: no tiene sentido reintentar un canal que no existe | No |
| D5 | Sin duplicar | El servicio recuerda los identificadores ya enviados (con la retención de la ingesta, 7 días) y los marca **después** de enviar. Un duplicado se descarta sin enviar | `ADR-IT3-003`, `AC-06`. Igual que en `ServicioIngesta` | No |
| D6 | Publicador con reintento | `PublicadorNotificaciones` en `orquestador/notificaciones.py`: valida el pedido, publica y, con la cola llena, reintenta tras 1, 2 y 4 s; al agotarlos manda el pedido a muertos con aviso. Imita a `EmisorEventos` | `AC-07` y el patrón de `REF-06` | No |
| D7 | Publicar desde hilos | Los servicios de `COMP-05` corren en hilos del servidor, así que `publicar_desde_hilo` intenta publicar al instante y, si la cola está llena, programa los reintentos en el bucle de eventos con `run_coroutine_threadsafe`. El bucle se enlaza al arrancar la app | Reemplaza el `broker.publicar` directo de `app.py` sin cambiar el código de `COMP-05` | No |
| D8 | Validación del pedido | `id` no vacío, `canal` no vacío, `destinatario` no vacío y `propuesta` con `asunto` y `cuerpo` de texto. Un pedido inválido lanza `ValueError` en el publicador y no entra a la cola | La spec define la forma y no el rechazo | No |
| D9 | Contenido intacto | El servicio pasa `propuesta` tal cual; no arma textos (regla 8) | Regla 8 | No |
| D10 | Canales simulados | Un `CanalSimulado` base con `demora_segundos`, `caida`, registro de los envíos y contador de llamadas. Email, WhatsApp e Instagram lo extienden. Ninguno tiene credenciales | `CON-02`, regla 7 | No |
| D11 | Tamaño de la cola | `Broker(..., tamanos={NOTIFICACIONES: tamano_cola_notificaciones})`, 100 por defecto (5 en los tests) | `ADR-IT3-002` | No |
| D12 | Supervisión | Cada consumidor se registra en el `Supervisor` existente con el nombre `notificaciones:<canal>`. Si hay un canal más, hay un consumidor más; la composición lo recorre sin conocer los nombres | Regla 1 y `AC-02` | No |
| D13 | Bases de prueba separadas | Los tests con base de esta rama (solo `AC-09`) usan `comp08_test` | Dos sesiones sobre `trotamundos_test` produjeron `DeadlockDetected` | No |

## Estructura de Código y Mapeo Arquitectónico

| Ruta en el repositorio | Elemento del paso 5 que instancia | Dependencias permitidas (imports) | Prohibiciones explícitas |
| :--- | :--- | :--- | :--- |
| `src/trotamundos/dominio/puertos_notificaciones.py` | `ICanal` y el modelo `Propuesta` | Solo `dominio` y la biblioteca estándar | `config`, `broker`, `persistencia`, `orquestador` |
| `src/trotamundos/notificaciones/servicio.py` | Servicio de notificaciones: consumidores por canal, deduplicación | `broker`, `dominio.puertos_notificaciones`, `config` | `persistencia`, `orquestador`, `entrada`, `identidad`, y **ningún módulo de `notificaciones/canales`** (recibe los canales por contrato) |
| `src/trotamundos/notificaciones/canales/__init__.py` | Registro y descubrimiento de canales (`@canal`) | `dominio.puertos_notificaciones`, `importlib`, `pkgutil` | `broker`, `persistencia`, `orquestador` |
| `src/trotamundos/notificaciones/canales/base.py` | `CanalSimulado` (demora, caída, registro) | `dominio.puertos_notificaciones` | `broker`, `persistencia`, `orquestador` |
| `src/trotamundos/notificaciones/canales/email.py`, `whatsapp.py`, `instagram.py` | Canales Email, WhatsApp e Instagram (adaptadores `ICanal`) | `notificaciones.canales` (el decorador y la base) | Cualquier otro canal, `broker`, `persistencia` |
| `src/trotamundos/orquestador/notificaciones.py` | Publicador del Orquestador de viajes en la cola de notificaciones | `broker`, `config`, `dominio` | `notificaciones` (no conoce a los canales) |
| `src/trotamundos/broker/broker.py` (se modifica) | Broker: `procesar_uno(..., donde=None)` | — | — |
| `src/trotamundos/config.py`, `composicion.py`, `app.py`, `tests/test_arquitectura.py` (se modifican) | `ConfiguracionNotificaciones`, `ensamblar_notificaciones`, montaje, reglas | — | — |

Reglas nuevas de arquitectura: `notificaciones` sin `persistencia`, `orquestador`, `entrada`, `identidad`, `analitica`, `cotizacion`, `asistente`; `notificaciones/servicio` sin `trotamundos.notificaciones.canales`; cada módulo de `notificaciones/canales` sin importar a otro canal; `orquestador/notificaciones` sin `trotamundos.notificaciones`; `dominio/puertos_notificaciones` sin `config`; y un test propio: **ningún archivo de `src` fuera de `canales/instagram.py` menciona «instagram»** (es lo que verifica `AC-02`).

Parámetros nuevos (`ConfiguracionNotificaciones`, variables `TROTA_*`): `canales` (`None` = todos los descubiertos; la spec los lista como `email`, `whatsapp`, `instagram`), `tamano_cola_notificaciones` 100, `reintentos_publicacion` 3 y `backoff_publicacion_segundos` 1.0 (los 1, 2 y 4 s de la spec). Los reintentos del Broker son los de `ConfiguracionBroker` (3 con 1, 2 y 4 s) y no se duplican.

## Tareas de Implementación

| ID | Descripción de la tarea | Archivos a crear / modificar | AC que cubre | Depende de | Criterio de terminado (Done) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `T-COMP-08-01` | `ICanal` y `Propuesta`, `ConfiguracionNotificaciones`, reglas de arquitectura y `Broker.procesar_uno(donde=...)` | `dominio/puertos_notificaciones.py`, `config.py`, `broker/broker.py`, `tests/test_arquitectura.py`, `tests/test_comp08_broker.py` | `AC-COMP-08-02` (parte de arquitectura) | — | El filtro toma solo lo que corresponde y los tests existentes del Broker siguen en verde |
| `T-COMP-08-02` | Registro y descubrimiento de canales, `CanalSimulado` y los canales Email, WhatsApp e Instagram | `notificaciones/canales/*`, `tests/test_comp08_canales.py` | `AC-COMP-08-02` | 01 | Instagram es un solo archivo y no hay otra mención en `src`; un canal nuevo de prueba se descubre sin tocar nada |
| `T-COMP-08-03` | `ServicioNotificaciones`: un consumidor por canal, deduplicación, canal no registrado a muertos | `notificaciones/servicio.py`, `tests/test_comp08_servicio.py` | `AC-COMP-08-01`, `AC-COMP-08-03`, `AC-COMP-08-06`, `AC-COMP-08-08` | 02 | Cada pedido se entrega una vez por su canal; un duplicado no se reenvía |
| `T-COMP-08-04` | Fallas y aislamiento: caída con reintentos y muertos, y un canal lento que no atrasa a los demás | `tests/test_comp08_aislamiento.py` | `AC-COMP-08-04`, `AC-COMP-08-05`, `AC-COMP-08-10` | 03 | Con Instagram caído o lento, Email sale sin demora adicional; agotados los reintentos hay un mensaje muerto y un aviso |
| `T-COMP-08-05` | `PublicadorNotificaciones` con reintentos (también desde hilos) | `orquestador/notificaciones.py`, `tests/test_comp08_publicador.py` | `AC-COMP-08-07` | 01 | Con la cola llena reintenta tras 1, 2 y 4 s, avisa a operaciones y, agotado, va a muertos |
| `T-COMP-08-06` | Composición: `ensamblar_notificaciones`, consumidores en el `Supervisor`, tamaño de la cola y reemplazo del `broker.publicar` de `COMP-05` por el publicador | `composicion.py`, `app.py`, `tests/test_comp08_punta_a_punta.py` | `AC-COMP-08-09` | 04, 05 | El correo de recuperación de `COMP-05` sale por el canal Email de este servicio |

## Matriz de Cobertura de Criterios de Aceptación

| Criterio de Aceptación (Spec) | Tarea(s) del Plan | Nombre del test automatizado | Estado |
| :--- | :--- | :--- | :--- |
| `AC-COMP-08-01` | `T-COMP-08-03` | `test_AC_COMP_08_01_un_pedido_por_email_invoca_enviar_una_vez` | `[x] Verde` |
| `AC-COMP-08-02` | `T-COMP-08-01`, `T-COMP-08-02` | `test_AC_COMP_08_02_instagram_es_un_solo_archivo_y_no_cambia_nada_mas` | `[x] Verde` |
| `AC-COMP-08-03` | `T-COMP-08-03` | `test_AC_COMP_08_03_un_pedido_por_instagram_no_toca_email_ni_whatsapp` | `[x] Verde` |
| `AC-COMP-08-04` | `T-COMP-08-04` | `test_AC_COMP_08_04_instagram_caido_no_atrasa_a_email` | `[x] Verde` |
| `AC-COMP-08-05` | `T-COMP-08-04` | `test_AC_COMP_08_05_agotados_los_reintentos_va_a_muertos_con_aviso` | `[x] Verde` |
| `AC-COMP-08-06` | `T-COMP-08-03` | `test_AC_COMP_08_06_el_mismo_pedido_dos_veces_se_envia_una_sola_vez` | `[x] Verde` |
| `AC-COMP-08-07` | `T-COMP-08-05` | `test_AC_COMP_08_07_cola_llena_reintenta_con_1_2_y_4_segundos_y_avisa` | `[x] Verde` |
| `AC-COMP-08-08` | `T-COMP-08-03` | `test_AC_COMP_08_08_canal_no_registrado_va_a_muertos_con_aviso` | `[x] Verde` |
| `AC-COMP-08-09` | `T-COMP-08-06` | `test_AC_COMP_08_09_el_correo_de_recuperacion_sale_por_el_canal_email` | `[x] Verde` |
| `AC-COMP-08-10` | `T-COMP-08-04` | `test_AC_COMP_08_10_un_canal_con_demora_no_cambia_la_latencia_de_los_otros` | `[x] Verde` |

Notas: solo `AC-09` necesita las bases (usa las cuentas de `COMP-05`); todos los demás corren sin Docker. Los tiempos de reintento se prueban con la espera inyectable del Broker y del publicador, sin esperar 7 s. `AC-04` y `AC-10` miden el tiempo real con demoras de 1 a 2 s y márgenes de 100 ms o más.

Cambios respecto de lo planeado al implementar:
* `AC-COMP-08-04` tiene un segundo test (`test_AC_COMP_08_04_los_pedidos_de_instagram_se_reintentan_con_el_mismo_identificador`) porque la medición de latencia y la del reintento son comprobaciones distintas.
* Un pedido **mal formado** de un canal registrado (sin destinatario o sin propuesta) va directo a mensajes muertos sin reintentos, igual que el de un canal inexistente: reintentarlo no lo arregla. El plan solo decía esto de los canales no registrados.
* Un nombre de canal configurado en `TROTA_CANALES` que no existe rechaza el arranque (`ValueError`); el plan no lo decía.
* `descubrir()` acepta un paquete alternativo, para probar que un canal nuevo se encuentra con solo agregar su archivo.
* Se agregó `tests/test_comp08_broker.py` (el parámetro `donde` del Broker) y `tests/test_comp08_canales.py`.

## Estrategia de Pruebas y Simulación de Fallos

* **Archivos:** `tests/test_comp08_*.py` y `tests/comp08_util.py` (un `Broker` con espera falsa, el servicio con los tres canales simulados y un cronómetro).
* **Inyección de fallos:** `caida` y `demora_segundos` en cada canal, cola llena (tamaño 1), canal no registrado y un mismo pedido publicado dos veces.
* **Aislamiento (`AC-04`, `AC-10`):** se publican pedidos de Instagram (con demora de 2 s o caído) y de Email; se mide cuándo sale cada pedido de Email, que debe ser igual al de una corrida sin Instagram, con un margen.
* **Deduplicación y duplicado del Broker (`AC-06`):** el mismo identificador se publica dos veces; `enviar` se invoca una sola vez.
* **Bases:** `comp08_test` para `AC-09`, con `TROTA_DSN_*` apuntando a ella.
* **Comando de ejecución:** `pytest tests/test_comp08_*.py tests/test_arquitectura.py tests/test_ref0*.py` (esto último por el cambio en el Broker). Antes de terminar, la suite completa, con ninguna otra sesión sobre las mismas bases.

## Riesgos Técnicos del Plan

* **Choque con `comp-07` y con lo que suba el compañero, en `config.py`, `composicion.py`, `app.py` y `test_arquitectura.py`:** son los mismos archivos. Mitigación: bloques nuevos y aislados, y un `git merge main` solo cuando el usuario lo indique. No se mergea a `main` desde esta rama.
* **Cambio en el Broker (D2):** lo usan todas las colas. Mitigación: el parámetro es opcional y por defecto el comportamiento no cambia; los tests del Broker corren completos en `T-COMP-08-01`.
* **Un pedido de un canal registrado que nadie consume:** si el consumidor de un canal cae, sus pedidos esperan en la cola. Mitigación: el `Supervisor` lo reinicia y la cola acotada avisa a operaciones al llenarse.
* **La deduplicación vive en memoria:** se pierde al reiniciar. Es la misma simplificación que la ingesta; el Broker tampoco persiste.
* **El correo de recuperación se publica desde un hilo (D7):** si el bucle de eventos todavía no está enlazado, los reintentos no se programan. Mitigación: se enlaza en el `lifespan` antes de aceptar pedidos y, sin bucle, el pedido va a muertos con aviso en lugar de perderse.
