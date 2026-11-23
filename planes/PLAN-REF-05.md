# PLAN-REF-05. Resolución de problemas

* **Spec asociada:** [SPEC-REF-05](../specs/SPEC-REF-05.md) *(estado `aprobada`)*
* **Estado:** terminado
* **Fecha:** 2026-11-23
* **Incremento (Slice):** Slice 5 de [PLAN_MAESTRO.md](PLAN_MAESTRO.md)

Se apoya en lo ya construido: el `Broker` (cola `casos_ayuda` y cola `novedades`, Retry, mensajes muertos), el `ServicioIngesta` de REF-03, la app de nodos de entrada de REF-02, y de REF-04 el control de acceso (`registrar`), la auditoría, las claves de operación y el itinerario. Esta spec agrega el **caso de ayuda**, la **agencia preferida** y el camino Orquestador → cola → Adaptador de agencia → agencia, con la vuelta por novedades.

```
Viajero ─► Orquestador ──(cola casos_ayuda)──► Adaptador de agencia ──abrirCaso──► Agencia
              ▲                                        │  ▲
              │                                        │  └── aviso (id del caso + clave) ──┐
              └── Servicio de ingesta ◄──(cola novedades)┘◄── consultarCaso ◄───────────────┘
```

## Decisiones Técnicas Locales

Las tres marcadas **[DECISIÓN]** las confirmó el usuario eligiendo la opción A en cada una.

| Decisión | Alternativa elegida | Motivo | ¿Afecta algún driver o requiere ADR? |
| :--- | :--- | :--- | :--- |
| **[DECISIÓN 1 · A]** Publicación del pedido con la cola llena | Tarea en segundo plano dentro del proceso del Orquestador, con reintentos de 1 s, 2 s y 4 s; al agotarlos el caso pasa a «sin entregar». Si el proceso muere a mitad, el caso queda «en trámite» sin publicarse (riesgo aceptado) | La spec pide que el Orquestador «reintente la publicación con espera creciente» sin que el viajero espere | No |
| **[DECISIÓN 2 · A]** Cómo se identifica el itinerario al reportar | El pedido trae `itinerario_id` y `reserva_id`, como en REF-04. Primero se verifica el permiso `registrar` sobre ese itinerario y después que la reserva sea de él | Una reserva inexistente y una ajena dan la misma respuesta; no se revela si existe | No |
| **[DECISIÓN 3 · A]** Quién ve y reintenta un caso | Cada viajero ve solo los casos que él reportó, y solo él los reintenta (además de tener `registrar` en el itinerario) | «Los casos del viajero» (spec). El caso guarda lo que el viajero contó y la agencia que eligió | No |
| Agencias disponibles | Se registran en la configuración (`TROTA_AGENCIAS`, lista de nombres). El Orquestador solo conoce **nombres**; los adaptadores viven en los nodos de entrada y se ensamblan en `composicion.py` | Una agencia nueva es un adaptador más sin tocar al Orquestador (`CON-02`). Es la simplificación de la spec | No |
| `IProveedor` / `IAgencia` | `IProveedor` mínimo (un nombre) y `IAgencia(IProveedor)` con `abrir_caso(pedido)` y `consultar_caso(id_caso)`, en `dominio/agencias.py`. El código no tiene aún `IProveedor` (la cotización es de otro slice) | La spec nombra `IAgencia` como extensión de `IProveedor` | No |
| Agencia preferida | Tabla `preferencia_agencia (cuenta_id, agencia, consentimiento_en)`, una por cuenta. Elegir sin consentimiento o una agencia no registrada se rechaza sin guardar nada | `AC-REF-05-06` | No |
| El caso guarda la agencia vigente | Tabla `caso` con la agencia vigente al reportar, el actor, el itinerario, la reserva, la descripción, el resumen del diálogo (si lo trae el asistente), el estado y las fechas | Regla 8 de la spec | No |
| Pedido a la agencia | Mensaje con `id_caso`, agencia, la reserva afectada (identificador, tipo, lugar, fechas), la descripción y el resumen del diálogo. **No incluye** miembros, cuentas ni otras reservas | Lo único que el viajero consintió que viaje a un tercero | No |
| Identificador del caso | `caso-<uuid>`, generado **antes** de la escritura de dos fases | La operación corre en las dos bases (aprendido en REF-04) | No |
| Reporte en una transacción | Permiso, clave de operación, validación, caso y asiento de auditoría, en una sola escritura de `BaseViajes`; la publicación en la cola es **después** del commit | Reglas 8 y 9. Publicar dentro de la transacción dejaría pedidos de casos que se revirtieron | No |
| Estados que solo avanzan | `en_tramite < abierto < en_curso < resuelto`. `sin_entregar` solo se alcanza desde `en_tramite` y solo se sale reintentando. Una novedad que retrocede, o que llega con el caso «sin entregar» o «resuelto», se ignora | Regla 10 y la nota de la spec: «solo se sale reintentando» | No |
| Ingesta generalizada | `ServicioIngesta` despacha por el campo `origen` del mensaje: `correo` (reserva, como hoy) o `caso` (cambio de estado). Un segundo puerto, `EntregaNovedadCaso`, lo implementa el Orquestador. Los identificadores se forman con el del caso y el estado (`caso:<id>:<estado>`) | La spec pide que las novedades de casos entren por la cola de novedades y la ingesta, que ya descarta duplicados por identificador | No |
| Entrega a la agencia | El `AdaptadorAgencia` consume la cola con `Broker.procesar_uno`: Retry de 1 s, 2 s y 4 s y cola de mensajes muertos ya probados. Si el resultado es `MUERTO`, publica la novedad `sin_entregar` | Reglas 2 y 5 | No |
| `abrirCaso` idempotente | El mock de la agencia descarta un `id_caso` que ya abrió. Reintentar publica el pedido con el **mismo** `id_caso` | Regla 5: no duplicar si la agencia ya lo había abierto | No |
| Listener de avisos | Endpoint en la app de nodos de entrada: `POST /agencia/avisos` con `{"id_caso": ...}` y la clave compartida en `X-Clave-Agencia` (variable de entorno `TROTA_CLAVE_AGENCIA`). Clave inválida: 401 sin consultar nada. Cola de novedades llena: 503, para que la agencia avise de nuevo | Mismo criterio que el Adaptador de anuncios (`ADR-IT3-002`) | No |
| `consultarCaso` sin respuesta | El aviso se pierde (503 a la agencia) y la agencia puede avisar de nuevo. Caso desconocido para la agencia: 200 sin publicar nada | Contrato de la spec | No |
| «Novedades» | `GET /casos` devuelve los casos del actor con su estado. Es la vista de «Novedades» para los casos. No se mezcla con las novedades de proveedor de REF-04 | Mantiene separados dos orígenes de novedad que la spec trata distinto | No |
| Cierre del ciclo con el asistente | `ServicioCasos.reportar(...)` es el mismo método que usa el endpoint y el que invocará SPEC-REF-07, con el resumen del diálogo opcional | `AC-REF-05-17` | No |
| Una agencia por endpoint de aviso | `POST /agencia/{agencia}/avisos`: el nombre de la agencia va en la ruta | El aviso solo trae el identificador del caso y la clave; con varios adaptadores el listener necesita saber a cuál preguntarle `consultarCaso` | No |
| Clave de operación de los casos | Se guarda en la misma tabla de REF-04 con el prefijo `caso:` | Evita que una clave de una reserva manual se confunda con la de un reporte de la misma cuenta | No |
| Reporte repetido | La respuesta de la primera operación se devuelve tal cual y no se vuelve a publicar | Regla 9 | No |
| Pedido guardado en el caso | La columna `pedido` conserva el pedido tal como se envió, y reintentar lo republica sin reconstruirlo | La reserva puede haber cambiado o estar en baja; el reintento debe ser el mismo pedido | No |
| Aviso antes de que exista el caso | Una novedad sobre un caso que el Orquestador no tiene se ignora y se da por procesada; la agencia puede avisar de nuevo | Carrera improbable entre el aviso y el commit | No |
| Estado «sin entregar» publicado por el Adaptador | Reintenta publicar la novedad con la misma espera creciente; si la cola de novedades sigue llena, el pedido queda en mensajes muertos con aviso a operaciones | Es la limitación de saturación que reconoce `ADR-IT3-002` | No |

## Estructura de Código y Mapeo Arquitectónico

| Ruta en el repositorio | Elemento del paso 5 que instancia | Dependencias permitidas (imports) | Prohibiciones explícitas |
| :--- | :--- | :--- | :--- |
| `src/trotamundos/dominio/agencias.py` | `IProveedor`, `IAgencia`, el pedido, los estados del caso y su regla de avance | `pydantic` | No importa ningún otro paquete |
| `src/trotamundos/dominio/puertos_casos.py` | Frontera de la ingesta hacia el Orquestador para los cambios de estado (`EntregaNovedadCaso`) | `dominio.agencias` | No importa otro paquete |
| `src/trotamundos/persistencia/esquemas/05_casos.sql`, `persistencia/repositorio_casos.py` | Base primaria: agencia preferida y casos | `psycopg`, `dominio` | No importa `orquestador` ni `entrada` |
| `src/trotamundos/orquestador/casos.py` | Orquestador: elegir agencia, reportar, reintentar, consultar, aplicar el estado de una novedad, publicar con reintentos | `dominio`, `broker`, `orquestador.control_acceso`, `persistencia` | **No importa `entrada`** (no conoce al Adaptador ni a las agencias, solo sus nombres) |
| `src/trotamundos/orquestador/api_casos.py` | Endpoints del viajero | `fastapi`, `orquestador.casos` | La cotización no pasa por acá |
| `src/trotamundos/entrada/agencia.py` | Adaptador de agencia (capa anti-corrupción) y `MockAgencia` | `dominio.agencias`, `broker`, `config` | **No importa `persistencia` ni `orquestador`**: no escribe la Base de viajes ni la lee |
| `src/trotamundos/entrada/api_agencia.py` | Listener del Adaptador (aviso de la agencia) | `fastapi`, `entrada.agencia` | Ídem |
| `src/trotamundos/entrada/ingesta.py` | Se generaliza (despacho por `origen`) | `dominio`, `broker`, `config` | **Sigue sin importar `persistencia`** |
| `src/trotamundos/composicion.py`, `app.py` | Ensamble: adaptadores registrados, Orquestador y nodos de entrada | Todos | Es el único lugar que conecta `entrada` con `orquestador` |

Ajustes a `tests/test_arquitectura.py` (aditivos): `entrada/agencia` y `entrada/api_agencia` no importan `persistencia`; `orquestador/casos` no importa `entrada`; `dominio/agencias` y `dominio/puertos_casos` no importan nada más del paquete.

## Tareas de Implementación

| ID | Descripción de la tarea | Archivos a crear / modificar | AC que cubre | Depende de | Criterio de terminado (Done) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `T-REF-05-01` | Dominio (estados, regla de avance, pedido, `IAgencia`), configuración (agencias, clave, reintentos de publicación), esquema `05_casos.sql` y `RepositorioCasos` | `dominio/agencias.py`, `dominio/puertos_casos.py`, `config.py`, `persistencia/esquemas/05_casos.sql`, `persistencia/repositorio_casos.py`, `tests/conftest.py`, `tests/test_ref05_modelo.py` | `AC-REF-05-15` (regla de avance) | — | Cada transición permitida y prohibida tiene su test; las tablas se recrean en la fixture |
| `T-REF-05-02` | `elegirAgenciaPreferida` con consentimiento y validación contra las agencias registradas | `orquestador/casos.py`, `tests/test_ref05_agencia_preferida.py` | `AC-REF-05-06` | `T-REF-05-01` | Sin consentimiento o agencia desconocida: rechazo sin guardar nada |
| `T-REF-05-03` | Reportar un problema: permiso `registrar`, clave de operación, agencia y consentimiento, reserva del itinerario, caso «en trámite», asiento y resumen del diálogo | `orquestador/casos.py`, `tests/test_ref05_reportar.py` | `AC-REF-05-01` (guarda el caso), `AC-REF-05-07`, `AC-REF-05-08`, `AC-REF-05-09`, `AC-REF-05-17` | `T-REF-05-02` | Una sola transacción; denegado y rechazado dejan su asiento; la misma clave no abre otro caso |
| `T-REF-05-04` | Publicación del pedido en la cola de casos con reintentos del Orquestador y paso a «sin entregar» | `orquestador/casos.py`, `tests/test_ref05_publicacion.py` | `AC-REF-05-01` (publica), `AC-REF-05-10`, `AC-REF-05-11` | `T-REF-05-03` | Con la cola llena el caso queda «en trámite»; al haber lugar se publica; agotados los reintentos, «sin entregar» |
| `T-REF-05-05` | `AdaptadorAgencia` y `MockAgencia`: consume la cola, `abrirCaso` con Retry, enruta por agencia, publica «sin entregar» al agotar | `entrada/agencia.py`, `tests/test_ref05_adaptador.py` | `AC-REF-05-02`, `AC-REF-05-03`, `AC-REF-05-04`, `AC-REF-05-16`, `AC-REF-05-17` (el pedido incluye el resumen) | `T-REF-05-01` | Un reintento no abre un segundo caso; una segunda agencia recibe sus pedidos sin tocar al Orquestador |
| `T-REF-05-06` | Vuelta por novedades: listener con clave, `consultarCaso`, publicación en la cola de novedades, ingesta generalizada y aplicación del estado en el Orquestador | `entrada/api_agencia.py`, `entrada/agencia.py`, `entrada/ingesta.py`, `orquestador/casos.py`, `tests/test_ref05_novedades_caso.py` | `AC-REF-05-05`, `AC-REF-05-14`, `AC-REF-05-15`, `AC-REF-05-04` (el caso queda «sin entregar») | `T-REF-05-04`, `T-REF-05-05` | Clave inválida no consulta ni publica; una novedad que retrocede se ignora; repetidas se descartan |
| `T-REF-05-07` | Reintentar un caso, consultar los casos del viajero y consultar la agencia preferida con su número de contacto | `orquestador/casos.py`, `tests/test_ref05_reintentar_consultar.py` | `AC-REF-05-12`, `AC-REF-05-13` | `T-REF-05-04` | «Sin entregar» vuelve a «en trámite» y republica el mismo `id_caso`; en cualquier otro estado, rechazo sin efecto |
| `T-REF-05-08` | Endpoints REST del viajero, ensamble de adaptadores y prueba de punta a punta con el mock de la agencia | `orquestador/api_casos.py`, `composicion.py`, `app.py`, `tests/test_ref05_api.py`, `tests/test_ref05_punta_a_punta.py` | `AC-REF-05-01`, `AC-REF-05-05`, `AC-REF-05-16` (de punta a punta) | `T-REF-05-06`, `T-REF-05-07` | De «en trámite» a «resuelto» pasando por la cola, el adaptador, la agencia, la ingesta y el Orquestador |

## Matriz de Cobertura de Criterios de Aceptación

Ningún `AC` de la spec puede quedar sin tarea ni sin test asociado.

| Criterio de Aceptación (Spec) | Tarea(s) del Plan | Nombre del test automatizado | Estado |
| :--- | :--- | :--- | :--- |
| `AC-REF-05-01` | `T-REF-05-03`, `T-REF-05-04`, `T-REF-05-08` | `test_AC_REF_05_01_reportar_guarda_el_caso_en_tramite_con_la_agencia_vigente`, `test_AC_REF_05_01_reportar_publica_el_pedido_en_la_cola_de_casos_de_ayuda`, `test_AC_REF_05_01_reportar_responde_201_en_tramite_sin_esperar_a_la_agencia` | `[x] Verde` |
| `AC-REF-05-02` | `T-REF-05-05` | `test_AC_REF_05_02_el_adaptador_consume_la_cola_y_llama_a_abrir_caso` | `[x] Verde` |
| `AC-REF-05-03` | `T-REF-05-05` | `test_AC_REF_05_03_un_reintento_no_abre_un_segundo_caso` | `[x] Verde` |
| `AC-REF-05-04` | `T-REF-05-05`, `T-REF-05-06` | `test_AC_REF_05_04_reintentos_agotados_publican_sin_entregar`, `test_AC_REF_05_04_el_caso_queda_sin_entregar_y_visible_con_opcion_de_reintentar` | `[x] Verde` |
| `AC-REF-05-05` | `T-REF-05-06`, `T-REF-05-08` | `test_AC_REF_05_05_el_aviso_de_la_agencia_llega_al_viajero_por_novedades`, `test_AC_REF_05_05_del_reporte_a_resuelto_por_el_camino_completo` | `[x] Verde` |
| `AC-REF-05-06` | `T-REF-05-02` | `test_AC_REF_05_06_sin_consentimiento_no_se_guarda_la_agencia` | `[x] Verde` |
| `AC-REF-05-07` | `T-REF-05-03` | `test_AC_REF_05_07_sin_agencia_preferida_no_se_crea_el_caso`, `test_AC_REF_05_07_si_el_consentimiento_se_rechazo_tampoco_se_crea_el_caso` | `[x] Verde` |
| `AC-REF-05-08` | `T-REF-05-03`, `T-REF-05-08` | `test_AC_REF_05_08_sin_permiso_registrar_se_deniega_con_asiento`, `test_AC_REF_05_08_sin_permiso_responde_403_y_no_crea_el_caso` | `[x] Verde` |
| `AC-REF-05-09` | `T-REF-05-03`, `T-REF-05-08` | `test_AC_REF_05_09_la_misma_clave_no_abre_un_segundo_caso`, `test_AC_REF_05_09_el_doble_toque_no_abre_un_segundo_caso_por_http` | `[x] Verde` |
| `AC-REF-05-10` | `T-REF-05-04` | `test_AC_REF_05_10_cola_llena_guarda_en_tramite_y_publica_cuando_hay_lugar` | `[x] Verde` |
| `AC-REF-05-11` | `T-REF-05-04` | `test_AC_REF_05_11_cola_llena_agotados_los_reintentos_queda_sin_entregar` | `[x] Verde` |
| `AC-REF-05-12` | `T-REF-05-07`, `T-REF-05-08` | `test_AC_REF_05_12_reintentar_vuelve_a_en_tramite_y_republica_el_mismo_pedido`, `test_AC_REF_05_12_y_13_reintentar_por_http` | `[x] Verde` |
| `AC-REF-05-13` | `T-REF-05-07`, `T-REF-05-08` | `test_AC_REF_05_13_reintentar_un_caso_que_no_esta_sin_entregar_se_rechaza`, `test_AC_REF_05_12_y_13_reintentar_por_http` | `[x] Verde` |
| `AC-REF-05-14` | `T-REF-05-06` | `test_AC_REF_05_14_clave_invalida_no_consulta_ni_publica` | `[x] Verde` |
| `AC-REF-05-15` | `T-REF-05-01`, `T-REF-05-06` | `test_AC_REF_05_15_la_regla_de_avance_ignora_lo_que_retrocede`, `test_AC_REF_05_15_una_novedad_que_retrocede_el_estado_se_ignora` | `[x] Verde` |
| `AC-REF-05-16` | `T-REF-05-05`, `T-REF-05-08` | `test_AC_REF_05_16_una_segunda_agencia_recibe_el_pedido_sin_cambios_en_el_orquestador`, `test_AC_REF_05_16_una_segunda_agencia_atiende_sin_cambios_en_el_orquestador` | `[x] Verde` |
| `AC-REF-05-17` | `T-REF-05-03`, `T-REF-05-05` | `test_AC_REF_05_17_el_resumen_del_dialogo_queda_en_el_caso_y_en_el_pedido`, `test_AC_REF_05_17_el_resumen_del_dialogo_llega_a_la_agencia` | `[x] Verde` |

## Estrategia de Pruebas y Simulación de Fallos

* **Tests unitarios / contractuales:** la regla de avance de estados se prueba para cada par de estados. El Adaptador se prueba con `MockAgencia` y un `Broker` real con colas de 5 y espera inyectada. El Orquestador usa las dos bases reales (marca `db`).
* **Inyección de fallos:**
  * Agencia caída o lenta: `MockAgencia` lanza error o demora a demanda (`AC-REF-05-03`, `AC-REF-05-04`); tras 3 reintentos el pedido va a mensajes muertos y se publica «sin entregar».
  * Cola de casos llena (`AC-REF-05-10`, `AC-REF-05-11`): se llenan los 5 lugares; el Orquestador reintenta con espera inyectada. Un test libera un lugar a mitad de los reintentos y verifica que el pedido se publica.
  * Aviso con clave inválida o con el estado de un caso desconocido para la agencia (`AC-REF-05-14`): el mock cuenta las consultas y el test verifica que no hubo ninguna.
  * Novedad repetida o que retrocede: se publica el mismo identificador dos veces y un estado anterior.
* **Auditoría:** reportar y reintentar dejan asiento permitido, denegado o rechazado, verificado en ambas bases.
* **Punta a punta (`T-REF-05-08`):** un reporte recorre el Orquestador, la cola de casos, el Adaptador, la agencia simulada, el aviso, `consultarCaso`, la cola de novedades, la ingesta y el Orquestador, hasta «resuelto».
* **Comando de ejecución:** `.venv/bin/pytest tests/test_ref05_*.py` (con `docker compose up -d --wait`).

## Riesgos Técnicos del Plan

* **Cambia la ingesta de REF-03.** Hoy solo entiende reservas del correo. Mitigación: el despacho por `origen` es aditivo y los tests de REF-03 deben seguir en verde.
* **Pedidos sin publicar si el proceso muere** (según la Decisión 1). Mitigación en las opciones de abajo.
* **«Sin entregar» no llega si la cola de novedades también está llena.** El Adaptador reintenta publicar esa novedad con la misma espera; si no hay lugar, queda en mensajes muertos con aviso a operaciones. Es la misma limitación de saturación que ya reconoce `ADR-IT3-002`.
* **Un aviso de la agencia llega antes de que el Orquestador guarde el caso** (el caso aún no existe en la base). La novedad se ignora y la agencia puede avisar de nuevo.
* **Mock de la agencia.** Solo simula `abrirCaso`, `consultarCaso`, demora, caída y avisos; no pretende reproducir una agencia real. Cambia el adaptador, no el contrato.
* **Datos de terceros.** Lo que viaja a la agencia se limita a lo consentido (reserva afectada, descripción y resumen del diálogo). Un test verifica que el pedido no incluye miembros ni otras reservas.
