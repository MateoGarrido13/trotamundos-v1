# PLAN-REF-06. Analítica de datos

* **Spec asociada:** [SPEC-REF-06](../specs/SPEC-REF-06.md) *(estado `aprobada`)*
* **Estado:** terminado
* **Fecha:** 2026-11-23
* **Incremento (Slice):** Slice 5 de [PLAN_MAESTRO.md](PLAN_MAESTRO.md)

Se apoya en lo construido: el `Broker` (la quinta cola `eventos_analiticos` ya existe), `BaseViajes` y las operaciones que escriben reservas (REF-01 archivado, REF-03 incorporación del correo, REF-04 alta, modificación, baja y novedades). Esta spec agrega un **camino de lectura aislado**: el Orquestador publica eventos anonimizados, un Proyector los consume en nodos propios y los resume en una **Base analítica** separada, y un Servicio de consultas responde el informe leyendo solo esa base.

```
Orquestador ──(quinta cola)──► Proyector ──► Base analítica ◄── Servicio de consultas ◄── equipo de datos
  (después del commit)        (descarta repetidos,            (no lee la Base de viajes
                               suma contadores)                 ni usa nodos del Orquestador)
```

## Decisiones Técnicas Locales

Las tres marcadas **[DECISIÓN]** las confirmó el usuario eligiendo la opción A en cada una.

| Decisión | Alternativa elegida | Motivo | ¿Afecta algún driver o requiere ADR? |
| :--- | :--- | :--- | :--- |
| **[DECISIÓN 1 · A]** Qué «día» usan los contadores | El día en que **ocurrió el evento** (cuándo se creó, modificó o canceló la reserva) | La spec dice «altas por día» y «bajas por destino y día». La baja se cuenta el día en que se canceló, no el día del viaje | No |
| **[DECISIÓN 2 · A]** Evento de archivado de un viaje | **Un evento por viaje**, sin tipo de reserva ni destino. Se guarda y se cuenta, pero no entra a ninguna de las tres secciones del informe | El archivado no tiene un único destino ni tipo | No |
| **[DECISIÓN 3 · A]** Prueba de carga con un millón de eventos | Se corre en la suite completa, marcada `carga` | `AC-REF-06-03` pide el millón; así el criterio se verifica siempre | No |
| Base analítica | Instancia PostgreSQL propia en el `docker-compose.yml` (`analitica`, puerto 5435), distinta de las bases de viajes | Aislamiento físico (`QA-DIS-01`). El Plan Maestro prevé 9 bases | No |
| Esquema analítico | `evento` (identificador del evento como clave primaria, tipo, tipo de reserva, destino, fechas, origen, estado, momento) y `contador` (día, destino, tipo de reserva, tipo de evento, cantidad) | Preagregación incremental (`ADR-IT5-002`). El histórico queda para recalcular dimensiones nuevas | No |
| Proyección idempotente | En una sola transacción: inserta el evento si no existe (`ON CONFLICT DO NOTHING`) y, solo si se insertó, suma al contador | Un identificador repetido no vuelve a sumar (`AC-REF-06-06`) | No |
| Anonimato del evento | El evento tiene una lista cerrada de campos: identificador del evento (aleatorio), tipo de evento, tipo de reserva, destino, fechas, origen, estado y momento. **No lleva el identificador de la reserva, del viaje, del itinerario ni de la cuenta** | `AC-REF-06-07`. Al Proyector no le hace falta saber a qué reserva pertenece el evento (regla 4) | No |
| Destino | `lugar` de la reserva (texto). Una reserva sin lugar cuenta con destino vacío | El contrato `Reserva` tiene `lugar` como texto; la spec habla de `lugar.destino` | No |
| Qué emite eventos | Alta y modificación y baja lógica de la gestión manual (REF-04), la reserva que entra por el correo (REF-03, alta con origen `correo`), una novedad aplicada (modificación con origen `proveedor`) y el archivado de un viaje (REF-01) | «Cada alta, modificación, baja lógica o archivado» (regla 1) | No |
| Publicación sin demorar | El evento se construye con los datos que ya devolvió la escritura y se publica **después** del commit, en una tarea en segundo plano con reintentos de 1 s, 2 s y 4 s | Regla 1 y `AC-REF-06-08`. No se publica un evento de una operación repetida (la clave ya aplicada) | No |
| Eventos que agotan los reintentos | El `Broker` gana `enviar_a_muertos(cola, mensaje)`: lo guarda en la cola de mensajes muertos y avisa a operaciones, como si lo hubiera agotado un consumidor | La spec pide ese destino para el publicador. Hoy solo lo alcanzaban los consumidores | No |
| Aislamiento de fallas | La publicación no depende de la Base analítica: el Orquestador solo habla con el Broker. Si el Proyector no puede escribir, el evento reintenta y termina en mensajes muertos; las operaciones del viajero no se enteran | `QA-DIS-01`, `AC-REF-06-09` | No |
| Paquete propio | `trotamundos.analitica` (Proyector, Servicio de consultas, acceso a la Base analítica). **No importa `orquestador` ni la persistencia de viajes** | La restricción de frontera de la spec. Un test de arquitectura lo hace cumplir | No |
| Informe | Tres secciones sobre el rango pedido: `tendencias` (altas por día), `destinos` (ranking de destinos por cantidad de altas) y `cancelaciones` (bajas por día y destino). Filtros opcionales de destino y tipo de reserva | La spec define las secciones sin fijar su forma exacta | No |
| Cota de 10 segundos | Doble: `statement_timeout` en la consulta y `asyncio.wait_for` alrededor. Al vencer, error de tiempo agotado y ningún informe parcial. Configurable, para probar con una cota corta | `AC-REF-06-11`. La consulta de PostgreSQL se cancela de verdad; el `wait_for` solo no la cancelaría | No |
| Cuentas del equipo de datos | Lista en la configuración (`TROTA_CUENTAS_DATOS`). Cualquier otra cuenta recibe acceso denegado y ningún dato | Simplificación de la spec | No |
| Servicio de consultas separado | App FastAPI propia (`trotamundos.analitica.app`), con `GET /analitica/informe`, separada de la del Orquestador. Identidad en `X-Viajero-Id`; 403 sin autorización; 504 al vencer la cota; 422 con fechas inválidas | Nodos propios, sin compartir con el Orquestador (`QA-PER-02`) | No |
| Zona horaria del «día» | UTC | El evento viaja con su momento con zona horaria y el día se calcula una vez en el Proyector | No |
| Ranking de destinos | Los 100 primeros por cantidad de altas, con desempate alfabético | Acota el tamaño de la respuesta | No |
| Evento de una operación repetida o rechazada | No se publica. Tampoco el de una escritura que falla: el evento sale solo después de confirmar | La clave ya aplicada devuelve el resultado sin escribir; lo denegado y lo rechazado no cambian nada | No |
| Reserva nueva del correo | `incorporar_reserva` devuelve si la reserva era nueva; una entrega repetida no emite otra alta | Evita contar dos veces el mismo correo | No |
| Hilo de la proyección | El Proyector mantiene una conexión y la reabre si falla; una consulta a la vez, protegida por un cerrojo | Una conexión por evento es lenta, y el consumidor es único | No |

## Estructura de Código y Mapeo Arquitectónico

| Ruta en el repositorio | Elemento del paso 5 que instancia | Dependencias permitidas (imports) | Prohibiciones explícitas |
| :--- | :--- | :--- | :--- |
| `src/trotamundos/dominio/eventos.py` | Evento analítico anonimizado (lista cerrada de campos) | `pydantic` | No importa otro paquete |
| `src/trotamundos/broker/broker.py` | `enviar_a_muertos` | — | Sin dependencias nuevas |
| `src/trotamundos/orquestador/eventos_analiticos.py` | Orquestador: publica en la quinta cola con Retry y mensajes muertos | `dominio`, `broker`, `config` | **No importa `analitica`** ni escribe la Base analítica |
| `src/trotamundos/orquestador/gestion_reservas.py`, `novedades.py`, `incorporacion.py`, `archivado.py` | Se ajustan: devuelven los datos del evento y lo publican tras el commit | los actuales | Tests previos en verde |
| `src/trotamundos/analitica/esquema.sql`, `analitica/base.py` | Base analítica y su acceso (su propia conexión) | `psycopg`, `config` | **No importa `persistencia` de viajes ni `orquestador`** |
| `src/trotamundos/analitica/proyector.py` | Proyector analítico (nodos propios) | `dominio.eventos`, `broker`, `analitica.base` | Ídem. No lee la Base de viajes |
| `src/trotamundos/analitica/consultas.py` | Servicio de consultas analíticas | `analitica.base`, `config` | Ídem. No llama a ningún nodo del Orquestador |
| `src/trotamundos/analitica/app.py` | Endpoint del informe (equipo de datos) | `fastapi`, `analitica.consultas` | Ídem |
| `docker-compose.yml`, `config.py` | `analitica` (puerto 5435), DSN, tamaño de la quinta cola, cuentas autorizadas, cota | — | — |

Ajustes a `tests/test_arquitectura.py` (aditivos): `analitica` no importa `orquestador` ni `persistencia`; `orquestador/eventos_analiticos` no importa `analitica`; `dominio/eventos` no importa nada más del paquete.

## Tareas de Implementación

| ID | Descripción de la tarea | Archivos a crear / modificar | AC que cubre | Depende de | Criterio de terminado (Done) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `T-REF-06-01` | Evento anonimizado, configuración, `enviar_a_muertos` en el Broker, instancia `analitica` en Docker, esquema y acceso a la Base analítica | `dominio/eventos.py`, `broker/broker.py`, `config.py`, `docker-compose.yml`, `analitica/esquema.sql`, `analitica/base.py`, `tests/conftest.py`, `tests/test_ref06_modelo.py` | `AC-REF-06-07` | — | El evento solo tiene los campos permitidos; la base analítica arranca y se recrea en los tests |
| `T-REF-06-02` | Emisor del Orquestador: publica con Retry, aviso y mensajes muertos, sin esperar a la cola | `orquestador/eventos_analiticos.py`, `tests/test_ref06_emisor.py` | `AC-REF-06-08`, `AC-REF-06-09` (parte del Orquestador) | `T-REF-06-01` | Con la cola llena la respuesta no se demora, se reintenta y al agotar va a mensajes muertos con aviso |
| `T-REF-06-03` | Emitir en cada alta, modificación, baja lógica y archivado | `orquestador/gestion_reservas.py`, `orquestador/incorporacion.py`, `orquestador/novedades.py`, `orquestador/archivado.py`, `persistencia/repositorio_viajes.py`, `app.py`, `tests/test_ref06_emision.py` | `AC-REF-06-01`, `AC-REF-06-05` (la baja se publica), `AC-REF-06-09` | `T-REF-06-02` | Cada operación publica un evento, una clave repetida no publica otro, y con la Base analítica caída las operaciones se completan |
| `T-REF-06-04` | Proyector: guarda el evento y suma contadores, idempotente, con Retry | `analitica/proyector.py`, `tests/test_ref06_proyector.py` | `AC-REF-06-02`, `AC-REF-06-05`, `AC-REF-06-06`, `AC-REF-06-13` | `T-REF-06-01` | Un identificador repetido no suma; cada tipo de evento suma solo a su contador |
| `T-REF-06-05` | Servicio de consultas: acceso, filtros, tres secciones, cota con cancelación real y secciones vacías | `analitica/consultas.py`, `tests/test_ref06_consultas.py` | `AC-REF-06-10`, `AC-REF-06-11`, `AC-REF-06-12`, `AC-REF-06-04` | `T-REF-06-04` | Sin autorización no sale ningún dato; al vencer la cota no hay informe parcial; sin eventos, secciones vacías |
| `T-REF-06-06` | App del Servicio de consultas y reglas de arquitectura | `analitica/app.py`, `tests/test_arquitectura.py`, `tests/test_ref06_api.py` | `AC-REF-06-10` (por HTTP), `AC-REF-06-11` (por HTTP), `AC-REF-06-04` | `T-REF-06-05` | 403 y 504 por la red; el Servicio funciona con las bases de viajes inalcanzables |
| `T-REF-06-07` | Prueba de carga con un millón de eventos sembrados y de punta a punta (Orquestador → cola → Proyector → informe) | `tests/test_ref06_carga.py`, `tests/test_ref06_punta_a_punta.py` | `AC-REF-06-03` | `T-REF-06-06`, `T-REF-06-03` | Diez informes concurrentes con el Proyector consumiendo: promedio menor a 10 s |

## Matriz de Cobertura de Criterios de Aceptación

Ningún `AC` de la spec puede quedar sin tarea ni sin test asociado. Resultado de la prueba de carga: 10 informes concurrentes sobre 1.000.000 de eventos, con el Proyector consumiendo, promedio de 0,40 s y máximo de 0,49 s (cota: 10 s).

| Criterio de Aceptación (Spec) | Tarea(s) del Plan | Nombre del test automatizado | Estado |
| :--- | :--- | :--- | :--- |
| `AC-REF-06-01` | `T-REF-06-03` | `test_AC_REF_06_01_cada_alta_modificacion_baja_y_archivado_publica_un_evento_anonimizado` | `[x] Verde` |
| `AC-REF-06-02` | `T-REF-06-04` | `test_AC_REF_06_02_el_proyector_guarda_el_evento_y_actualiza_los_contadores` | `[x] Verde` |
| `AC-REF-06-03` | `T-REF-06-07` | `test_AC_REF_06_03_diez_informes_concurrentes_sobre_un_millon_de_eventos_tardan_menos_de_10_s` | `[x] Verde` |
| `AC-REF-06-04` | `T-REF-06-05`, `T-REF-06-06` | `test_AC_REF_06_04_el_informe_no_lee_la_base_de_viajes_ni_usa_el_orquestador`, `test_AC_REF_06_04_el_servicio_responde_aunque_las_bases_de_viajes_no_existan` | `[x] Verde` |
| `AC-REF-06-05` | `T-REF-06-03`, `T-REF-06-04` | `test_AC_REF_06_05_la_baja_logica_suma_a_las_cancelaciones_de_ese_destino_y_dia` | `[x] Verde` |
| `AC-REF-06-06` | `T-REF-06-04` | `test_AC_REF_06_06_un_evento_repetido_no_se_guarda_ni_suma_de_nuevo` | `[x] Verde` |
| `AC-REF-06-07` | `T-REF-06-01`, `T-REF-06-03` | `test_AC_REF_06_07_el_evento_no_contiene_datos_personales`, `test_AC_REF_06_07_los_eventos_reales_no_contienen_datos_personales` | `[x] Verde` |
| `AC-REF-06-08` | `T-REF-06-02`, `T-REF-06-03` | `test_AC_REF_06_08_cola_llena_no_demora_reintenta_y_agotada_va_a_mensajes_muertos`, `test_AC_REF_06_08_con_la_cola_llena_la_respuesta_al_viajero_no_se_demora` | `[x] Verde` |
| `AC-REF-06-09` | `T-REF-06-03` | `test_AC_REF_06_09_con_la_base_analitica_caida_las_operaciones_del_viajero_se_completan` | `[x] Verde` |
| `AC-REF-06-10` | `T-REF-06-05`, `T-REF-06-06` | `test_AC_REF_06_10_una_cuenta_que_no_es_del_equipo_de_datos_recibe_acceso_denegado`, `test_AC_REF_06_10_acceso_denegado_por_http_sin_ningun_dato` | `[x] Verde` |
| `AC-REF-06-11` | `T-REF-06-05`, `T-REF-06-06` | `test_AC_REF_06_11_al_vencer_la_cota_hay_error_de_tiempo_agotado_y_ningun_informe_parcial`, `test_AC_REF_06_11_la_cota_vencida_responde_504_sin_informe_parcial` | `[x] Verde` |
| `AC-REF-06-12` | `T-REF-06-05` | `test_AC_REF_06_12_sin_eventos_en_el_rango_las_tres_secciones_llegan_vacias` | `[x] Verde` |
| `AC-REF-06-13` | `T-REF-06-04` | `test_AC_REF_06_13_cada_evento_suma_solo_a_su_contador_sin_recalcular_la_reserva` | `[x] Verde` |

## Estrategia de Pruebas y Simulación de Fallos

* **Tests unitarios / contractuales:** el evento se inspecciona campo por campo. El Proyector y el Servicio usan la Base analítica real (marca `db`) con tablas recreadas en cada caso. El emisor se prueba con un `Broker` real de colas de 5 y espera inyectada.
* **Inyección de fallos:**
  * Quinta cola llena (`AC-REF-06-08`): se llenan los 5 lugares; el test mide que la respuesta del Orquestador no espera los reintentos, que las esperas son 1 s, 2 s y 4 s, y que el evento termina en mensajes muertos con aviso.
  * Base analítica caída (`AC-REF-06-09`): el Proyector apunta a un DSN inalcanzable; alta, modificación y baja del viajero se completan, y el evento queda reintentando o en mensajes muertos.
  * Cota (`AC-REF-06-11`): cota de 0,3 s y una consulta que duerme 2 s con `pg_sleep`; se verifica que la consulta se cancela en la base y que no hay informe parcial.
* **Aislamiento (`AC-REF-06-04`):** el Servicio se construye solo con el DSN analítico y con las bases de viajes inalcanzables; además, el test de arquitectura impide los imports prohibidos.
* **Carga (`AC-REF-06-03`):** se siembran 1.000.000 de eventos en la Base analítica con `generate_series` (sin pasar por el Orquestador, como autoriza la spec) y se recalculan los contadores desde ellos. Diez informes concurrentes mientras el Proyector consume eventos nuevos; se mide el promedio.
* **Comando de ejecución:** `.venv/bin/pytest tests/test_ref06_*.py` (con `docker compose up -d --wait`).

## Riesgos Técnicos del Plan

* **Modifica código de REF-01, REF-03 y REF-04.** Cada servicio gana un emisor opcional. Mitigación: sin emisor no hacen nada, y los tests anteriores deben seguir en verde.
* **Un corte entre la escritura y la publicación pierde el evento.** Es la limitación que la spec acepta. El informe es eventual y no exige entrega garantizada.
* **Una instancia más de PostgreSQL.** Mitigación: el contenedor es liviano y los tests la recrean.
* **Tiempo de la prueba de carga.** Sembrar un millón de filas y diez consultas puede tardar varios segundos. Decisión 3 confirmada: se corre en la suite completa.
* **El «día» define el significado del informe** (Decisión 1, confirmada). Queda escrito en la spec.
