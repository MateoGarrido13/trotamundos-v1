# PLAN-REF-01. Ciclo de vida del viaje

* **Spec asociada:** [SPEC-REF-01](../specs/SPEC-REF-01.md) *(estado `aprobada`)*
* **Estado:** aprobado
* **Fecha:** 2026-11-23
* **Incremento (Slice):** Slice 4 de [PLAN_MAESTRO.md](PLAN_MAESTRO.md) (con la parte de `QA-DIS-01` que el Slice 2 deja a esta spec)

Parte del esqueleto compartido ya construido: `Reserva`, `RegistroTipos`, `Broker`, `Configuracion`, `persistencia.conectar` y `docker-compose.yml` con `viajes_primaria` (5433) y `viajes_pasiva` (5434).

## Decisiones Técnicas Locales

| Decisión | Alternativa elegida | Motivo | ¿Afecta algún driver o requiere ADR? |
| :--- | :--- | :--- | :--- |
| Modelo de datos | Tablas `viaje` y `reserva`. Los campos comunes del contrato `Reserva` son columnas; los propios de cada tipo van en una columna `datos` JSONB, que `RegistroTipos` hidrata a la clase concreta | La agrupación no conoce los tipos (ADR-IT3-005): un medio nuevo no exige migrar el esquema | No |
| Pertenencia del viaje | `viaje.viajero_id` (texto). La identidad llega «ya encaminada» por el header `X-Viajero-Id`, que simula al gateway | La autenticación es del Slice 1, sin spec en esta tanda | No |
| Commit en dos fases | `PREPARE TRANSACTION` / `COMMIT PREPARED` de PostgreSQL sobre las dos bases. Orden: ejecutar en ambas, preparar la **pasiva primero** (su acuerdo), preparar la primaria y recién entonces confirmar | La primaria no confirma éxito hasta que la pasiva acuerda (ADR-IT2-004). `max_prepared_transactions=20` ya está en el compose | No |
| Detección de caída | Error de conexión (`psycopg.OperationalError`) al escribir o leer, contado de forma consecutiva | Es el mecanismo que fija la spec | No |
| Umbral de fallos consecutivos | `3`, configurable (`TROTA_UMBRAL_CONMUTACION`). Valor confirmado con `OK PLAN` y fijado en la spec | Evitar conmutar por un fallo transitorio. Los tests lo fijan en `1` o `2` para ser rápidos | No (la spec lo declara parámetro) |
| Tras conmutar | La primaria vieja queda marcada `no_escribible` hasta resincronización manual; la pasiva atiende sola, sin acuerdo de segunda copia | Evita *split-brain* (simplificación de la spec) | No |
| Archivado periódico | Tarea `asyncio` que llama a `archivar_completados(ahora)`; la misma función se invoca a demanda en los tests, con un reloj inyectado | La spec pide «invocable a demanda en las pruebas» | No |
| Viaje completo | Todas sus reservas tienen `fin <= ahora` (su última reserva ya terminó). Un viaje sin reservas no se archiva | Regla 2 de la spec | No |
| Esquemas SQL | Carpeta `persistencia/esquemas/` con un `.sql` por spec (`01_viajes.sql`) y un cargador que los aplica en orden | Evita que REF-01 y REF-02 editen el mismo archivo y choquen al integrar | No |
| Alta de viajes y reservas | El repositorio expone insertar viaje y reserva, **solo como base de escritura**. Las operaciones públicas `agregarReserva` / `actualizarReserva` / `eliminarReserva` son de SPEC-REF-04 | Los tests de REF-01 necesitan datos. El contrato manual con permisos y auditoría es de REF-04 | No |
| Fallo por debajo del umbral | La llamada falla con `ErrorBaseNoDisponible` y no cae a la pasiva; cualquier éxito en la primaria reinicia el contador | Evita conmutar por un fallo transitorio | No |
| Fallo de la pasiva en una escritura | Revierte ambas bases y lanza `ErrorBaseNoDisponible`; no cuenta como caída de la primaria | La caída de la primaria es lo único que dispara la conmutación | No |
| Orden de confirmación | `COMMIT PREPARED` primero en la primaria y después en la pasiva (la pasiva prepara antes) | Cumple el acuerdo de la pasiva previo a la confirmación | No |
| Conexiones | Autocommit con `BEGIN` explícito; `BaseViajes` no reintenta la operación fallida | El siguiente llamado ya va a la pasiva tras conmutar | No |
| Intervalo del archivado | 3600 s, configurable (`TROTA_INTERVALO_ARCHIVADO`); la tarea periódica corre en el lifespan de FastAPI y captura errores | Una base caída no mata la tarea | No |
| Viaje completo | Al menos una reserva y todas con `fin <= ahora`, incluidas las canceladas | Regla 2 de la spec | No |
| Identidad ausente | Sin `X-Viajero-Id` el servicio responde 422 | Validación estándar de FastAPI | No |
| Tipos concretos | Sin campos propios; `datos` (JSONB) vacío por ahora | La spec solo fija los campos comunes | No |

## Estructura de Código y Mapeo Arquitectónico

| Ruta en el repositorio | Elemento del paso 5 que instancia | Dependencias permitidas (imports) | Prohibiciones explícitas |
| :--- | :--- | :--- | :--- |
| `src/trotamundos/dominio/tipos_reserva.py` | Clases concretas que extienden `Reserva`: `ReservaHotel`, `ReservaAuto`, `ReservaVuelo`, `ReservaTren`, `ReservaAutobus` (ADR-IT3-005, ITERACION_3) | `dominio.reserva` | No importa orquestador, broker, entrada ni persistencia |
| `src/trotamundos/dominio/registro_tipos.py` | Registro de tipos (ya existe) | `dominio.reserva` | Ídem |
| `src/trotamundos/persistencia/esquemas/01_viajes.sql` y `esquemas.py` | Base primaria / Base pasiva: tablas `viaje` y `reserva` (ITERACION_1) | psycopg | Sin cuentas, perfiles ni sesiones en la Base de viajes |
| `src/trotamundos/persistencia/coordinador_2pc.py` | Commit en dos fases del Orquestador (ADR-IT2-004, ITERACION_2) | `persistencia.conexion` | No importa orquestador |
| `src/trotamundos/persistencia/base_viajes.py` | Base primaria + Base pasiva y Reconfiguration (ADR-IT2-005): contador de fallos, conmutación, primaria bloqueada | `persistencia.coordinador_2pc`, `config` | No importa orquestador |
| `src/trotamundos/persistencia/repositorio_viajes.py` | Acceso a viajes y reservas, hidratando por `RegistroTipos` | `persistencia.base_viajes`, `dominio` | No conoce tipos concretos de reserva |
| `src/trotamundos/orquestador/agrupacion.py` | Orquestador de viajes: agrupación y vista principal (ITERACION_1) | `dominio`, `persistencia.repositorio_viajes` | **No importa ningún tipo concreto de `Reserva`**. No importa `entrada` |
| `src/trotamundos/orquestador/archivado.py` | Orquestador de viajes: archivado automático por fecha | `orquestador.agrupacion`, `persistencia` | Ídem |
| `src/trotamundos/orquestador/arranque.py` | Registro de tipos al arrancar (configuration-time binding) | `dominio.registro_tipos`, `dominio.tipos_reserva` | Ídem |
| `src/trotamundos/orquestador/api.py` | Vista principal y archivo para Cliente web y móvil (`CON-01`) | `fastapi`, `orquestador.*` | No lee ni escribe ninguna Base de cuentas |

## Tareas de Implementación

| ID | Descripción de la tarea | Archivos a crear / modificar | AC que cubre | Depende de | Criterio de terminado (Done) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `T-REF-01-01` | Los cinco tipos concretos de reserva y el arranque que los registra. `create_app` acepta tipos extra y falla al arrancar si el registro los rechaza | `dominio/tipos_reserva.py`, `orquestador/arranque.py`, `app.py`, `tests/test_ref01_registro.py` | `AC-REF-01-08`, `AC-REF-01-03` (parte de registro) | — | Tests en verde; el mensaje de error nombra la causa |
| `T-REF-01-02` | Esquema `viaje` / `reserva`, cargador de esquemas y repositorio (insertar, listar por viajero y estado) con hidratación por `RegistroTipos`. Fixture `bases_limpias` que recrea las tablas | `persistencia/esquemas/01_viajes.sql`, `persistencia/esquemas.py`, `persistencia/repositorio_viajes.py`, `tests/conftest.py` | `AC-REF-01-01` (base de datos) | — | Ida y vuelta de una reserva con la clase concreta correcta (test `db`) |
| `T-REF-01-03` | Coordinador de commit en dos fases y `BaseViajes.escribir(operacion)`: ejecuta en ambas, prepara la pasiva, luego la primaria, confirma. Si cualquier fase falla, revierte ambas | `persistencia/coordinador_2pc.py`, `persistencia/base_viajes.py`, `tests/test_ref01_2pc.py` | `AC-REF-01-04` | `T-REF-01-02` | La pasiva registra el acuerdo antes que la primaria confirme; un fallo de la pasiva deja la primaria sin cambios |
| `T-REF-01-04` | Reconfiguration: contador de errores de conexión consecutivos, umbral configurable, conmutación a la pasiva para leer y escribir, primaria marcada `no_escribible` | `persistencia/base_viajes.py`, `config.py`, `tests/test_ref01_conmutacion.py` | `AC-REF-01-05` | `T-REF-01-03` | Tras el umbral, lectura y escritura las atiende la pasiva; con ambas caídas, error de servicio no disponible |
| `T-REF-01-05` | Agrupación polimórfica: vista principal (viajes activos con sus reservas agrupadas) y viajes archivados | `orquestador/agrupacion.py`, `tests/test_ref01_agrupacion.py` | `AC-REF-01-01`, `AC-REF-01-07`, `AC-REF-01-06`, `AC-REF-01-03` (agrupación sin cambios) | `T-REF-01-01`, `T-REF-01-02` | Listas vacías (no error) sin viajes; un tipo nuevo se agrupa sin tocar `agrupacion.py` |
| `T-REF-01-06` | Archivado automático: `archivar_completados(ahora)` y la tarea periódica que la llama | `orquestador/archivado.py`, `tests/test_ref01_archivado.py` | `AC-REF-01-02` | `T-REF-01-03`, `T-REF-01-05` | El viaje queda `archivado`, no se elimina, y sale de la vista principal; la escritura pasó por 2PC |
| `T-REF-01-07` | Endpoints `GET /viajes` y `GET /viajes/archivados` con `X-Viajero-Id`; error 503 si no hay base disponible. Se monta en `create_app` | `orquestador/api.py`, `app.py`, `tests/test_ref01_api.py` | `AC-REF-01-01`, `AC-REF-01-06`, `AC-REF-01-07` (vía HTTP, `CON-01`) | `T-REF-01-04`, `T-REF-01-05`, `T-REF-01-06` | Respuestas JSON con reservas agrupadas; 503 sin ninguna base |

## Matriz de Cobertura de Criterios de Aceptación

| Criterio de Aceptación (Spec) | Tarea(s) del Plan | Nombre del test automatizado | Estado |
| :--- | :--- | :--- | :--- |
| `AC-REF-01-01` | `T-REF-01-02`, `T-REF-01-05`, `T-REF-01-07` | `test_AC_REF_01_01_vista_principal_agrupa_reservas_por_viaje` | `[x] Verde` |
| `AC-REF-01-02` | `T-REF-01-06` | `test_AC_REF_01_02_archivado_saca_viaje_completo_de_vista_principal` | `[x] Verde` |
| `AC-REF-01-03` | `T-REF-01-01`, `T-REF-01-05` | `test_AC_REF_01_03_tipo_nuevo_queda_agrupado_sin_cambiar_agrupacion` | `[x] Verde` |
| `AC-REF-01-04` | `T-REF-01-03` | `test_AC_REF_01_04_pasiva_acuerda_antes_de_que_la_primaria_confirme` | `[x] Verde` |
| `AC-REF-01-05` | `T-REF-01-04` | `test_AC_REF_01_05_primaria_caida_atiende_la_pasiva` | `[x] Verde` |
| `AC-REF-01-06` | `T-REF-01-05`, `T-REF-01-07` | `test_AC_REF_01_06_archivados_devuelve_viajes_o_lista_vacia` | `[x] Verde` |
| `AC-REF-01-07` | `T-REF-01-05`, `T-REF-01-07` | `test_AC_REF_01_07_sin_viajes_activos_devuelve_lista_vacia` | `[x] Verde` |
| `AC-REF-01-08` | `T-REF-01-01` | `test_AC_REF_01_08_arranque_rechaza_tipo_duplicado_o_clase_invalida` | `[x] Verde` |

## Estrategia de Pruebas y Simulación de Fallos

* **Tests unitarios / contractuales:** agrupación, registro y archivado con un repositorio en memoria cuando no hace falta SQL. Los tests marcados `db` usan las dos instancias reales de PostgreSQL y recrean las tablas antes de cada caso.
* **Inyección de fallos:** `BaseViajes` recibe una fábrica de conexiones. Los tests la envuelven con un doble que lanza `OperationalError` en la primaria a demanda (caída de la primaria, `AC-REF-01-05`) o en la pasiva (fallo de acuerdo, `AC-REF-01-04`). Un test adicional `db` detiene de verdad el contenedor `viajes_primaria` con `docker compose stop`.
* **Orden del acuerdo (`AC-REF-01-04`):** un doble registra la secuencia de `PREPARE` y `COMMIT PREPARED`; el test verifica que la pasiva preparó antes de que la primaria confirmara.
* **Reloj:** el archivado recibe `ahora` por parámetro; ningún test espera tiempo real.
* **Comando de ejecución:** `.venv/bin/pytest tests/test_ref01_*.py` (con `docker compose up -d --wait` para los `db`).

## Riesgos Técnicos del Plan

* **`PREPARE TRANSACTION` deja transacciones colgadas si el proceso muere entre fases.** Mitigación: el coordinador revierte con `ROLLBACK PREPARED` ante cualquier excepción, y la fixture de tests limpia `pg_prepared_xacts`.
* **Solapamiento con REF-02 en `persistencia/`.** REF-02 guarda tokens cifrados en la Base primaria de viajes. Mitigación: cada spec agrega su propio `.sql` en `esquemas/` y REF-02 consume `BaseViajes` recién tras integrar `T-REF-01-03`.
* **Conflicto en `app.py` y `pyproject.toml` al integrar.** Mitigación: REF-02 monta sus rutas en una app de entrada separada; los cambios de REF-01 a `app.py` son acotados (registro de tipos y un router).
* **Umbral de conmutación.** Quedó fijado en `3`, configurable, en la spec y en este plan.
* **Datos específicos de cada tipo de reserva.** La spec solo fija los campos comunes. Mitigación: las cinco clases concretas llevan los campos mínimos y no se agregan campos que la spec no pide.
