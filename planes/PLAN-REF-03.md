# PLAN-REF-03. Filtros y whitelists

* **Spec asociada:** [SPEC-REF-03](../specs/SPEC-REF-03.md) *(estado `aprobada`)*
* **Estado:** terminado
* **Fecha:** 2026-11-23
* **Incremento (Slice):** Slice 3 de [PLAN_MAESTRO.md](PLAN_MAESTRO.md)

Se apoya en lo ya construido: el Parseo aislado y el `ConsumidorCorreo` de REF-02 (que entregan a `FiltroRemitentes.recibir`), el `Broker` y su cola de mensajes muertos, y de REF-01 el `RepositorioViajes`, `BaseViajes` (commit en dos fases) y el `RegistroTipos`. Esta spec cierra el camino del correo: Parseo → Filtro de remitentes → Servicio de ingesta → Orquestador → itinerario.

## Decisiones Técnicas Locales

| Decisión | Alternativa elegida | Motivo | ¿Afecta algún driver o requiere ADR? |
| :--- | :--- | :--- | :--- |
| Fronteras entre nodos | El Filtro y la Ingesta (nodos de entrada) hablan con el Orquestador solo a través de `Protocol` definidos en `dominio/puertos_correo.py`: `AlmacenRevision`, `EntregaOrquestador` e `Ingesta`, más `LiberadorDeRevision` para el aviso de aprobación. El Orquestador los implementa. Se ensamblan en `composicion.py` | El paso 5 usa HTTP/REST interno síncrono entre estas piezas. En el prototipo es una llamada a método detrás de un `Protocol`, como en las demás simplificaciones. Respeta la prohibición `entrada` → `orquestador` | No (misma simplificación que la spec permite para APIs externas; el contrato no cambia) |
| Almacén de whitelist y revisión | Tablas `remitente_seguro` y `mensaje_revision` en la Base primaria de viajes, escritas por `BaseViajes` (commit en dos fases). Esquema `03_revision.sql` | El Orquestador es dueño de lo que se guarda (paso 5). Un `.sql` por spec evita conflictos | No |
| Comparación de remitentes | Se normaliza a minúsculas y sin espacios en los extremos antes de comparar o guardar | La spec no lo define; evita que `Ana@x.com` y `ana@x.com` sean dos remitentes | No |
| Mensaje en revisión | Fila por `(titular_id, id_mensaje)` con `remitente`, la reserva normalizada en JSONB, `estado` (`pendiente` / `descartado`) y `creado_en`. El descartado conserva solo identificador y fecha | Regla 4 de la spec: el descartado no reaparece | No |
| Idempotencia del filtro | La clave es `(titular_id, id_mensaje)`: si ya está pendiente o descartado, se ignora | Reglas 4 y 6 | No |
| Tope alcanzado | El mensaje no se retiene y el filtro termina sin error ni reintento. Vuelve en un sondeo posterior mientras esté en la ventana | Contrato «Filtrar remitente» de la spec | No |
| Aprobar | 1) agrega a la whitelist (idempotente); 2) lee los pendientes de ese remitente; 3) los libera hacia la ingesta; 4) recién entonces los borra de revisión. Aprobar un remitente ya aprobado también libera lo que haya quedado pendiente | Si la liberación falla, el mensaje no se pierde y aprobar de nuevo lo reintenta; la ingesta descarta el duplicado | No |
| Descartar | Pasa un `pendiente` del titular a `descartado`. Si no existe, no es suyo o ya está resuelto: error 404 sin cambios | Contrato de la spec | No |
| Retención | 30 días, configurable. `ConfiguracionRevision` rechaza un valor menor que la ventana de sondeo de REF-02. Una tarea periódica llama a `purgar(ahora)`, con el mismo patrón de `archivado.tarea_periodica` | Regla 7 y `AC-REF-03-11` | No |
| Cola de la ingesta | La ingesta recibe del Filtro publicando en la cola `novedades` del Broker (el paso 5 dice que la ingesta toma de esa cola y del Filtro), con el cuerpo `{origen: "correo", reserva: ...}`. Un consumidor de la ingesta la procesa con el Retry y la cola de mensajes muertos del Broker | Reutiliza Retry, backoff y mensajes muertos ya probados (`AC-REF-03-15`). No agrega una sexta cola, que el Plan Maestro no prevé | No |
| Idempotencia de la ingesta | Registro en memoria de identificadores ya entregados, con retención de 7 días (parámetro de SPEC-REF-02, nunca menor que la ventana de sondeo). Se marca como procesado **después** de entregar | Si se marcara antes, un reintento tras un fallo se descartaría y se perdería la reserva | No |
| Límite de tasa | Limitador de ventana con reloj y espera inyectables, 20 mensajes por segundo (parámetro de SPEC-REF-02) | Los tests no esperan tiempo real | No |
| Entrega al Orquestador | `IncorporadorReservas.incorporar(reserva_normalizada)`: construye la clase concreta con el `RegistroTipos` y escribe viaje y reserva en **una sola** escritura de dos fases, con `ON CONFLICT DO NOTHING` | Una entrega repetida tras un timeout no falla ni duplica | No |
| Viaje de una reserva del correo | **La spec no lo define.** Cada reserva del correo crea su propio viaje (`viaje-<identificador>`) del titular. Agrupar varias reservas en un mismo viaje queda para la gestión manual de SPEC-REF-04 | Es lo más simple que no inventa una regla de agrupación. A confirmar con `OK PLAN` | No |
| Campo `codigo` | Las cinco clases concretas de `Reserva` ganan un campo opcional `codigo`, que viaja en la columna `datos` | El esquema de correo trae `codigo` y el contrato `Reserva` no tiene dónde guardarlo. Es el uso previsto de `datos` | No |
| Tipo de reserva desconocido | Si `tipo` no está en el Registro, la entrega falla de forma permanente: tras los reintentos va a mensajes muertos con aviso | La spec solo descarta lo que no valida el parseo. No se pierde en silencio | No |
| API del titular | Endpoints en el Orquestador, con `X-Viajero-Id`: `GET /revision`, `POST /revision/remitentes`, `DELETE /revision/remitentes`, `POST /revision/descartar`. Los ids de mensaje van en el cuerpo porque llevan `<`, `>` y `@` | La consulta, la aprobación y el descarte los hace el titular por el API Gateway | No |
| Identificador de la reserva | `<titular_id>:<id_mensaje>` (propiedad `ReservaNormalizada.identificador_reserva`). Lo usan la ingesta (clave de duplicados), el Orquestador (identificador de la `Reserva` y del viaje) y el repositorio de revisión | Un mismo correo enviado a dos titulares comparte `Message-ID`: sin el titular, la segunda reserva se descartaría o chocaría con la clave primaria | No |
| Mensaje ya incorporado | `retener` trata como duplicado a todo mensaje cuya reserva ya está en el itinerario. Por eso, al quitar a un remitente, el correo viejo que sigue en la ventana de sondeo no reaparece en revisión | Se hizo al implementar: el test de punta a punta mostró el reaparecido. Cierra la limitación que este plan había dejado como riesgo | No |
| Quitar remitente por HTTP | `DELETE /revision/remitentes/{remitente}` (el remitente va en la ruta, sin cuerpo). Solo los identificadores de mensaje, que llevan `<`, `>` y `@`, van en el cuerpo | Un `DELETE` sin cuerpo se transporta mejor por proxies y gateways | No |

## Estructura de Código y Mapeo Arquitectónico

| Ruta en el repositorio | Elemento del paso 5 que instancia | Dependencias permitidas (imports) | Prohibiciones explícitas |
| :--- | :--- | :--- | :--- |
| `src/trotamundos/dominio/puertos_correo.py` | Fronteras del Filtro, la Ingesta y el Orquestador (`Protocol`) | `dominio.reserva_normalizada` | No importa ningún otro paquete |
| `src/trotamundos/entrada/filtro_remitentes.py` | Filtro de remitentes (ya existe el `Protocol`; se agrega `FiltroWhitelist`) | `dominio` | **No importa `persistencia` ni `orquestador`**: no guarda nada ni escribe la reserva |
| `src/trotamundos/entrada/ingesta.py` | Servicio de ingesta: consumidor, registro de duplicados, limitador de tasa | `dominio`, `broker`, `config` | **No importa `persistencia`**: la ingesta nunca escribe en la base. No importa `orquestador` |
| `src/trotamundos/orquestador/revision.py` | Orquestador de viajes: operaciones del titular y `AlmacenRevision`; tarea periódica de purga | `dominio`, `persistencia.repositorio_revision`, `config` | No importa `entrada` |
| `src/trotamundos/persistencia/repositorio_revision.py` | Whitelist y Mensajes en revisión en la Base primaria, con escritura por `BaseViajes` | `dominio`, `persistencia.base_viajes` | No importa `orquestador` ni `entrada` |
| `src/trotamundos/orquestador/incorporacion.py` | Orquestador de viajes: recibe lo que entrega la ingesta | `dominio`, `persistencia.repositorio_viajes` | No importa `entrada`. No conoce tipos concretos |
| `src/trotamundos/orquestador/api_revision.py` | Endpoints del titular (Cliente web y móvil) | `fastapi`, `orquestador.revision` | No lee ni escribe ninguna Base de cuentas |
| `src/trotamundos/persistencia/esquemas/03_revision.sql` | Tablas de whitelist y revisión en la Base primaria | — | Sin cuentas ni sesiones |
| `src/trotamundos/composicion.py` | Ensamble de los nodos de entrada y el Orquestador | Todos | Es el único lugar que conecta `entrada` con `orquestador` |

Ajuste a `tests/test_arquitectura.py` (aditivo): `entrada/filtro_remitentes.py` e `entrada/ingesta.py` no importan `trotamundos.persistencia`; `dominio/puertos_correo.py` no importa nada más del paquete.

## Tareas de Implementación

| ID | Descripción de la tarea | Archivos a crear / modificar | AC que cubre | Depende de | Criterio de terminado (Done) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `T-REF-03-01` | Puertos, `ConfiguracionRevision` (retención 30 días, tope 50, validación contra la ventana de sondeo) y límites de la ingesta en la configuración | `dominio/puertos_correo.py`, `config.py`, `tests/test_ref03_config.py` | `AC-REF-03-11` (base de la retención) | — | Una retención menor que la ventana de sondeo se rechaza al construir la configuración |
| `T-REF-03-02` | Esquema `03_revision.sql` y `RepositorioRevision`: whitelist, retener (idempotente, con tope), descartar, pendientes por remitente, borrar liberados, purgar | `persistencia/esquemas/03_revision.sql`, `persistencia/repositorio_revision.py`, `tests/conftest.py`, `tests/test_ref03_repositorio.py` | `AC-REF-03-05`, `AC-REF-03-06`, `AC-REF-03-07`, `AC-REF-03-11` | `T-REF-03-01` | Tests `db` en verde; las escrituras quedan en primaria y pasiva |
| `T-REF-03-03` | `ServicioRevision`: consultar, aprobar o dar de alta, quitar, descartar y purgar, con la liberación hacia la ingesta. Tarea periódica de purga | `orquestador/revision.py`, `app.py`, `tests/test_ref03_servicio.py` | `AC-REF-03-03`, `AC-REF-03-08`, `AC-REF-03-09` (quitar), `AC-REF-03-10`, `AC-REF-03-12` | `T-REF-03-02` | Aprobar libera lo pendiente una sola vez; descartar algo inexistente no cambia datos |
| `T-REF-03-04` | `FiltroWhitelist`: remitente seguro hacia la ingesta, desconocido a revisión, idempotente por identificador, sin retener lo ya descartado | `entrada/filtro_remitentes.py`, `tests/test_ref03_filtro.py` | `AC-REF-03-01`, `AC-REF-03-02`, `AC-REF-03-04`, `AC-REF-03-05`, `AC-REF-03-06` | `T-REF-03-01` | Con un `AlmacenRevision` en memoria, los cinco escenarios en verde |
| `T-REF-03-05` | Servicio de ingesta: publicación del Filtro, consumidor, registro de duplicados, limitador de tasa, Retry y mensajes muertos | `entrada/ingesta.py`, `tests/test_ref03_ingesta.py` | `AC-REF-03-13`, `AC-REF-03-14`, `AC-REF-03-15` | `T-REF-03-01` | Un duplicado llega una sola vez; la tasa nunca supera 20/s; un fallo persistente va a mensajes muertos con aviso |
| `T-REF-03-06` | `IncorporadorReservas` y escritura única de viaje y reserva; campo `codigo` en los cinco tipos | `orquestador/incorporacion.py`, `persistencia/repositorio_viajes.py`, `dominio/tipos_reserva.py`, `tests/test_ref03_incorporacion.py` | `AC-REF-03-16` (parte del Orquestador), `AC-REF-03-13` | `T-REF-03-02` | Entregar dos veces la misma reserva deja una sola; un tipo desconocido falla |
| `T-REF-03-07` | Endpoints del titular sobre `ServicioRevision` | `orquestador/api_revision.py`, `app.py`, `tests/test_ref03_api.py` | `AC-REF-03-10`, `AC-REF-03-12`, `AC-REF-03-03`, `AC-REF-03-09` | `T-REF-03-03` | Lista vacía sin mensajes; 404 al descartar algo inválido; sin `X-Viajero-Id`, 422 |
| `T-REF-03-08` | Ensamble (`composicion.py`) y pruebas de punta a punta con el Parseo real, el Filtro, la Ingesta y las bases PostgreSQL | `composicion.py`, `tests/test_ref03_punta_a_punta.py` | `AC-REF-03-16`, `AC-REF-03-01`, `AC-REF-03-03`, `AC-REF-03-09` (reserva ya incorporada permanece) | `T-REF-03-03`, `T-REF-03-04`, `T-REF-03-05`, `T-REF-03-06` | Tres sondeos del mismo mensaje dejan una sola reserva en el itinerario |

## Matriz de Cobertura de Criterios de Aceptación

Ningún `AC` de la spec puede quedar sin tarea ni sin test asociado.

| Criterio de Aceptación (Spec) | Tarea(s) del Plan | Nombre del test automatizado | Estado |
| :--- | :--- | :--- | :--- |
| `AC-REF-03-01` | `T-REF-03-04`, `T-REF-03-08` | `test_AC_REF_03_01_remitente_seguro_pasa_a_la_ingesta`, `test_AC_REF_03_01_remitente_seguro_entra_al_itinerario_de_punta_a_punta` | `[x] Verde` |
| `AC-REF-03-02` | `T-REF-03-04`, `T-REF-03-08` | `test_AC_REF_03_02_remitente_desconocido_queda_en_revision`, `test_AC_REF_03_02_y_03_desconocido_espera_y_al_aprobar_entra_al_itinerario` | `[x] Verde` |
| `AC-REF-03-03` | `T-REF-03-03`, `T-REF-03-07`, `T-REF-03-08` | `test_AC_REF_03_03_aprobar_remitente_libera_la_reserva_retenida`, `test_AC_REF_03_03_aprobar_por_http_libera_hacia_la_ingesta` | `[x] Verde` |
| `AC-REF-03-04` | `T-REF-03-04` | `test_AC_REF_03_04_contenido_invalido_no_llega_a_revision` | `[x] Verde` |
| `AC-REF-03-05` | `T-REF-03-02`, `T-REF-03-04` | `test_AC_REF_03_05_mismo_mensaje_deja_una_sola_entrada_en_revision`, `test_AC_REF_03_05_mismo_mensaje_deja_una_sola_entrada_en_revision_en_el_filtro` | `[x] Verde` |
| `AC-REF-03-06` | `T-REF-03-02`, `T-REF-03-04` | `test_AC_REF_03_06_tope_alcanzado_no_retiene_ni_pierde`, `test_AC_REF_03_06_tope_alcanzado_no_retiene_ni_falla` | `[x] Verde` |
| `AC-REF-03-07` | `T-REF-03-02` | `test_AC_REF_03_07_descartado_no_reaparece_en_pendientes` | `[x] Verde` |
| `AC-REF-03-08` | `T-REF-03-03` | `test_AC_REF_03_08_alta_directa_del_remitente_libera_la_reserva` | `[x] Verde` |
| `AC-REF-03-09` | `T-REF-03-03`, `T-REF-03-07`, `T-REF-03-08` | `test_AC_REF_03_09_quitar_remitente_manda_lo_nuevo_a_revision`, `test_AC_REF_03_09_quitar_remitente_por_http_no_es_error_si_no_esta`, `test_AC_REF_03_09_quitar_remitente_manda_lo_nuevo_a_revision_y_conserva_lo_incorporado` | `[x] Verde` |
| `AC-REF-03-10` | `T-REF-03-03`, `T-REF-03-07` | `test_AC_REF_03_10_sin_mensajes_en_revision_devuelve_lista_vacia`, `test_AC_REF_03_10_sin_mensajes_en_revision_devuelve_lista_vacia_por_http` | `[x] Verde` |
| `AC-REF-03-11` | `T-REF-03-01`, `T-REF-03-02`, `T-REF-03-03` | `test_AC_REF_03_11_mensaje_vencido_se_elimina_de_revision`, `test_AC_REF_03_11_purga_elimina_lo_que_cumplio_la_retencion`, `test_AC_REF_03_11_retencion_menor_que_la_ventana_de_sondeo_se_rechaza` | `[x] Verde` |
| `AC-REF-03-12` | `T-REF-03-03`, `T-REF-03-07` | `test_AC_REF_03_12_descartar_inexistente_o_ajeno_se_rechaza_sin_cambios`, `test_AC_REF_03_12_descartar_por_http_rechaza_inexistente_o_ajeno_sin_cambios` | `[x] Verde` |
| `AC-REF-03-13` | `T-REF-03-05`, `T-REF-03-06` | `test_AC_REF_03_13_ingesta_descarta_identificador_ya_procesado`, `test_AC_REF_03_13_entregar_dos_veces_la_misma_reserva_deja_una` | `[x] Verde` |
| `AC-REF-03-14` | `T-REF-03-05` | `test_AC_REF_03_14_entrega_no_supera_el_limite_de_tasa` | `[x] Verde` |
| `AC-REF-03-15` | `T-REF-03-05` | `test_AC_REF_03_15_entrega_fallida_agota_reintentos_y_va_a_mensajes_muertos` | `[x] Verde` |
| `AC-REF-03-16` | `T-REF-03-06`, `T-REF-03-08` | `test_AC_REF_03_16_tres_sondeos_del_mismo_mensaje_dejan_una_sola_reserva` | `[x] Verde` |

## Estrategia de Pruebas y Simulación de Fallos

* **Tests unitarios / contractuales:** el Filtro y la Ingesta se prueban con dobles en memoria de `AlmacenRevision` y `EntregaOrquestador`. El repositorio, el servicio y la incorporación usan las dos bases reales (marca `db`), con la fixture `bases_limpias` ampliada para recrear las tablas nuevas.
* **Inyección de fallos / latencia:**
  * Entrega fallida de la ingesta al Orquestador: un doble que lanza error (timeout simulado), una vez para comprobar que el reintento no duplica y siempre para llegar a mensajes muertos (`AC-REF-03-15`).
  * Cola llena de la ingesta: la cola `novedades` con tamaño 5 hace fallar al Filtro, y el Broker reintenta el mensaje del correo.
  * Pico por encima del límite de tasa (`AC-REF-03-14`): se encolan 100 reservas con un reloj y una espera inyectados, y el test verifica que en ninguna ventana de 1 s virtual hay más de 20 entregas.
  * Retención (`AC-REF-03-11`): `purgar(ahora)` con un `ahora` desplazado 31 días.
* **Punta a punta (`AC-REF-03-16`):** el `MockApiCorreo` publica el mismo correo en tres sondeos, el Parseo corre como proceso real, y el test consulta el itinerario real en PostgreSQL: una sola reserva.
* **Comando de ejecución:** `.venv/bin/pytest tests/test_ref03_*.py` (con `docker compose up -d --wait` para los `db`).

## Riesgos Técnicos del Plan

* **La spec no dice a qué viaje va una reserva del correo.** Se decide un viaje por reserva; si el equipo quiere agrupar por destino o fechas, es un cambio de spec, no de código.
* **Reaparición de un mensaje ya incorporado.** Resuelto al implementar: `retener` trata como duplicado a lo que ya está en el itinerario (ver decisiones). Un mensaje cuya reserva se eliminara del itinerario por completo volvería a aceptarse; la baja lógica de SPEC-REF-04 conserva la fila, así que no lo afecta.
* **Registro de duplicados en memoria.** Un reinicio de la ingesta lo vacía. Mitigación: la escritura del Orquestador es idempotente por identificador, así que un duplicado que se cuele no crea una segunda reserva.
* **Reservas de remitentes no verificados guardadas en la base.** Es el riesgo que reconoce `ADR-IT3-008`; se acota con el tope de 50 por titular y la retención de 30 días.
* **Dependencia de `tipos_reserva.py` y `repositorio_viajes.py` (REF-01).** Se modifican de forma aditiva (campo `codigo` y una escritura única); los tests de REF-01 deben seguir en verde.
* **Solapamiento con REF-04 (gestión manual).** `IncorporadorReservas` y la futura `agregarReserva` escribirán sobre las mismas tablas. Mitigación: la incorporación del correo es una entrada propia, sin permisos de itinerario, y no reemplaza al contrato de REF-04.
