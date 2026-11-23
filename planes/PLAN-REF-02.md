# PLAN-REF-02. Procesamiento de correo

* **Spec asociada:** [SPEC-REF-02](../specs/SPEC-REF-02.md) *(estado `aprobada`)*
* **Estado:** aprobado
* **Fecha:** 2026-11-23
* **Incremento (Slice):** Slice 3 de [PLAN_MAESTRO.md](PLAN_MAESTRO.md)

Parte del esqueleto compartido ya construido: `Broker` (cola `correo`, acotada, con Retry y cola de mensajes muertos), `ReservaNormalizada`, `FiltroRemitentes` (frontera con SPEC-REF-03) y `Configuracion`. Esta spec llega hasta entregar la reserva normalizada al Filtro de remitentes.

## Decisiones Técnicas Locales

| Decisión | Alternativa elegida | Motivo | ¿Afecta algún driver o requiere ADR? |
| :--- | :--- | :--- | :--- |
| Nodos de entrada | App FastAPI separada, `trotamundos.entrada.app`, con los endpoints de autorizar y revocar. No se monta en la app del Orquestador | ADR-IT3-010: los nodos de entrada corren separados de los del Orquestador. Además evita conflictos con REF-01 en `app.py` | No |
| Cifrado de tokens | `cryptography` (Fernet). La clave sale de `TROTA_CLAVE_TOKENS` | Es la simplificación que fija la spec. Se agrega la dependencia a `pyproject.toml` | No |
| Vigencia del token | 60 min, configurable. Un token vencido cuenta como no vigente; no se renueva | Parámetro y regla 6 de la spec | No |
| Revocar | Borra el token guardado. Sin token no hay lectura | La reserva ya incorporada no se toca (regla 4) | No |
| Almacén de tokens | `RepositorioTokens` es un `Protocol`. Implementaciones: en memoria (tests y desarrollo) y PostgreSQL sobre la Base primaria de viajes, tabla `token_correo` | Permite avanzar en paralelo con REF-01. La implementación PostgreSQL usa `BaseViajes` de REF-01 y entra en la última tarea, tras integrar | No |
| API de correo | `Protocol ApiCorreo` y un `MockApiCorreo` con buzones por titular, demora y caída inyectables, que rechaza tokens inválidos | `CON-02`: capa anti-corrupción del Adaptador; el mock es la simplificación de la spec | No |
| Formato de correo crudo | El cuerpo es un JSON con `tipo`, `inicio`, `fin`, `lugar` y `codigo` | Esquema estructurado simple de la spec | No |
| Identificador del mensaje | `Message-ID`; si falta, SHA-256 del contenido crudo | ADR-IT3-003 | No |
| Sondeo sin estado | Cada sondeo lee la ventana completa (7 días) y publica todo. No se guarda hasta dónde se leyó | Regla 2 de la spec: el Adaptador no escribe la Base de viajes | No |
| Frecuencia de sondeo | 15 min por buzón, configurable. El programador expone `tick(ahora)` para los tests | Parámetro de la spec; los tests no esperan tiempo real | No |
| Parseo aislado | Proceso real del sistema operativo (`subprocess`), lanzado con un entorno vacío de credenciales. Habla con el Orquestador de entrada por JSON por líneas (stdin/stdout). Usa solo `pydantic` y la biblioteca estándar | ADR-IT3-007: sin token y sin acceso a la base. El test inspecciona `/proc/<pid>/environ` | No |
| Validación del parseo | Un mensaje es válido si cumple el esquema estructurado, con tope de tamaño (64 KB), campos de texto acotados y sin caracteres de control. Lo demás se descarta | «Contenido malicioso» de `AC-REF-02-04`. El tope de tamaño es un valor de prototipo | No |
| Mensaje enviado al Parseo | `id`, `titular_id`, `remitente` y cuerpo crudo. **Nunca el token** | El Parseo no tiene token | No |
| Entrega tras el parseo | `ConsumidorCorreo` toma de la cola `correo`, parsea y llama a `FiltroRemitentes.recibir`. Si algo falla lanza la excepción y el Broker reintenta (1 s, 2 s, 4 s) y luego va a mensajes muertos | ADR-IT3-002, ADR-IT3-003 | No |
| Contrato con REF-03 | Hasta que exista SPEC-REF-03 se usa `FiltroRemitentesNulo` | Esta spec termina antes del Filtro | No |
| Endpoints de autorización | `POST /correo/autorizacion` con `{"token": ...}` y `X-Titular-Id` (201 con el vencimiento); `DELETE` idempotente (204); sin `X-Titular-Id`, 401 | La spec no dice de dónde sale el token | No |
| Resultado de sondeo | `sondear` devuelve `ResultadoSondeo(leyo, publicados, cola_llena)`; la API caída lanza `ErrorApiCorreo`, que `tick` captura por titular | Una caída o una cola llena no afectan a los demás titulares | No |
| Programador | `tick(ahora)` sondea siempre a todos los titulares con token guardado, sin chequear el intervalo; `ejecutar()` duerme 15 min entre ticks | Los tests no esperan tiempo real | No |
| Mensaje en la cola de correo | `Mensaje(id, {titular_id, remitente, cuerpo})`; nunca el token | ADR-IT3-007 | No |
| Hash sin `Message-ID` | SHA-256 del cuerpo crudo | ADR-IT3-003 | No |
| Validación del Parseo | JSON con exactamente `tipo`, `inicio`, `fin`, `lugar`, `codigo` (`extra="forbid"`); textos de 1 a 200 caracteres, sin caracteres de control (también acota `id`, `titular_id` y `remitente`); `fin` posterior a `inicio`; cuerpo de hasta 64 KB | Concreta «contenido malicioso» de `AC-REF-02-04` | No |
| Descarte del Parseo | El Consumidor lo da por entregado, sin Retry ni mensajes muertos; si el proceso falla o muere, lanza error y el Broker reintenta; el cliente reinicia el proceso | Regla 11 de la spec | No |

## Estructura de Código y Mapeo Arquitectónico

| Ruta en el repositorio | Elemento del paso 5 que instancia | Dependencias permitidas (imports) | Prohibiciones explícitas |
| :--- | :--- | :--- | :--- |
| `src/trotamundos/entrada/gestor_autorizacion/` (`gestor.py`, `cifrado.py`, `repositorio.py`) | Gestor de autorización del correo (ADR-IT3-006) | `dominio`, `config`; **solo este paquete** puede importar `persistencia` (tokens en la Base primaria de viajes) | No importa `orquestador` |
| `src/trotamundos/entrada/api_correo.py` | API de correo (externa): `Protocol` y mock (`CON-02`) | `config` | No importa `persistencia` ni `orquestador` |
| `src/trotamundos/entrada/adaptador_correo.py` | Adaptador de correo, capa anti-corrupción (ITERACION_3) | `entrada.api_correo`, `entrada.gestor_autorizacion` (solo `token_vigente`), `broker` | **No importa `persistencia`**: no escribe la Base de viajes. No importa `orquestador` |
| `src/trotamundos/entrada/programador_sondeo.py` | Sondeo periódico del Adaptador | `entrada.adaptador_correo`, `entrada.gestor_autorizacion` | Ídem |
| `src/trotamundos/entrada/parseo_aislado/` (`esquema.py`, `proceso.py`, `cliente.py`) | Parseo aislado (ADR-IT3-007) | `esquema.py` y `proceso.py`: solo `pydantic` y la biblioteca estándar. `cliente.py`: `asyncio`, `dominio.reserva_normalizada` | **No importa `persistencia`, `config`, `gestor_autorizacion` ni `broker`.** No recibe el token |
| `src/trotamundos/entrada/consumidor_correo.py` | Consumidor de la cola de correo hacia el Filtro | `broker`, `entrada.parseo_aislado.cliente`, `entrada.filtro_remitentes` | No importa `persistencia` ni `orquestador` |
| `src/trotamundos/entrada/app.py` | Endpoints de autorizar y revocar, vía API Gateway | `fastapi`, `entrada.gestor_autorizacion` | No importa `orquestador` |
| `src/trotamundos/persistencia/esquemas/02_tokens.sql` | Tabla `token_correo` en la Base primaria de viajes | — | Solo la usa el Gestor |

Ajuste al test de arquitectura (`tests/test_arquitectura.py`): agregar la prohibición `entrada/parseo_aislado` → `trotamundos.config`, `trotamundos.broker` y `trotamundos.entrada.gestor_autorizacion`, y `entrada/adaptador_correo.py` → `trotamundos.persistencia` (esta última ya existe).

## Tareas de Implementación

| ID | Descripción de la tarea | Archivos a crear / modificar | AC que cubre | Depende de | Criterio de terminado (Done) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `T-REF-02-01` | Configuración del correo (frecuencia, ventana, vigencia, clave), cifrado Fernet y `RepositorioTokens` en memoria | `config.py`, `entrada/gestor_autorizacion/cifrado.py`, `entrada/gestor_autorizacion/repositorio.py`, `pyproject.toml`, `tests/test_ref02_tokens.py` | `AC-REF-02-07` (base del vencimiento) | — | El token se guarda cifrado: el valor almacenado no contiene el texto en claro |
| `T-REF-02-02` | `GestorAutorizacion`: `autorizar`, `revocar`, `token_vigente` (con reloj inyectado), `titulares_autorizados` | `entrada/gestor_autorizacion/gestor.py`, `tests/test_ref02_gestor.py` | `AC-REF-02-07`, `AC-REF-02-01` (sin autorización) | `T-REF-02-01` | Sin token, revocado o vencido: `token_vigente` devuelve `None` |
| `T-REF-02-03` | `ApiCorreo` y `MockApiCorreo` con buzones, demora y caída inyectables | `entrada/api_correo.py`, `tests/test_ref02_api_correo.py` | `AC-REF-02-02` (fuente de mensajes) | — | El mock rechaza tokens inválidos y falla o demora a demanda |
| `T-REF-02-04` | `AdaptadorCorreo.sondear`: sin token no lee; con token lee la ventana y publica cada mensaje con su identificador; cola llena no publica y no pierde; la API caída hace fallar solo ese sondeo | `entrada/adaptador_correo.py`, `tests/test_ref02_adaptador.py` | `AC-REF-02-01`, `AC-REF-02-07`, `AC-REF-02-02`, `AC-REF-02-03` | `T-REF-02-02`, `T-REF-02-03` | Los cuatro escenarios en verde; el mock registra cero lecturas sin token |
| `T-REF-02-05` | `ProgramadorSondeo`: recorre los titulares autorizados cada 15 min (`tick(ahora)` invocable a demanda) | `entrada/programador_sondeo.py`, `tests/test_ref02_programador.py` | `AC-REF-02-09` | `T-REF-02-04` | Dos sondeos seguidos publican el mismo mensaje con el mismo identificador |
| `T-REF-02-06` | Parseo aislado: esquema de validación, proceso con entrada y salida por líneas JSON, y cliente que lo lanza con entorno limpio | `entrada/parseo_aislado/esquema.py`, `proceso.py`, `cliente.py`, `tests/test_ref02_parseo.py` | `AC-REF-02-04`, `AC-REF-02-08`, `AC-REF-02-05` (parseo) | — | Inválidos y maliciosos descartados; el proceso hijo no tiene credenciales de base ni token en su entorno |
| `T-REF-02-07` | `ConsumidorCorreo`: de la cola `correo` al parseo y al Filtro de remitentes, con el identificador intacto. Maneja fallos con el Retry del Broker | `entrada/consumidor_correo.py`, `tests/test_ref02_consumidor.py` | `AC-REF-02-05`, `AC-REF-02-10` | `T-REF-02-06` | La reserva llega al Filtro con su `id_mensaje`; un fallo persistente termina en mensajes muertos con aviso |
| `T-REF-02-08` | App de entrada: `POST /correo/autorizacion` y `DELETE /correo/autorizacion` (por API Gateway, con `X-Titular-Id`) | `entrada/app.py`, `tests/test_ref02_app.py` | `AC-REF-02-06` (revocación), `AC-REF-02-01` | `T-REF-02-02` | Revocar desde el endpoint deja de leer; la reserva ya incorporada permanece |
| `T-REF-02-09` | **Integración, tras fusionar REF-01.** `RepositorioTokens` sobre PostgreSQL usando `BaseViajes`, esquema `02_tokens.sql`, y el test de revocación contra el itinerario real | `entrada/gestor_autorizacion/repositorio.py`, `persistencia/esquemas/02_tokens.sql`, `tests/test_ref02_integracion.py` | `AC-REF-02-06` (de punta a punta) | `T-REF-02-08`, `T-REF-01-03` | Token cifrado persistido en la Base primaria; la reserva ya incorporada sigue tras revocar |

## Matriz de Cobertura de Criterios de Aceptación

| Criterio de Aceptación (Spec) | Tarea(s) del Plan | Nombre del test automatizado | Estado |
| :--- | :--- | :--- | :--- |
| `AC-REF-02-01` | `T-REF-02-02`, `T-REF-02-04`, `T-REF-02-08` | `test_AC_REF_02_01_sin_autorizacion_o_revocado_el_adaptador_no_lee` | `[x] Verde` |
| `AC-REF-02-07` | `T-REF-02-01`, `T-REF-02-02`, `T-REF-02-04` | `test_AC_REF_02_07_token_vencido_no_lee_y_exige_reautorizar` | `[x] Verde` |
| `AC-REF-02-02` | `T-REF-02-03`, `T-REF-02-04` | `test_AC_REF_02_02_sondeo_publica_con_message_id_o_hash` | `[x] Verde` |
| `AC-REF-02-03` | `T-REF-02-04` | `test_AC_REF_02_03_cola_llena_no_publica_no_pierde_y_reintenta_en_el_siguiente_sondeo` | `[x] Verde` |
| `AC-REF-02-04` | `T-REF-02-06` | `test_AC_REF_02_04_parseo_descarta_invalidos_y_maliciosos` | `[x] Verde` |
| `AC-REF-02-08` | `T-REF-02-06` | `test_AC_REF_02_08_proceso_de_parseo_sin_credenciales_ni_token` | `[x] Verde` |
| `AC-REF-02-09` | `T-REF-02-05` | `test_AC_REF_02_09_dos_sondeos_publican_el_mismo_identificador` | `[x] Verde` |
| `AC-REF-02-10` | `T-REF-02-07` | `test_AC_REF_02_10_reintentos_agotados_van_a_mensajes_muertos_con_aviso` | `[x] Verde` |
| `AC-REF-02-05` | `T-REF-02-06`, `T-REF-02-07` | `test_AC_REF_02_05_reserva_valida_llega_al_filtro_con_su_identificador` | `[x] Verde` |
| `AC-REF-02-06` | `T-REF-02-08`, `T-REF-02-09` | `test_AC_REF_02_06_revocar_deja_de_leer_y_conserva_la_reserva_incorporada` | `[ ] Pendiente` (revocación cubierta por T-REF-02-08; falta T-REF-02-09) |

## Estrategia de Pruebas y Simulación de Fallos

* **Tests unitarios / contractuales:** cada pieza se prueba con dobles de sus vecinas: `RepositorioTokens` en memoria, `MockApiCorreo` y un `Broker` real con colas de 5 y backoff sin espera real (se inyecta `dormir`), como ya hacen los tests del esqueleto.
* **Inyección de fallos / latencia:**
  * Cola llena: se llena la cola `correo` con 5 mensajes y se sondea (`AC-REF-02-03`).
  * API de correo caída o lenta: el mock lanza error o demora a demanda; el sondeo falla sin afectar al siguiente.
  * Token vencido: reloj inyectado que avanza más de 60 min.
  * Fallo persistente del consumidor: un `FiltroRemitentes` que siempre lanza, para llegar a mensajes muertos (`AC-REF-02-10`).
* **Aislamiento (`AC-REF-02-08`):** el test lanza el proceso real, lee `/proc/<pid>/environ` y comprueba que no contiene ninguna variable `TROTA_DSN_*` ni `TROTA_CLAVE_TOKENS`, aun cuando el padre las tenga definidas. El test de arquitectura verifica además que el código del Parseo no importa `persistencia`, `config` ni `gestor_autorizacion`.
* **Comando de ejecución:** `.venv/bin/pytest tests/test_ref02_*.py` (los de `T-REF-02-09` requieren `docker compose up -d --wait`).

## Riesgos Técnicos del Plan

* **Dependencia con REF-01 para persistir tokens.** Mitigación: el `Protocol` y el repositorio en memoria desacoplan las ocho primeras tareas; `T-REF-02-09` espera a `T-REF-01-03`.
* **`/proc/<pid>/environ` solo existe en Linux.** Mitigación: el entorno de desarrollo es Linux; el test se salta con un mensaje explícito si no hay `/proc`.
* **Procesos hijo que quedan vivos si un test falla.** Mitigación: el cliente del Parseo se cierra en `finally` y en una fixture, con *timeout* de arranque.
* **`SUPUESTO` de `remitente` y `titular_id` en `ReservaNormalizada`.** Mitigación: ya decidido en el esqueleto; conviene reflejarlo en SPEC-REF-02/03 en la próxima revisión.
* **Tope de 64 KB del correo crudo.** Valor de prototipo confirmado con `OK PLAN` y fijado en la spec, junto con el tope de 200 caracteres por campo.
* **Conflicto en `pyproject.toml` y `tests/test_arquitectura.py` al integrar con REF-01.** Mitigación: cambios aditivos y de pocas líneas; se resuelven en el merge.
