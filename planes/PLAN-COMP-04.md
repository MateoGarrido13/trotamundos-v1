# PLAN-COMP-04. Correo real (Gmail API)

* **Spec asociada:** [SPEC-COMP-04](../specs/SPEC-COMP-04.md) (aprobada)
* **Estado:** aprobado (`OK PLAN`, 2026-11-23)
* **Fecha:** 2026-11-23
* **Incremento (Slice):** Slice 3 de [PLAN_MAESTRO.md](PLAN_MAESTRO.md)

No cambia el Adaptador de correo, el Parseo aislado, el filtro ni el Orquestador. Agrega la implementación real del puerto `ApiCorreo` y el flujo OAuth, y los conecta en `composicion.py` y `app.py`. Los tests automáticos usan un Google simulado (`httpx.MockTransport`); la prueba contra Google real (`AC-COMP-04-10`) es manual.

## Decisiones Técnicas Locales

Las decisiones que la spec dejaba abiertas las tomó el asistente por delegación del usuario (2026-11-23), igual que en `PLAN-COMP-06`. Ninguna cambia un ADR ni agrega un elemento de arquitectura.

| # | Decisión | Elegida | Motivo | ¿Afecta driver o requiere ADR? |
| :--- | :--- | :--- | :--- | :--- |
| D1 | Cliente de Gmail | `httpx` contra la API REST de Gmail y de OAuth. Sin la biblioteca oficial de Google. `httpx` pasa de dependencia de desarrollo a dependencia de ejecución en `pyproject.toml` | Se usan 5 llamadas. La biblioteca oficial es síncrona y trae decenas de dependencias. `httpx` ya está en el proyecto y permite simular a Google con `MockTransport` | No |
| D2 | Dónde vive | Paquete `src/trotamundos/entrada/gmail/`, con `mensajes.py`, `api.py` y `oauth.py`. **Solo `composicion.py` lo importa** | «Nada fuera de la clase nueva importa el cliente de Google». Se verifica con un test de arquitectura | No |
| D3 | Cliente HTTP | `ApiGmail` y `ServicioOAuth` reciben un `httpx.AsyncClient` ya armado. La composición lo crea y lo cierra al apagar la app | Los tests inyectan un cliente con transporte simulado, sin red | No |
| D4 | Almacén del `state` | En memoria del proceso: un solo uso, ligado al titular, vence a los 600 s (`vigencia_state_segundos`, nuevo). `secrets.token_urlsafe(32)` | La spec pide un `state` de un solo uso. Es una simplificación de prototipo (un proceso); se declara en «Simplificaciones» | No |
| D5 | Vigencia del token | La del Gestor (60 min, `REF-02`). Se ignora el `expires_in` de Google. Se pide `access_type=online` y no se guarda ningún token de renovación | Regla 3 de la spec | No |
| D6 | Token rechazado por Gmail (401) | `ApiGmail` lanza `TokenInvalido`. El `ProgramadorSondeo` lo captura y **revoca el token local** de ese titular, para que no se lea hasta autorizar de nuevo. Es un cambio de 3 líneas en `programador_sondeo.py` con su test | `AC-04` pide que el titular quede sin lectura. Ni la API ni el Adaptador conocen al Gestor | No |
| D7 | Orden al revocar | 1) se borra el token local, 2) se pide la revocación a Google con la cota de 10 s. Si Google falla, se registra un aviso (sin el token) y el borrado local ya está hecho | Regla de la spec: «el token local igual se borra» | No |
| D8 | Endpoint de revocar | Se mantiene `DELETE /correo/autorizacion`. `crear_router(gestor, al_revocar=None)` recibe un hook opcional que la composición llena con la revocación en Google. El hook recibe el token que había antes de borrarlo | No se duplican rutas ni se rompen los tests de `REF-02` | No |
| D9 | Endpoints nuevos | `POST /correo/oauth/iniciar` (con `X-Titular-Id`) devuelve `{"url"}`. `GET /correo/oauth/callback?code=&state=` completa la autorización y devuelve JSON `{"titular_id", "vence"}`. Un `state` inválido, usado o vencido responde `400` sin detalle ni efecto | La spec define las operaciones pero no el verbo ni la forma de la respuesta | No |
| D10 | Elección real o mock | Si `TROTA_GMAIL_CLIENT_ID` y `TROTA_GMAIL_CLIENT_SECRET` están definidos, `app.py` usa Gmail; si no, `MockApiCorreo` y un aviso en el log (regla 8). Con un solo valor definido, también mock y aviso | Los tests de `COMP-01` siguen usando el mock sin tocar nada | No |
| D11 | Secretos | `ConfiguracionGmail.client_secret` con `repr=False`. `ApiGmail` manda el token **solo** en el encabezado `Authorization`; al revocar lo manda en el cuerpo del formulario, nunca en la URL | `AC-07`: nada de esto debe aparecer en un log (`httpx` registra las URL) | No |
| D12 | Lectura de la ventana | `GET messages?q=after:<epoch>&maxResults=<=100` paginando con `nextPageToken`, hasta `max_mensajes_por_sondeo` (100). Después, `GET messages/{id}?format=full` con a lo sumo 10 en paralelo. Se descartan los de `internalDate` anterior a `desde` | La consulta `after:` de Gmail tiene resolución de día; el filtro por `internalDate` es exacto | No |
| D13 | Cuerpo | Se prefiere `text/plain`. Si no hay, se reduce `text/html` a texto con `html.parser` (se descartan `script` y `style`, los bloques pasan a saltos de línea y se resuelven las entidades). Se ignoran las partes con `filename` o `attachmentId`. Se decodifica con el `charset` de la parte (UTF-8 por defecto, con reemplazo) | Regla 6 de la spec | No |
| D14 | Remitente | Solo la dirección del encabezado `From`, en minúsculas (`email.utils.parseaddr`) | Es la forma que compara la whitelist de `REF-03` | No |
| D15 | Contenido esperado | El texto del correo debe traer el JSON de reserva que el Parseo valida (`REF-02`). Para la demo manual se envía un correo cuyo cuerpo es ese JSON | No se cambia el Parseo (spec). Se documenta en la demo | No |
| D16 | Cotas | Una sola cota por llamada (`cota_llamada_gmail_segundos`, 10) con `httpx.Timeout`. Un vencimiento es `ErrorApiCorreo`; no se reintenta (regla 9) | Regla 9 | No |

## Estructura de Código y Mapeo Arquitectónico

| Ruta en el repositorio | Elemento del paso 5 que instancia | Dependencias permitidas (imports) | Prohibiciones explícitas |
| :--- | :--- | :--- | :--- |
| `src/trotamundos/entrada/gmail/mensajes.py` | Capa anti-corrupción de Gmail: traduce el mensaje de Gmail a `CorreoCrudo` | Biblioteca estándar, `entrada.api_correo` | `httpx`, `persistencia`, `broker`, `orquestador` |
| `src/trotamundos/entrada/gmail/api.py` | `ApiGmail`: implementa el puerto `ApiCorreo` contra Gmail | `httpx`, `entrada.api_correo`, `entrada.gmail.mensajes`, `config` | `persistencia`, `broker`, `orquestador`, `entrada.gestor_autorizacion` |
| `src/trotamundos/entrada/gmail/oauth.py` | Flujo de consentimiento OAuth y revocación en Google, sobre el Gestor de autorización | `httpx`, `config`, `entrada.gestor_autorizacion` | `persistencia`, `broker`, `orquestador`, `entrada.gmail.api` |
| `src/trotamundos/entrada/gmail/rutas.py` | Endpoints `/correo/oauth/*` (API Gateway hacia el Gestor) | `fastapi`, `entrada.gmail.oauth` | `persistencia`, `broker`, `orquestador` |
| `src/trotamundos/entrada/app.py` (se modifica) | Endpoint de revocar con hook `al_revocar` | `entrada.gestor_autorizacion` | **`entrada.gmail`** (lo conecta la composición) |
| `src/trotamundos/entrada/programador_sondeo.py` (se modifica) | `TokenInvalido` revoca el token local | lo que ya importa | `entrada.gmail` |
| `src/trotamundos/config.py` (se modifica) | `ConfiguracionGmail` | — | — |
| `src/trotamundos/composicion.py` (se modifica) | `ensamblar_gmail(...)`: único lugar que importa `entrada.gmail` | todo `entrada` | — |
| `src/trotamundos/app.py` (se modifica) | Elige Gmail o mock, monta las rutas OAuth, cierra el cliente HTTP | — | — |
| `pyproject.toml` (se modifica) | `httpx` como dependencia de ejecución | — | — |
| `tests/test_arquitectura.py` (se modifica) | Reglas de este plan | — | — |

Reglas nuevas de arquitectura: `entrada/gmail` sin `persistencia`, `broker`, `orquestador`; `entrada/gmail/mensajes` sin `httpx`; **ningún módulo fuera de `composicion.py` importa `trotamundos.entrada.gmail`** (test propio); ningún módulo de `src` fuera de `entrada/gmail` importa `httpx` (test propio).

Parámetros nuevos en `ConfiguracionGmail` (variables `TROTA_*`): `client_id` (`TROTA_GMAIL_CLIENT_ID`), `client_secret` (`TROTA_GMAIL_CLIENT_SECRET`, sin `repr`), `redireccion_oauth` (`http://localhost:8000/correo/oauth/callback`), `max_mensajes_por_sondeo` 100, `cota_llamada_gmail_segundos` 10, `vigencia_state_segundos` 600 (nuevo, D4) y las cuatro URL de Google (autorización, token, revocación, API de Gmail), configurables para apuntar al simulado.

## Tareas de Implementación

| ID | Descripción de la tarea | Archivos a crear / modificar | AC que cubre | Depende de | Criterio de terminado (Done) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `T-COMP-04-01` | `ConfiguracionGmail`, `httpx` como dependencia de ejecución, reglas de arquitectura y el Google simulado de los tests | `config.py`, `pyproject.toml`, `tests/test_arquitectura.py`, `tests/comp04_util.py` | — (base de las demás) | — | Los tests de arquitectura corren y el secreto no aparece en el `repr` |
| `T-COMP-04-02` | Traducción de un mensaje de Gmail a `CorreoCrudo`: cuerpo en texto, HTML reducido, sin adjuntos, `Message-ID`, remitente y fecha | `entrada/gmail/mensajes.py`, `tests/test_comp04_mensajes.py` | `AC-COMP-04-08`, `AC-COMP-04-09` | 01 | Sin `Message-ID` el identificador es el hash estable; el HTML y los adjuntos no llegan |
| `T-COMP-04-03` | `ApiGmail.leer_mensajes`: paginación, tope, paralelismo acotado, cota, 401 a `TokenInvalido` y el resto a `ErrorApiCorreo`, token solo en el encabezado | `entrada/gmail/api.py`, `tests/test_comp04_api.py` | `AC-COMP-04-03` (lado API), `AC-COMP-04-07` | 02 | Con Google simulado devuelve los `CorreoCrudo` de la ventana y ningún log contiene el token |
| `T-COMP-04-04` | `ServicioOAuth`: `iniciarAutorizacion`, `completarAutorizacion`, `state` de un solo uso con vencimiento, revocación en Google | `entrada/gmail/oauth.py`, `tests/test_comp04_oauth.py` | `AC-COMP-04-01`, `AC-COMP-04-02` | 01 | La URL lleva `gmail.readonly` y el `state`; un `state` repetido, vencido o ajeno no guarda nada |
| `T-COMP-04-05` | Rutas `/correo/oauth/*`, hook `al_revocar`, revocación del token local ante `TokenInvalido`, y la elección Gmail o mock en `composicion.py` y `app.py` | `entrada/gmail/rutas.py`, `entrada/app.py`, `entrada/programador_sondeo.py`, `composicion.py`, `app.py`, `tests/test_comp04_sondeo.py` | `AC-COMP-04-04`, `AC-COMP-04-05`, `AC-COMP-04-06` | 03, 04 | Un 401 deja al titular sin lectura; un titular caído no frena a los demás; revocar no llama a Gmail y borra el token aunque Google falle |
| `T-COMP-04-06` | Prueba de punta a punta con Gmail simulado (necesita las bases: marca `db`) y de que el token no figura en claro en la base ni en los logs | `tests/test_comp04_punta_a_punta.py` | `AC-COMP-04-03` (reservas en el itinerario), `AC-COMP-04-07` (base) | 05 | Los mensajes de viaje del buzón simulado terminan como reservas del itinerario |

## Matriz de Cobertura de Criterios de Aceptación

| Criterio de Aceptación (Spec) | Tarea(s) del Plan | Nombre del test automatizado | Estado |
| :--- | :--- | :--- | :--- |
| `AC-COMP-04-01` | `T-COMP-04-04` | `test_AC_COMP_04_01_la_url_de_consentimiento_pide_solo_lectura_con_state` | `[x] Verde` |
| `AC-COMP-04-02` | `T-COMP-04-04` | `test_AC_COMP_04_02_un_state_usado_se_rechaza_y_no_guarda_token` | `[x] Verde` |
| `AC-COMP-04-03` | `T-COMP-04-03`, `T-COMP-04-06` | `test_AC_COMP_04_03_los_mensajes_del_buzon_llegan_como_reservas_del_itinerario` (`test_comp04_punta_a_punta`) | `[x] Verde` |
| `AC-COMP-04-04` | `T-COMP-04-05` | `test_AC_COMP_04_04_un_401_deja_al_titular_sin_lectura_hasta_autorizar_de_nuevo` | `[x] Verde` |
| `AC-COMP-04-05` | `T-COMP-04-05` | `test_AC_COMP_04_05_gmail_caido_falla_solo_ese_titular` | `[x] Verde` |
| `AC-COMP-04-06` | `T-COMP-04-05` | `test_AC_COMP_04_06_revocar_no_llama_a_gmail_y_borra_el_token` | `[x] Verde` |
| `AC-COMP-04-07` | `T-COMP-04-03`, `T-COMP-04-06` | `test_AC_COMP_04_07_el_token_viaja_solo_en_el_encabezado_y_no_figura_en_ningun_log` (API) y `test_AC_COMP_04_07_el_token_no_figura_en_claro_en_logs_ni_en_la_base` (base) | `[x] Verde` |
| `AC-COMP-04-08` | `T-COMP-04-02` | `test_AC_COMP_04_08_sin_message_id_se_identifica_por_hash_estable` y `test_AC_COMP_04_08_dos_sondeos_de_un_mensaje_sin_message_id_no_duplican_la_reserva` | `[x] Verde` |
| `AC-COMP-04-09` | `T-COMP-04-02` | `test_AC_COMP_04_09_html_y_adjuntos_se_entregan_solo_como_texto` | `[x] Verde` |
| `AC-COMP-04-10` | — | **Demo manual** (ver más abajo). No se marca verde por un test | `[ ] Pendiente (manual)` |

Notas de cobertura: `AC-03` y `AC-07` tienen dos tests (el de `ApiGmail` y el de punta a punta con la base). `AC-08` verifica además que dos sondeos seguidos dan los mismos identificadores; el descarte de duplicados lo hace la ingesta y ya lo cubre `REF-03`. `AC-05` se prueba con dos titulares: uno con el Google simulado caído (`500`) y otro sano.

Cambios respecto de lo planeado al implementar: la cota de cada llamada se aplica también con `asyncio.wait_for` (el `timeout` de `httpx` no rige sobre un transporte simulado ni acota la llamada entera), `ServicioOAuth.descartar_estado` evita que las rutas toquen el almacén de `state`, y el HTML reduce `&nbsp;` a un espacio normal.

## Estrategia de Pruebas y Simulación de Fallos

* **Google simulado:** `tests/comp04_util.py` define `GoogleSimulado`, un manejador de `httpx.MockTransport` con buzones por token, los cuatro endpoints (autorización no se llama; token, revocación, lista y detalle de mensajes), los contadores de llamadas y las fallas inyectables: `responder = 401 | 500 | demora`, y mensajes multipart con HTML y adjuntos grabados con la forma real del contrato de Gmail.
* **Fallos:** 401 (token rechazado), 500 y demora mayor que la cota (se ajusta `cota_llamada_gmail_segundos` en el test para no esperar 10 s), y Google caído al revocar.
* **Logs y base (`AC-07`):** `caplog` en nivel `DEBUG` sobre todos los loggers (incluidos `httpx` y `httpcore`) durante un flujo completo con un token reconocible, y lectura directa de la columna `token_cifrado` de `token_correo`.
* **Punta a punta (`T-COMP-04-06`):** reutiliza las fábricas de `tests/ref03_util.py` y las bases de test. Necesita Docker; los demás tests no.
* **Comando de ejecución:** `pytest tests/test_comp04_*.py tests/test_arquitectura.py`. Antes de terminar, la suite completa.

### Demo manual de `AC-COMP-04-10` (no automatizable)

1. En Google Cloud Console: proyecto con la Gmail API habilitada, pantalla de consentimiento en modo «Testing» con la cuenta de prueba agregada, credencial OAuth de tipo «Aplicación web» con la redirección `http://localhost:8000/correo/oauth/callback`.
2. Arrancar la app con `TROTA_GMAIL_CLIENT_ID`, `TROTA_GMAIL_CLIENT_SECRET` y `TROTA_SONDEO_MINUTOS=1` (sondeo cada minuto).
3. `POST /correo/oauth/iniciar` con `X-Titular-Id`, abrir la URL, aceptar el permiso de solo lectura.
4. Desde otra cuenta, enviar a la cuenta de prueba un correo cuyo cuerpo sea el JSON de reserva de `REF-02`, desde un remitente que ya esté en la whitelist del titular.
5. Esperar el sondeo y consultar `GET /viajes`: la reserva debe figurar en el itinerario.

## Riesgos Técnicos del Plan

* **Choque con COMP-05 y COMP-06 en `config.py`, `composicion.py` y `app.py`:** los tres planes tocan esos archivos. Mitigación: bloques nuevos y aislados (`ConfiguracionGmail`, `ensamblar_gmail`, una rama de elección en `app.py`) y `git merge main` antes de cerrar `T-COMP-04-05`.
* **Tests con base de datos compartidos entre sesiones:** dos sesiones corriendo `pytest` contra `trotamundos_test` a la vez producen `DeadlockDetected` (pasó con COMP-06 y COMP-05). Mitigación: `T-COMP-04-06` es el único de este plan que usa la base; se corre solo cuando ninguna otra sesión lo hace.
* **El contrato de Gmail se reproduce de memoria, no contra Google:** una diferencia (por ejemplo en la forma de `payload.parts`) pasaría los tests y fallaría en la demo. Mitigación: los mensajes simulados siguen la documentación de `users.messages.get` y se prueban con las variantes de partes anidadas; `AC-10` es la comprobación real.
* **Estado del `state` en memoria:** se pierde al reiniciar el proceso y no sirve con varios nodos. Es una simplificación declarada; en la demo es un solo proceso.
* **Google restringe el alcance `gmail.readonly`:** una app sin verificar solo funciona con usuarios de prueba. La verificación está fuera de alcance en la spec.
* **El cuerpo debe ser el JSON de reserva:** un correo de aerolínea real no lo es y el Parseo lo descartará. Es el alcance de `REF-02` y no se cambia aquí.
