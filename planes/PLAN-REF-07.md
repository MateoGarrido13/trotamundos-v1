# PLAN-REF-07. Asistente virtual (Chatbot)

* **Spec asociada:** [SPEC-REF-07](../specs/SPEC-REF-07.md) *(estado `aprobada`)*
* **Estado:** terminado
* **Fecha:** 2026-11-23
* **Incremento (Slice):** Slice 5 de [PLAN_MAESTRO.md](PLAN_MAESTRO.md)

Se apoya en lo construido: las operaciones de REF-04 (`agregarReserva`, `actualizarReserva`, `eliminarReserva`, vista del itinerario, novedades), la apertura de caso y la consulta de la agencia preferida de REF-05, el control de acceso y la auditoría del Orquestador. Esta spec agrega un **módulo nuevo, sin estado y en nodos propios**, que interpreta mensajes, pide confirmación y delega todo efecto al Orquestador.

```
Cliente ──► Módulo de Asistente ──filtro──► IMotorConversacional (cota 20 s, Circuit Breaker)
                │   (sin estado: el contexto firmado viaja con el cliente)
                └──► Orquestador (identidad + clave de operación): reservas, caso complejo, agencia preferida
```

## Decisiones Técnicas Locales

Las tres marcadas **[DECISIÓN]** las confirmó el usuario eligiendo la opción A en cada una.

| Decisión | Alternativa elegida | Motivo | ¿Afecta algún driver o requiere ADR? |
| :--- | :--- | :--- | :--- |
| **[DECISIÓN 1 · A]** `AC-REF-07-22` contradecía el time-out de 20 s | Se corrigió el criterio en la spec: una demora menor al time-out (15 s) propone la acción; una mayor (30 s) degrada al número y el menú dentro de los 35 s. El time-out sigue en 20 s | Con un time-out de 20 s, un proveedor que demora 30 s nunca llegaba a proponer una acción | Sí: se cambió el criterio, con registro en el historial de la spec |
| **[DECISIÓN 2 · A]** Qué motor se construye | `MotorSimulado` por reglas de palabras clave, con demora, time-out y caída inyectables | Permite probar y demostrar el asistente sin un proveedor de IA real. No se integra ningún proveedor externo | No |
| **[DECISIÓN 3 · A]** Cómo se elige la reserva de un mensaje | El motor devuelve una referencia y el asistente filtra las reservas del itinerario; si no hay exactamente una, muestra las candidatas | Regla 5 de la spec | No |
| Itinerario del turno | El cliente lo envía en cada pedido (`itinerario_id`), como en REF-04 y REF-05 | El Asistente no guarda estado ni sabe qué itinerarios tiene el actor | No |
| Fronteras | `asistente/` solo conoce `Protocol` definidos en `dominio/puertos_asistente.py`. El Orquestador los implementa en `orquestador/fachada_asistente.py`, que delega en los servicios ya existentes. Se ensamblan en `composicion.py` | El Asistente no importa `orquestador`, `persistencia` ni `entrada` (`AC-REF-07-21`). En el paso 5 la llamada es la interfaz interna del Orquestador | No |
| `IMotorConversacional` | `Protocol` con `async interpretar(mensaje, contexto)`. Devuelve una intención del conjunto cerrado; cualquier otra cosa se trata como `fueraDeAlcance` | Contrato de la spec | No |
| Intención tipada | Modelo con `tipo` (de las seis intenciones), `referencia` (identificador o texto), `cambios` y `motivo`. Un tipo desconocido, un valor mal formado o una excepción al construirla se normalizan a `fueraDeAlcance` | Regla 6 y `AC-REF-07-07` | No |
| Filtro de inyección | Reglas fijas antes del motor: largo máximo de 500 caracteres, caracteres de control y patrones (ignorar instrucciones, mostrar o cambiar las instrucciones internas, adoptar otro rol, marcas que imitan al sistema, en español e inglés). Un rechazo no pasa por el motor y no entra al contexto | `ADR-IT7-001`. Se verifica con un conjunto fijo de al menos 30 mensajes | No |
| Contexto firmado | JSON con acción pendiente (con su clave de operación), últimos 5 mensajes aceptados y vencimiento, firmado con HMAC-SHA256. La clave sale de `TROTA_CLAVE_ASISTENTE`. Firma inválida o vencido: se descarta y la conversación empieza de nuevo | Sin estado en el módulo (`ADR-IT6-001`) | No |
| Escala de tiempos | La cota (35 s), el time-out (20 s) y la apertura del circuito (30 s) se multiplican por un factor de escala configurable; las pruebas usan uno chico | La spec lo declara parámetro, para que las pruebas no esperen los valores reales | No |
| Cota del turno | Todo el turno corre dentro de un `asyncio.timeout` de 35 s. El motor recibe el menor entre 20 s y lo que reste. Si algo agota el turno, la respuesta es el número de la agencia y el menú | `AC-REF-07-08`, `AC-REF-07-22` | No |
| Circuit Breaker | Cerrado, abierto y semi-abierto, con reloj inyectable. Cuentan los fallos consecutivos del motor (time-out o caída); un turno exitoso reinicia la cuenta. En semi-abierto deja pasar una sola llamada de prueba | `ADR-IT7-004` | No |
| Menú guiado | Consultar estado, reprogramar y derivar a la agencia. Se muestra siempre que no se pudo usar el motor (time-out, circuito abierto o rechazo del filtro) | Spec | No |
| Confirmación | Toda acción con efecto se propone y queda en el contexto con su clave de operación. Se ejecuta solo con la acción estructurada «confirmar», que no pasa por el motor. Reintentar la confirmación reusa la clave y el Orquestador no aplica dos veces | `AC-REF-07-02`, `AC-REF-07-18` | No |
| Resumen del diálogo | Armado sin el motor: motivo, reserva afectada y los últimos 5 mensajes aceptados por el filtro | Regla de la spec, para derivar con el motor caído | No |
| Sin agencia preferida | El asistente lo dice y propone elegirla. Nunca muestra otro número | `AC-REF-07-20` | No |
| Qué es «consultar estado» | La reserva (o todas las del itinerario), sus novedades pendientes y los casos del viajero, en un texto corto | La spec no define el contenido | No |
| Permiso denegado | El asistente informa la denegación y ofrece derivar a la agencia. La auditoría ya la dejó el Orquestador | `AC-REF-07-03` | No |
| App del Asistente | FastAPI propia (`trotamundos.asistente.app`): `POST /asistente/turno` y `POST /asistente/accion`, con `X-Viajero-Id`. Separada de las del Orquestador y de los nodos de entrada | Nodos propios, sin estado (`ADR-IT6-001`) | No |
| Viaje de una actividad agregada por el asistente | Si el motor no indica un viaje, la reserva va a `viaje-<itinerario>`, que el Orquestador crea dentro de ese itinerario | La spec no define a qué viaje va. Es el mismo criterio de la gestión manual: el viaje se crea si no existe | No |
| Datos mínimos para agregar | Hacen falta lugar y fecha de inicio; el fin, si falta, es el inicio. Sin eso el asistente pide los datos y no propone nada | No se inventa lo que el viajero no dijo | No |
| Candidatas | Si no hay una única reserva identificada se muestran hasta 10 candidatas; si el itinerario no tiene reservas, el asistente lo dice | Regla 5 | No |
| Listado de reservas por turno | Cada turno que usa el motor pide al Orquestador las reservas vigentes del itinerario, para dárselas al motor como contexto y para resolver la referencia. Sin permiso de ver, la lista va vacía y la denegación queda auditada por el Orquestador | El motor necesita saber qué reservas existen para reconocer una referencia | No |
| Acciones guiadas con una reserva explícita | `reprogramar` con `reserva_id` no pre-valida la existencia ni el permiso: los decide el Orquestador al confirmar, con su rechazo y su asiento | Así la denegación y la auditoría son las de la gestión manual (`AC-REF-07-03`) | No |
| Cuenta y itinerario del contexto | El contexto firmado lleva la cuenta y el itinerario; uno firmado para otra cuenta u otro itinerario se descarta | Evita que una cuenta confirme la acción propuesta a otra | No |
| Falla del Orquestador al confirmar | La acción queda pendiente con la misma clave de operación, y el viajero puede reintentar la confirmación | No se pierde la acción ni se aplica dos veces | No |
| Fallos que cuenta el Circuit Breaker | Time-out y caída del proveedor, no los rechazos del filtro ni las intenciones fuera de alcance | Solo el proveedor puede estar caído | No |
| Respuesta sin agencia | Tipo `sin_agencia`, sin número y con el menú; nunca se muestra un número que no sea el de su agencia | `AC-REF-07-20` | No |

## Estructura de Código y Mapeo Arquitectónico

| Ruta en el repositorio | Elemento del paso 5 que instancia | Dependencias permitidas (imports) | Prohibiciones explícitas |
| :--- | :--- | :--- | :--- |
| `src/trotamundos/dominio/puertos_asistente.py` | Interfaz interna del Orquestador que usa el Asistente | `pydantic` | No importa otro paquete |
| `src/trotamundos/asistente/intenciones.py`, `motor.py` | `IMotorConversacional`, intención tipada y `MotorSimulado` | `dominio`, `asyncio` | No importa `orquestador`, `persistencia`, `entrada` ni `broker` |
| `src/trotamundos/asistente/filtro.py` | Filtrado de inyección de prompt | biblioteca estándar | Ídem |
| `src/trotamundos/asistente/contexto.py` | Contexto firmado | biblioteca estándar | Ídem |
| `src/trotamundos/asistente/circuito.py` | Circuit Breaker | biblioteca estándar | Ídem |
| `src/trotamundos/asistente/asistente.py` | Módulo de Asistente Virtual (turno y acciones guiadas) | `dominio`, `asistente.*`, `config` | **No lee ni escribe ninguna base, no llama a la agencia y no guarda estado entre turnos** |
| `src/trotamundos/asistente/app.py` | Endpoints para Cliente web y móvil | `fastapi`, `asistente.asistente` | Ídem |
| `src/trotamundos/orquestador/fachada_asistente.py` | Orquestador: implementa la interfaz interna usando los servicios existentes | `dominio`, `orquestador.*` | No importa `asistente` |
| `src/trotamundos/composicion.py`, `config.py` | Ensamble y parámetros del asistente | Todos | Es el único lugar que conecta `asistente` con `orquestador` |

Ajustes a `tests/test_arquitectura.py` (aditivos): `asistente` no importa `orquestador`, `persistencia`, `entrada`, `broker` ni `analitica`; `orquestador/fachada_asistente` no importa `asistente`; `dominio/puertos_asistente` no importa nada más del paquete.

## Tareas de Implementación

| ID | Descripción de la tarea | Archivos a crear / modificar | AC que cubre | Depende de | Criterio de terminado (Done) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `T-REF-07-01` | Puertos del Orquestador, intención tipada, `IMotorConversacional`, `MotorSimulado` y configuración | `dominio/puertos_asistente.py`, `asistente/intenciones.py`, `asistente/motor.py`, `config.py`, `tests/test_ref07_modelo.py` | `AC-REF-07-07` | — | Una intención fuera del conjunto cerrado se normaliza a `fueraDeAlcance` |
| `T-REF-07-02` | Filtro de inyección y conjunto fijo de 30 mensajes de inyección | `asistente/filtro.py`, `tests/test_ref07_filtro.py` | `AC-REF-07-05` | `T-REF-07-01` | Los 30 mensajes se rechazan; mensajes legítimos pasan |
| `T-REF-07-03` | Contexto firmado: firma, vencimiento y descarte | `asistente/contexto.py`, `tests/test_ref07_contexto.py` | `AC-REF-07-16`, `AC-REF-07-17` | `T-REF-07-01` | Firma alterada o vencido: se descarta y no queda ninguna acción pendiente |
| `T-REF-07-04` | Circuit Breaker, time-out del motor y cota del turno, con tiempos escalables | `asistente/circuito.py`, `asistente/asistente.py`, `tests/test_ref07_circuito.py`, `tests/test_ref07_tiempos.py` | `AC-REF-07-08`, `AC-REF-07-10`, `AC-REF-07-11`, `AC-REF-07-12`, `AC-REF-07-13`, `AC-REF-07-22` | `T-REF-07-01` | Cinco fallos abren el circuito; con el circuito abierto la respuesta sale en menos de 100 ms sin llamar al proveedor |
| `T-REF-07-05` | Núcleo del turno: filtro, motor, intención, propuesta, reserva ambigua y fuera de alcance | `asistente/asistente.py`, `tests/test_ref07_turno.py` | `AC-REF-07-01` (propuesta), `AC-REF-07-06`, `AC-REF-07-18`, `AC-REF-07-19` | `T-REF-07-02`, `T-REF-07-03`, `T-REF-07-04` | Una intención de las seis se resuelve o se propone; sin una única reserva no se ejecuta nada |
| `T-REF-07-06` | Fachada del Orquestador y confirmación de las escrituras de primer nivel, con identidad, clave y permisos | `orquestador/fachada_asistente.py`, `asistente/asistente.py`, `tests/test_ref07_escrituras.py` | `AC-REF-07-01`, `AC-REF-07-02`, `AC-REF-07-03` | `T-REF-07-05` | Confirmar llama a `actualizarReserva`; reintentar con la misma clave no aplica dos veces; sin permiso, rechazo y asiento |
| `T-REF-07-07` | Caso complejo y derivación: clasificación, resumen determinista, agencia preferida y sin agencia | `asistente/asistente.py`, `orquestador/fachada_asistente.py`, `tests/test_ref07_caso_complejo.py` | `AC-REF-07-04`, `AC-REF-07-09`, `AC-REF-07-14`, `AC-REF-07-20` | `T-REF-07-06` | El caso se abre por el Orquestador, nunca contra la agencia; sin agencia no se muestra otro número |
| `T-REF-07-08` | Acciones guiadas sin motor, app del Asistente, aislamiento y prueba de punta a punta | `asistente/asistente.py`, `asistente/app.py`, `composicion.py`, `tests/test_ref07_acciones.py`, `tests/test_ref07_api.py`, `tests/test_ref07_aislamiento.py` | `AC-REF-07-15`, `AC-REF-07-21`, `AC-REF-07-04` (de punta a punta) | `T-REF-07-07` | Consultar, reprogramar y derivar funcionan con el motor caído; el módulo no tiene credenciales de base ni de la agencia |

## Matriz de Cobertura de Criterios de Aceptación

Ningún `AC` de la spec puede quedar sin tarea ni sin test asociado. Los tests de tiempos usan un factor de escala de 0,02 (35 s → 0,7 s, 20 s → 0,4 s, 30 s → 0,6 s).

| Criterio de Aceptación (Spec) | Tarea(s) del Plan | Nombre del test automatizado | Estado |
| :--- | :--- | :--- | :--- |
| `AC-REF-07-01` | `T-REF-07-05`, `T-REF-07-06` | `test_AC_REF_07_01_reprogramar_se_propone_y_espera_la_confirmacion`, `test_AC_REF_07_01_reprogramar_se_propone_y_al_confirmar_llama_a_actualizar_reserva` | `[x] Verde` |
| `AC-REF-07-02` | `T-REF-07-06` | `test_AC_REF_07_02_reintentar_la_confirmacion_no_aplica_la_reprogramacion_dos_veces` | `[x] Verde` |
| `AC-REF-07-03` | `T-REF-07-06` | `test_AC_REF_07_03_sin_permiso_no_se_escribe_queda_auditado_y_se_ofrece_derivar` | `[x] Verde` |
| `AC-REF-07-04` | `T-REF-07-07`, `T-REF-07-08` | `test_AC_REF_07_04_un_caso_complejo_se_abre_por_el_orquestador_y_queda_en_tramite` | `[x] Verde` |
| `AC-REF-07-05` | `T-REF-07-02` | `test_AC_REF_07_05_cada_inyeccion_se_rechaza` (32 mensajes), `test_AC_REF_07_05_ninguna_inyeccion_alcanza_al_motor_y_todas_ofrecen_el_numero` | `[x] Verde` |
| `AC-REF-07-06` | `T-REF-07-05` | `test_AC_REF_07_06_los_pedidos_fuera_de_proposito_reciben_el_mismo_rechazo` | `[x] Verde` |
| `AC-REF-07-07` | `T-REF-07-01` | `test_AC_REF_07_07_una_intencion_fuera_del_conjunto_cerrado_se_trata_como_fuera_de_alcance`, `test_AC_REF_07_07_una_intencion_fuera_del_conjunto_cerrado_no_ejecuta_nada` | `[x] Verde` |
| `AC-REF-07-08` | `T-REF-07-04` | `test_AC_REF_07_08_sin_proveedor_el_viajero_ve_el_numero_y_el_menu_dentro_de_la_cota` | `[x] Verde` |
| `AC-REF-07-09` | `T-REF-07-07` | `test_AC_REF_07_09_el_100_por_ciento_de_las_consultas_sin_proveedor_recibe_el_numero` | `[x] Verde` |
| `AC-REF-07-10` | `T-REF-07-04` | `test_AC_REF_07_10_con_el_circuito_abierto_la_respuesta_sale_en_menos_de_100_ms` | `[x] Verde` |
| `AC-REF-07-11` | `T-REF-07-04` | `test_AC_REF_07_11_a_los_30_segundos_pasa_a_semiabierto_y_deja_pasar_una_sola_llamada`, `test_AC_REF_07_11_pasa_a_semiabierto_y_una_sola_llamada_de_prueba_decide`, `test_AC_REF_07_11_si_la_llamada_de_prueba_responde_se_cierra`, `test_AC_REF_07_11_si_la_llamada_de_prueba_falla_el_circuito_vuelve_a_abrirse` | `[x] Verde` |
| `AC-REF-07-12` | `T-REF-07-04` | `test_AC_REF_07_12_un_exito_reinicia_la_cuenta_y_hacen_falta_cinco_nuevos`, `test_AC_REF_07_12_un_turno_exitoso_reinicia_la_cuenta_de_timeouts` | `[x] Verde` |
| `AC-REF-07-13` | `T-REF-07-04` | `test_AC_REF_07_13_el_timeout_degrada_a_menu_y_numero_sin_retry_bloqueante` | `[x] Verde` |
| `AC-REF-07-14` | `T-REF-07-07` | `test_AC_REF_07_14_derivar_con_el_motor_caido_arma_el_resumen_sin_el_motor` | `[x] Verde` |
| `AC-REF-07-15` | `T-REF-07-08` | `test_AC_REF_07_15_consultar_y_reprogramar_por_el_menu_funcionan_sin_motor` | `[x] Verde` |
| `AC-REF-07-16` | `T-REF-07-03` | `test_AC_REF_07_16_un_contexto_con_la_firma_alterada_se_descarta`, `test_AC_REF_07_16_un_contexto_alterado_por_la_red_se_descarta` | `[x] Verde` |
| `AC-REF-07-17` | `T-REF-07-03` | `test_AC_REF_07_17_un_contexto_vencido_se_descarta` | `[x] Verde` |
| `AC-REF-07-18` | `T-REF-07-05` | `test_AC_REF_07_18_confirmar_sin_accion_pendiente_se_rechaza_sin_efecto` | `[x] Verde` |
| `AC-REF-07-19` | `T-REF-07-05` | `test_AC_REF_07_19_una_intencion_ambigua_muestra_las_candidatas_y_no_ejecuta` | `[x] Verde` |
| `AC-REF-07-20` | `T-REF-07-07` | `test_AC_REF_07_20_sin_agencia_preferida_propone_elegirla_sin_mostrar_otro_numero` | `[x] Verde` |
| `AC-REF-07-21` | `T-REF-07-08` | `test_AC_REF_07_21_el_modulo_no_tiene_credenciales_de_base_ni_de_agencia`, `test_AC_REF_07_21_ningun_archivo_del_modulo_importa_una_base_ni_al_orquestador_ni_a_la_agencia`, `test_AC_REF_07_21_no_guarda_estado_entre_turnos` | `[x] Verde` |
| `AC-REF-07-22` | `T-REF-07-04` | `test_AC_REF_07_22_una_demora_menor_al_timeout_propone_la_accion_dentro_de_la_cota`, `test_AC_REF_07_22_una_demora_mayor_al_timeout_degrada_al_numero_y_el_menu_dentro_de_la_cota` | `[x] Verde` |

## Estrategia de Pruebas y Simulación de Fallos

* **Tests unitarios / contractuales:** el filtro, el contexto, el Circuit Breaker y la normalización de intenciones se prueban sin base ni red. Las escrituras de primer nivel usan el Orquestador real y las dos bases (marca `db`) a través de la fachada.
* **Inyección de fallos y de tiempo:**
  * Motor simulado con demora, time-out o caída a demanda.
  * Reloj y esperas inyectables y factor de escala (por ejemplo, un décimo): los tests no esperan los 35 s reales.
  * Circuito: cinco fallos abren; se avanza el reloj 30 s para pasar a semi-abierto; una llamada de prueba exitosa cierra y una fallida vuelve a abrir.
  * Respuesta con el circuito abierto: se mide que sale en menos de 100 ms y que el motor no recibió ninguna llamada.
* **Seguridad (`QA-SEG-04`):** un conjunto fijo de al menos 30 mensajes de inyección que no deben llegar al motor (el motor del test falla si lo reciben) y un conjunto fijo de pedidos fuera de propósito que el motor clasifica como `fueraDeAlcance`.
* **Aislamiento (`AC-REF-07-21`):** la configuración del asistente no tiene campos de base ni de agencia, el módulo no importa persistencia ni orquestador, y dos conversaciones intercaladas con contextos distintos no se contaminan.
* **Comando de ejecución:** `.venv/bin/pytest tests/test_ref07_*.py` (con `docker compose up -d --wait` para los `db`).

## Riesgos Técnicos del Plan

* **`AC-REF-07-22` se corrigió en la spec** (Decisión 1). Mitigación: el test cubre las dos demoras, la menor y la mayor al time-out.
* **El filtro de patrones no es infalible.** La spec lo declara una simplificación y exige solo que el conjunto fijo de 30 mensajes se rechace. Un mensaje legítimo que coincida con un patrón recibiría el rechazo y el menú; es el costo aceptado.
* **El texto del viajero llegaría a un proveedor de IA externo.** La spec lo deja fuera de alcance. Con el motor simulado no sale del proceso.
* **Modifica `composicion.py` y la configuración.** Cambios aditivos; los tests anteriores deben seguir en verde.
* **El estado vive en el cliente.** Un cliente que no devuelve el contexto pierde la acción pendiente; es el diseño (módulo sin estado).
