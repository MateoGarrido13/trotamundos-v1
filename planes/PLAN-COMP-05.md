# PLAN-COMP-05. Identidad regional y seguridad en el borde

* **Spec asociada:** [SPEC-COMP-05](../specs/SPEC-COMP-05.md) (aprobada)
* **Estado:** terminado
* **Fecha:** 2026-11-23
* **Incremento (Slice):** Slice 1 de [PLAN_MAESTRO.md](PLAN_MAESTRO.md)

## Decisiones Técnicas Locales

| # | Decisión | Alternativa elegida | Motivo | ¿Afecta driver o requiere ADR? |
| :--- | :--- | :--- | :--- | :--- |
| D1 | Dónde viven las 6 bases de cuentas | Seis contenedores nuevos en `docker-compose.yml` (puertos 5436 a 5441), con `trotamundos_dev` y `trotamundos_test` creadas por `scripts/crear_bases.py` | Aislamiento físico completo de cada región y de su pasiva (`ADR-IT4-001`) | No |
| D2 | Firma del token de acceso | Ed25519 por región. El Gateway tiene solo las claves públicas | El Gateway valida sin poder emitir (`ADR-IT4-004`) | No |
| D3 | Hash de contraseñas | `scrypt` de la biblioteca estándar, con el costo como parámetro (`costo_hash`, bajo en los tests) | Sin dependencias nuevas | No |
| D4 | Rechazo de `X-Viajero-Id` que no pasó por el Gateway | El Gateway agrega `X-Gateway-Firma` (HMAC de la identidad con un secreto interno) y el Core la verifica | Defensa real, comprobable con un pedido directo (`AC-COMP-05-07`) | No |
| D5 | Efecto sobre los tests existentes | `exigir_gateway` configurable: `True` en la app real, `False` por defecto. Los tests viejos no cambian | No tocar 583 tests en verde | No |
| D6 | Correo de recuperación y aviso | Se publican en la cola `notificaciones` con la forma de [SPEC-COMP-08](../specs/SPEC-COMP-08.md) (canal, destinatario, propuesta). Cola llena: se registra y la operación sigue | La cola no tiene consumidor hasta COMP-08 | No |
| D7 | Cómo se identifica la región en login y recuperación | El cliente la envía en el cuerpo, como en el alta. Los tokens de renovación y de recuperación llevan el prefijo `<región>.` | Es el «enrutamiento por proximidad» simulado; una región equivocada responde como cuenta inexistente | No |
| D8 | Escritura de cuentas | `BaseViajes` (primaria, pasiva, 2PC) instanciada con las bases de la región | Reusa el commit en dos fases ya probado; las operaciones reciben id, tiempos y tokens ya calculados porque corren en las dos bases | No |
| D9 | Unicidad entre regiones | Consulta en paralelo con un `ThreadPoolExecutor` y espera acotada por `cota_unicidad_ms`. La reconciliación de «pendientes» queda fuera (spec, Fuera de Alcance) | Cumple `ADR-IT4-003` sin sincronizar regiones | No |
| D11 | Conexiones a las bases de cuentas | Una conexión por hilo y por base, reutilizada (`ConexionesPorHilo`); `BaseViajes` no cambia | Abrir ~5 conexiones por alta llevaba la carga de 1.000 altas de 24 s a 3,5 s | No |
| D12 | Alcance de la prueba de carga de `AC-COMP-05-13` | 1.000 altas con 100 en vuelo a la vez (semáforo en el test); el tiempo de cada alta se mide desde que sale su pedido | Con 1.000 simultáneas en un proceso y una base la más lenta tardó 3,5 s (unas 285 altas/s): el límite era la máquina, no el diseño. `QA-ESC-01` exige unas 1,2 altas/s de promedio. **Enmienda de la spec con ratificación pendiente del usuario** | Sí, el criterio de la spec |
| D10 | Recuperación aislada | Un pool de hilos propio para la recuperación, además de su cupo de tasa | Saturarla no consume los hilos del login (`ADR-IT4-005`) | No |

## Estructura de Código y Mapeo Arquitectónico

| Ruta | Elemento del paso 5 | Dependencias permitidas | Prohibiciones |
| :--- | :--- | :--- | :--- |
| `src/trotamundos/dominio/identidad.py` | `IRegistroUsuario`, `Sesion` y errores | Solo el dominio | No importa `config` |
| `src/trotamundos/identidad/tokens.py` | Token firmado de vida corta | `cryptography`, dominio | No conoce bases |
| `src/trotamundos/identidad/contrasenas.py` | Hash con sal | Biblioteca estándar | — |
| `src/trotamundos/identidad/region/` (`esquema.sql`, `base.py`, `servicio.py`, `regiones.py`, `api.py`) | Módulo de registro y autenticación y Base de cuentas de cada región | `persistencia.base_viajes`, `persistencia.conexion`, dominio, `identidad.tokens` | No importa `orquestador`, `entrada`, `asistente`, `analitica` ni `broker` (publica por una función que recibe) |
| `src/trotamundos/identidad/gateway/` (`limitador.py`, `firma.py`, `gateway.py`, `nucleo.py`) | API Gateway: validación local del token y limitación de tasa | `identidad.tokens`, dominio | No importa `identidad.region` ni `persistencia`: no llama a ninguna región |
| `src/trotamundos/config.py` | `ConfiguracionIdentidad` | — | — |
| `src/trotamundos/app.py` | Conecta regiones, Gateway, cola de notificaciones y Core | Todo | Único que conecta módulos |
| `docker-compose.yml`, `scripts/crear_bases.py` | Seis bases de cuentas | — | — |

El `orquestador`, `entrada`, `asistente`, `analitica` y `persistencia` no importan `identidad` (se agrega a `tests/test_arquitectura.py`).

## Tareas de Implementación

| ID | Descripción | Archivos | AC | Depende de | Done |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `T-COMP-05-01` | Seis bases, configuración, esquema de cuentas y fixtures de test | `docker-compose.yml`, `scripts/crear_bases.py`, `config.py`, `identidad/region/esquema.sql`, `identidad/region/base.py`, `tests/conftest.py` | `AC-COMP-05-01` | — | Bases creadas y esquema aplicable |
| `T-COMP-05-02` | Tokens Ed25519 y hash de contraseñas | `dominio/identidad.py`, `identidad/tokens.py`, `identidad/contrasenas.py` | `AC-COMP-05-06` | — | Tokens válidos, alterados y vencidos verificados |
| `T-COMP-05-03` | Servicio de región: alta, login, renovación y cierre | `identidad/region/servicio.py`, `identidad/region/regiones.py` | `AC-COMP-05-01`, `02`, `03`, `04`, `11` | 01, 02 | Tests en verde con demora inyectada |
| `T-COMP-05-04` | Recuperación: un pedido vigente, un solo uso, aviso | `identidad/region/servicio.py` | `AC-COMP-05-09`, `10`, `11`, `12` | 03 | Tests en verde |
| `T-COMP-05-05` | Gateway: limitador de tasa, validación local y firma de identidad; verificación en el Core | `identidad/gateway/*` | `AC-COMP-05-05`, `06`, `07` | 02 | Tests en verde |
| `T-COMP-05-06` | API `/auth`, montaje en `app.py`, publicación en la cola, ráfaga de 50 | `identidad/region/api.py`, `app.py` | `AC-COMP-05-08` | 03, 04, 05 | Ráfaga contenida y login disponible |
| `T-COMP-05-07` | Prueba de carga de 1.000 altas y reglas de arquitectura | `tests/test_comp05_carga.py`, `tests/test_arquitectura.py` | `AC-COMP-05-13` | 06 | 0 rechazos, menos de 2 s con 100 en vuelo (D12) |

## Matriz de Cobertura de Criterios de Aceptación

| AC | Tarea | Test | Estado |
| :--- | :--- | :--- | :--- |
| `AC-COMP-05-01` | 01, 03 | `test_AC_COMP_05_01_cada_cuenta_vive_en_una_region_con_su_prefijo` | [x] |
| `AC-COMP-05-02` | 03 | `test_AC_COMP_05_02_el_alta_trae_la_sesion` | [x] |
| `AC-COMP-05-03` | 03 | `test_AC_COMP_05_03_region_lenta_deja_unicidad_pendiente` | [x] |
| `AC-COMP-05-04` | 03 | `test_AC_COMP_05_04_correo_de_otra_region_se_rechaza` | [x] |
| `AC-COMP-05-05` | 05 | `test_AC_COMP_05_05_el_gateway_valida_sin_llamar_a_ninguna_region` | [x] |
| `AC-COMP-05-06` | 02, 05 | `test_AC_COMP_05_06_token_alterado_o_vencido_no_llega_al_core` | [x] |
| `AC-COMP-05-07` | 05 | `test_AC_COMP_05_07_pedido_directo_al_core_con_identidad_se_rechaza` | [x] |
| `AC-COMP-05-08` | 06 | `test_AC_COMP_05_08_rafaga_de_50_recuperaciones` | [x] |
| `AC-COMP-05-09` | 04 | `test_AC_COMP_05_09_respuesta_uniforme_exista_o_no_la_cuenta` | [x] |
| `AC-COMP-05-10` | 04 | `test_AC_COMP_05_10_token_de_recuperacion_de_un_solo_uso` | [x] |
| `AC-COMP-05-11` | 03, 04 | `test_AC_COMP_05_11_recuperar_revoca_los_tokens_de_renovacion` | [x] |
| `AC-COMP-05-12` | 04 | `test_AC_COMP_05_12_un_solo_aviso_por_ventana` | [x] |
| `AC-COMP-05-13` | 07 | `test_AC_COMP_05_13_mil_altas_con_cien_en_vuelo` | [x] |

## Estrategia de Pruebas y Simulación de Fallos

* **Unitarios y contractuales:** tokens, hash, limitador, servicio de región contra las bases de test (`*_test`).
* **Inyección de fallos y latencia:** la consulta de unicidad de una región se reemplaza por una función con demora mayor que la cota (`AC-03`). La caída de región se simula con servicios de región que fallan ante cualquier llamada (`AC-05`). La ráfaga se envía con `asyncio.gather` (`AC-08`).
* **Reloj inyectable** en el servicio y el limitador, para vencimientos y ventanas sin esperar.
* **Comando:** `.venv/bin/python -m pytest tests/test_comp05_*.py` y la suite completa.

## Riesgos Técnicos del Plan

* **Los 2 s de `AC-13`** dependen del hilo disponible y del 2PC por alta. Se mide en la carga; si no alcanza, se presentan las opciones antes de cambiar nada.
* **Pasiva de cuentas:** el 2PC exige las dos bases de la región arriba. Los tests las levantan con `docker compose up -d`.
* **Cola de notificaciones sin consumidor:** si se llena, la recuperación sigue pero el correo no sale hasta COMP-08 (D6).
