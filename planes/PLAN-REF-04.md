# PLAN-REF-04. Gestión manual

* **Spec asociada:** [SPEC-REF-04](../specs/SPEC-REF-04.md) *(estado `aprobada`)*
* **Estado:** terminado
* **Fecha:** 2026-11-23
* **Incremento (Slice):** Slice 4 de [PLAN_MAESTRO.md](PLAN_MAESTRO.md)

Se apoya en REF-01 (modelo de viajes y reservas, `BaseViajes` con commit en dos fases, `RegistroTipos`, `Agrupacion`) y en REF-03 (la reserva del correo ya entra al itinerario). Esta spec agrega lo que hoy no existe: el **itinerario** con sus miembros, el control de acceso, la auditoría, la idempotencia por clave de operación, la baja lógica, `creadoPor` y la precedencia de la edición manual sobre las novedades.

## Decisiones Técnicas Locales

| Decisión | Alternativa elegida | Motivo | ¿Afecta algún driver o requiere ADR? |
| :--- | :--- | :--- | :--- |
| Qué es un itinerario | Contenedor de viajes: `viaje` gana la columna `itinerario_id`. El itinerario individual de un viajero tiene como identificador su propia cuenta (`itinerario_id = viajero_id`). Los itinerarios compartidos se precargan | La spec habla de «reservas del itinerario agrupadas por viaje» y de un itinerario individual con una sola membresía, pero el modelo de REF-01 no tiene itinerarios. Así REF-01 y REF-03 siguen funcionando: sus altas fijan `itinerario_id = viajero_id` | No |
| Membresías | Tabla `membresia (itinerario_id, cuenta_id, rol)` con roles `organizador` y `participante`. Se precarga con datos de prueba, como fija la spec. Los itinerarios individuales **no** se crean solos: quien use las operaciones manuales necesita su membresía precargada | Simplificación de la spec. Evita inventar una operación de alta de miembros que la spec deja fuera de alcance | No |
| Qué recibe `agregarReserva` | `itinerario_id`, `viaje_id` y los datos de la reserva. Si el viaje existe y es de ese itinerario, la reserva va a él; si no existe, se crea dentro de ese itinerario; si existe en otro itinerario, se rechaza por campos inválidos | La spec no dice a qué viaje va una reserva manual. Es la lectura más simple que respeta el contrato `Reserva` (que ya trae `viaje_id`). Decisión confirmada por el usuario. | No |
| Una sola transacción | Cada operación manual es **una única** escritura de `BaseViajes` (commit en dos fases) que: verifica permiso, revisa la clave de operación, valida, escribe la reserva y el asiento de auditoría y guarda el resultado de la clave. Si algo lanza una excepción, se revierte todo en ambas bases | Reglas 1 y 5 y `AC-REF-04-14`. La decisión de acceso se lee dentro de la misma transacción: no hay ventana entre verificar y escribir | No |
| Orden de validación | Permiso, clave de operación, existencia y estado de la reserva, alcance del participante, validación del tipo y los campos. Es el orden de la spec, más el paso del alcance que la spec describe en la regla 6 | Para no revelar si una reserva existe a quien no puede verla | No |
| Auditoría | Tabla `auditoria` (cuenta, itinerario, operación, permiso exigido, resultado `permitido` / `denegado` / `rechazado`, reserva, clave, motivo, momento). Toda operación de escritura deja su asiento, también las denegadas y las rechazadas por validación. **Los rechazos por reserva inexistente, ajena al itinerario o en baja también dejan asiento**; la spec dice «rechazo sin efecto» y no aclara si eso excluye el asiento. En las consultas solo se audita la denegación, no cada vista permitida | La auditoría registra la decisión permitida o denegada (`ADR-IT4-007`). Decisión confirmada por el usuario. | No |
| Idempotencia | Tabla `clave_operacion (cuenta_id, clave)` con el resultado de la primera operación. Una clave repetida devuelve ese resultado sin aplicar nada, aunque el contenido sea distinto. Una operación rechazada no memoriza su clave. Retención de 7 días con purga periódica. Si dos pedidos con la misma clave chocan en la base, el segundo se reintenta una vez y encuentra el resultado | Regla 2 y `AC-REF-04-10`. La clave es por cuenta, para que dos cuentas puedan usar el mismo valor | No |
| Baja lógica | Columna `baja_en` en `reserva`. Las reservas dadas de baja no aparecen en la vista, ni en el archivo, ni cuentan para el cierre de un viaje. **Cambia una lectura de REF-01**: `reservas_de` y `viajes_completos` las excluyen | Regla 3. Un viaje con todas sus reservas en baja no se archiva (no tiene reservas vigentes) | No |
| Campos nuevos de `Reserva` | `origen` (`manual`, `correo`, `proveedor`), `creado_por` (cuenta o vacío), `editada_manualmente` y `baja_en`. Van en columnas propias, no en `datos`. Las altas de REF-03 fijan `origen = correo` y sin `creado_por` | Hacen falta para la matriz de permisos y para la precedencia. El contrato común de `Reserva` es el lugar que la spec asigna (`ADR-IT4-009`) | No |
| Qué se puede actualizar | `inicio`, `fin`, `lugar`, `estado` y los campos propios del tipo. No se cambian el tipo, el viaje ni el identificador. Se revalida reconstruyendo la clase concreta con los cambios | La spec habla de «cambios» sin enumerarlos | No |
| `ReservaActividad` | Nueva clase concreta, registrada con el nombre `actividad` en `TIPOS_BASE` | `ADR-IT4-008`: es una clase más del Registro de tipos | No |
| Novedades mínimas | Tabla `novedad` y `aplicar_novedad(novedad)`: si la reserva fue editada a mano o está en baja, la novedad **no** la modifica y queda pendiente; si no, se aplican sus cambios. `GET /itinerarios/{id}/novedades` las lista | `AC-REF-04-04` exige que la novedad quede visible en «Novedades». La ingesta de Booking (`QA-PER-01`) no tiene spec, así que esto es solo el lado del Orquestador, con la forma mínima que hace testeable la precedencia. La interfaz para resolver la novedad queda fuera, como dice la spec | No |
| Códigos HTTP | 403 acceso denegado (cuerpo `{"error": "acceso_denegado"}`); 404 reserva inexistente o de otro itinerario; 409 reserva en baja; 422 tipo no registrado o campos inválidos; 422 si falta la identidad o la clave. Una clave repetida devuelve el estado y el cuerpo de la primera operación | La spec fija solo el 403. Los demás son de este plan | No |
| Identidad y clave | `X-Viajero-Id` (la cuenta del actor, ya verificada por el gateway, como en REF-01) y `X-Clave-Operacion` | Coherencia con las demás APIs del Orquestador | No |
| Página «Error 401» | **No se implementa en esta tanda.** El cliente web todavía no existe. Se verifica la respuesta (403 con su cuerpo) y la página queda como demostración pendiente, tal como marca la spec («Test automático para la respuesta, demostración para la página») | El Plan Maestro ubica los clientes en otro trabajo | No |
| Determinismo de la operación | El identificador de la reserva (`res-<uuid>`) y la hora se calculan **antes** de la escritura y se pasan adentro | La operación corre dos veces (una por base): si se generaran adentro, la primaria y la pasiva tendrían identificadores distintos | No |
| Cuerpo del pedido | `POST` y `PATCH` reciben el JSON crudo, no un modelo estricto de FastAPI. Solo se rechaza antes del permiso un cuerpo que no es un objeto JSON | La spec pide verificar el permiso antes que los campos, y que un campo inválido deje su asiento. Un rechazo previo de FastAPI no hace ninguna de las dos cosas | No |
| Campos que fija el servidor | `datos` no puede traer los campos comunes ni el identificador (`creado_por`, `origen`, etc.): se rechaza por campos inválidos | Evita que el cliente se atribuya la autoría o cambie el origen | No |
| Novedades repetidas o sobre reservas que no se pueden aplicar | Un identificador de novedad ya visto se descarta (`duplicada`); una novedad que no se puede aplicar sola (campos no editables, fechas inválidas) queda `retenida` para que decida el viajero | Mismo criterio que la precedencia: no se pierde ni se pisa | No |
| Test de REF-01 actualizado | `test_arranque_registra_los_cinco_tipos_base` pasó a `test_arranque_registra_los_tipos_base` e incluye `actividad` | `ReservaActividad` se suma al Registro de tipos por esta spec | No |
| Purga de claves | La tarea periódica `tarea_purga_claves` corre en el ciclo de vida de la app con el mismo intervalo que la purga de revisión | Retención de 7 días de la spec | No |

## Estructura de Código y Mapeo Arquitectónico

| Ruta en el repositorio | Elemento del paso 5 que instancia | Dependencias permitidas (imports) | Prohibiciones explícitas |
| :--- | :--- | :--- | :--- |
| `src/trotamundos/dominio/reserva.py`, `tipos_reserva.py` | Contrato `Reserva` (`origen`, `creado_por`, `editada_manualmente`, `baja_en`) y `ReservaActividad` | `dominio` | No importa ningún otro paquete |
| `src/trotamundos/persistencia/esquemas/04_gestion.sql` | Base primaria: `itinerario_id`, columnas nuevas de `reserva`, `membresia`, `auditoria`, `clave_operacion`, `novedad` | — | La Base de viajes no guarda cuentas ni sesiones: `membresia` solo relaciona identificadores |
| `src/trotamundos/persistencia/repositorio_gestion.py` | Acceso a membresías, reservas, claves, auditoría y novedades, **dentro de una transacción ya abierta** | `psycopg`, `dominio` | No importa `orquestador` ni `entrada` |
| `src/trotamundos/orquestador/control_acceso.py` | Módulo de control de acceso y auditoría, con `verificarPermiso` (`ADR-IT4-007`) | `dominio`, `persistencia.repositorio_gestion` | **Nadie fuera de `orquestador` lo importa.** Un test lo hace cumplir |
| `src/trotamundos/orquestador/gestion_reservas.py` | Operaciones manuales de reserva: `agregarReserva`, `actualizarReserva`, `eliminarReserva` y la vista del itinerario (`ADR-IT4-008`) | `dominio`, `orquestador.control_acceso`, `persistencia` | No importa `entrada`. No conoce tipos concretos de reserva |
| `src/trotamundos/orquestador/novedades.py` | Orquestador: precedencia de la edición manual | `dominio`, `persistencia.repositorio_gestion` | No importa `entrada` |
| `src/trotamundos/orquestador/api_gestion.py` | Endpoints para Cliente web y móvil | `fastapi`, `orquestador.*` | La cotización no pasa por acá ni por el control de acceso |
| `src/trotamundos/persistencia/repositorio_viajes.py`, `orquestador/incorporacion.py` | Se ajustan: `itinerario_id = viajero_id`, `origen = correo`, y las lecturas excluyen las bajas | los actuales | Sus tests de REF-01 y REF-03 siguen en verde |

Ajuste a `tests/test_arquitectura.py` (aditivo): `persistencia` no importa `orquestador`; ningún paquete fuera de `orquestador` importa `orquestador.control_acceso`.

## Tareas de Implementación

| ID | Descripción de la tarea | Archivos a crear / modificar | AC que cubre | Depende de | Criterio de terminado (Done) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `T-REF-04-01` | Modelo: campos nuevos de `Reserva`, `ReservaActividad`, esquema `04_gestion.sql`, ajuste de las altas de REF-01/REF-03 y exclusión de bajas en las lecturas | `dominio/reserva.py`, `dominio/tipos_reserva.py`, `persistencia/esquemas/04_gestion.sql`, `persistencia/repositorio_viajes.py`, `orquestador/incorporacion.py`, `tests/conftest.py`, `tests/test_ref04_modelo.py` | `AC-REF-04-03` (base de la baja), `AC-REF-04-06` (la actividad es un tipo) | — | La suite de REF-01 y REF-03 sigue en verde; una reserva en baja no aparece en la vista |
| `T-REF-04-02` | Control de acceso: matriz de roles y permisos, `verificarPermiso` con denegación por defecto, alcance «solo propias» | `persistencia/repositorio_gestion.py`, `orquestador/control_acceso.py`, `tests/test_ref04_control_acceso.py` | `AC-REF-04-05` (decisión), `AC-REF-04-07`, `AC-REF-04-08`, `AC-REF-04-09` (decisiones) | `T-REF-04-01` | Cada celda de la matriz de la spec tiene su test; una cuenta sin membresía no tiene ningún permiso |
| `T-REF-04-03` | `agregarReserva`: una sola transacción con permiso, clave, validación, reserva, auditoría y resultado de la clave | `orquestador/gestion_reservas.py`, `persistencia/repositorio_gestion.py`, `tests/test_ref04_agregar.py` | `AC-REF-04-01`, `AC-REF-04-02`, `AC-REF-04-10`, `AC-REF-04-13`, `AC-REF-04-14` | `T-REF-04-02` | Alta con `creadoPor`; reintento sin duplicar; clave con otro contenido devuelve la primera; un fallo a mitad no deja nada |
| `T-REF-04-04` | `actualizarReserva` y `eliminarReserva`: existencia, baja, alcance del participante, baja lógica | `orquestador/gestion_reservas.py`, `tests/test_ref04_actualizar_eliminar.py` | `AC-REF-04-03`, `AC-REF-04-07`, `AC-REF-04-08`, `AC-REF-04-09`, `AC-REF-04-11`, `AC-REF-04-12` | `T-REF-04-03` | Baja conserva la fila; sin permiso no se revela si la reserva existe |
| `T-REF-04-05` | Vista del itinerario para cualquier miembro con permiso de ver, agrupada por viaje | `orquestador/gestion_reservas.py`, `tests/test_ref04_vista.py` | `AC-REF-04-06`, `AC-REF-04-05` (vista denegada) | `T-REF-04-04` | Otro miembro ve la actividad en su próxima consulta; sin permiso, acceso denegado |
| `T-REF-04-06` | Novedades: `aplicar_novedad` con precedencia de la edición manual y listado de novedades pendientes | `orquestador/novedades.py`, `persistencia/repositorio_gestion.py`, `tests/test_ref04_novedades.py` | `AC-REF-04-04` | `T-REF-04-04` | La reserva editada a mano no cambia y la novedad queda visible |
| `T-REF-04-07` | Endpoints REST con sus códigos (403, 404, 409, 422) y la purga de las claves vencidas | `orquestador/api_gestion.py`, `orquestador/revision.py` o `gestion_reservas.py` (purga), `app.py`, `tests/test_ref04_api.py` | `AC-REF-04-05` (respuesta 403), `AC-REF-04-01`, `AC-REF-04-02`, `AC-REF-04-06` | `T-REF-04-05`, `T-REF-04-06` | La respuesta de acceso denegado lleva 403; la purga elimina claves de más de 7 días |

## Matriz de Cobertura de Criterios de Aceptación

Ningún `AC` de la spec puede quedar sin tarea ni sin test asociado. `AC-REF-04-05` queda verde en lo automático (la respuesta 403 y su cuerpo); la página «Error 401» es una demostración pendiente hasta que exista el cliente web.

| Criterio de Aceptación (Spec) | Tarea(s) del Plan | Nombre del test automatizado | Estado |
| :--- | :--- | :--- | :--- |
| `AC-REF-04-01` | `T-REF-04-03`, `T-REF-04-07` | `test_AC_REF_04_01_agregar_persiste_con_creado_por_y_asiento_de_auditoria`, `test_AC_REF_04_01_agregar_por_http_responde_201_con_la_reserva` | `[x] Verde` |
| `AC-REF-04-02` | `T-REF-04-03`, `T-REF-04-07` | `test_AC_REF_04_02_reintento_con_la_misma_clave_no_duplica`, `test_AC_REF_04_02_reintento_por_http_devuelve_lo_mismo_sin_duplicar` | `[x] Verde` |
| `AC-REF-04-03` | `T-REF-04-01`, `T-REF-04-04` | `test_AC_REF_04_03_eliminar_deja_baja_logica_y_conserva_el_historial`, `test_AC_REF_04_03_una_reserva_en_baja_no_aparece_en_la_vista_pero_se_conserva` | `[x] Verde` |
| `AC-REF-04-04` | `T-REF-04-06` | `test_AC_REF_04_04_novedad_no_pisa_la_edicion_manual_y_queda_visible` | `[x] Verde` |
| `AC-REF-04-05` | `T-REF-04-02`, `T-REF-04-03`, `T-REF-04-05`, `T-REF-04-07` | `test_AC_REF_04_05_sin_membresia_no_hay_ningun_permiso`, `test_AC_REF_04_05_sin_membresia_no_persiste_y_deja_el_asiento_de_la_denegacion`, `test_AC_REF_04_05_sin_permiso_de_ver_el_acceso_se_deniega_con_asiento`, `test_AC_REF_04_05_sin_membresia_responde_403_y_no_persiste` | `[x] Verde` (la página «Error 401» queda como demostración) |
| `AC-REF-04-06` | `T-REF-04-05`, `T-REF-04-07` | `test_AC_REF_04_06_otro_miembro_ve_la_actividad_registrada`, `test_AC_REF_04_06_otro_miembro_ve_la_actividad_por_http` | `[x] Verde` |
| `AC-REF-04-07` | `T-REF-04-02`, `T-REF-04-04` | `test_AC_REF_04_07_participante_alcanza_solo_lo_que_creo`, `test_AC_REF_04_07_participante_modifica_y_elimina_lo_que_creo` | `[x] Verde` |
| `AC-REF-04-08` | `T-REF-04-02`, `T-REF-04-04` | `test_AC_REF_04_08_participante_no_alcanza_lo_ajeno_ni_lo_de_proveedor_o_correo`, `test_AC_REF_04_08_participante_no_toca_lo_ajeno_ni_lo_de_proveedor_o_correo` | `[x] Verde` |
| `AC-REF-04-09` | `T-REF-04-02`, `T-REF-04-04` | `test_AC_REF_04_09_organizador_alcanza_cualquier_reserva`, `test_AC_REF_04_09_organizador_modifica_cualquier_reserva` | `[x] Verde` |
| `AC-REF-04-10` | `T-REF-04-03` | `test_AC_REF_04_10_misma_clave_con_otro_contenido_devuelve_la_primera_operacion` | `[x] Verde` |
| `AC-REF-04-11` | `T-REF-04-04` | `test_AC_REF_04_11_reserva_en_baja_no_se_actualiza_ni_se_elimina` | `[x] Verde` |
| `AC-REF-04-12` | `T-REF-04-04` | `test_AC_REF_04_12_inexistente_o_de_otro_itinerario_se_rechaza_sin_revelar_existencia` | `[x] Verde` |
| `AC-REF-04-13` | `T-REF-04-03` | `test_AC_REF_04_13_tipo_no_registrado_se_rechaza_con_asiento`, `test_AC_REF_04_13_campos_invalidos_se_rechazan_con_asiento` | `[x] Verde` |
| `AC-REF-04-14` | `T-REF-04-03`, `T-REF-04-04` | `test_AC_REF_04_14_falla_a_mitad_de_la_escritura_no_deja_reserva_ni_asiento`, `test_AC_REF_04_14_falla_al_actualizar_no_deja_cambio_ni_asiento` | `[x] Verde` |

## Estrategia de Pruebas y Simulación de Fallos

* **Tests unitarios / contractuales:** la matriz de permisos se prueba celda por celda sobre `verificarPermiso` con membresías en memoria. El resto usa las dos bases reales (marca `db`), con la fixture `bases_limpias` ampliada para recrear las tablas nuevas y una fixture que precarga un itinerario con un organizador, un participante y una cuenta sin membresía.
* **Inyección de fallos:**
  * Falla a mitad de la escritura (`AC-REF-04-14`): el servicio acepta un gancho de prueba que se ejecuta dentro de la transacción, entre la escritura de la reserva y la del asiento. El test lo hace lanzar una excepción y comprueba que no quedó ni la reserva ni el asiento en ninguna de las dos bases.
  * Reintento y choque de claves (`AC-REF-04-02`, `AC-REF-04-10`): se repite la operación con la misma clave, con el mismo contenido y con otro, y se cuentan filas en reserva y auditoría.
  * Base primaria caída: ya está cubierto por REF-01; estas operaciones usan el mismo `BaseViajes`.
* **Auditoría:** cada test de escritura verifica el asiento correspondiente (permitido, denegado o rechazado) en las dos bases.
* **Comando de ejecución:** `.venv/bin/pytest tests/test_ref04_*.py` (con `docker compose up -d --wait`).

## Riesgos Técnicos del Plan

* **El itinerario no existía en REF-01.** Se agrega `itinerario_id` con el valor del viajero. Mitigación: las altas de REF-01 y REF-03 lo fijan y el SQL completa los viajes ya existentes; la suite anterior debe seguir en verde.
* **Cambio de comportamiento de REF-01.** Las reservas en baja dejan de contar para la vista y para el cierre del viaje. Mitigación: ningún `AC` de REF-01 depende de las bajas, y se deja escrito en la spec al fijar las decisiones.
* **Membresías precargadas.** Un viajero real de REF-01 o REF-03 no puede usar las operaciones manuales hasta que tenga su membresía. Mitigación: es la simplificación de la spec; se documenta y se ofrece una función de precarga.
* **Novedades sin ingesta de Booking.** Solo existe el lado del Orquestador. Mitigación: la forma de la novedad es mínima y se deja explícita como parte a revisar cuando se especifique `QA-PER-01`.
* **Transacción más larga.** La operación lee y escribe varias tablas dentro del commit en dos fases. Mitigación: son pocas filas por operación; no hay cota de tiempo en la spec.
* **Página «Error 401».** Sin cliente web no hay página que demostrar. Mitigación: se entrega el contrato (403 con su cuerpo) y la demostración queda para cuando exista el cliente.
