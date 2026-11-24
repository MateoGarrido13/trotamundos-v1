# Propuesta de specs faltantes (borrador para decisión)

> **Actualización 2026-11-23:** las specs propuestas ya están redactadas y aprobadas (`OK SPEC`, 2026-11-23): [COMP-02](SPEC-COMP-02.md) cliente web, [COMP-03](SPEC-COMP-03.md) cliente móvil, [COMP-04](SPEC-COMP-04.md) correo real, [COMP-05](SPEC-COMP-05.md) identidad regional, [COMP-06](SPEC-COMP-06.md) cotización, [COMP-07](SPEC-COMP-07.md) novedades de Booking, [COMP-08](SPEC-COMP-08.md) notificaciones. La A es [SPEC-COMP-01](SPEC-COMP-01.md), ya implementada.

* **Fecha:** 2026-11-23
* **Origen:** prueba de humo del prototipo (REF-01 a REF-07 implementadas, 568 tests en verde) y `planes/PLAN_MAESTRO.md`.

Esto **no es una spec**. Es el mapa de lo que falta, con lo que necesita decidirse antes de redactar cada una. La política (`POLITICAS_SPECS_Y_PLANES.md` §1.2) pide que, si aparece una elección de arquitectura sin ADR, se frene y se registre primero el ADR.

## 1. Hallazgos de la prueba de humo

| # | Hallazgo | Gravedad |
| :--- | :--- | :--- |
| H1 | `trotamundos.app:app` **no consume ninguna cola del Broker** (correo, novedades, casos de ayuda, eventos analíticos). Solo los tests llaman a `procesar_uno`. En ejecución real un caso queda «en trámite» para siempre y la analítica no recibe nada | Alta |
| H2 | La app principal **no monta** asistente, analítica, `POST /correo/autorizacion` ni `POST /agencia/{agencia}/avisos`: son sub-apps que solo arman los tests | Alta |
| H3 | **No hay forma de crear un viaje, un itinerario ni una membresía por API.** Sin datos sembrados todo devuelve `acceso_denegado`. Se agregó `scripts/sembrar_demo.py` como paliativo | Alta |
| H4 | El campo `tipo` sale como `hotel` al crear y como `ReservaHotel` al listar. Un cliente no puede usarlo de forma uniforme | Media |
| H5 | La base de desarrollo y la de los tests es la misma: correr `pytest` borra los datos de demo | Media |
| H6 | No hay adaptador de correo real: `ApiCorreo` es un puerto con mock | Esperado (CON-02) |
| H7 | No hay login ni emisión de token. La identidad es el header `X-Viajero-Id` | Esperado (Slice 1 sin spec) |

Funciona bien y verificado a mano: alta idempotente de reservas, permisos por rol (403 al intruso, participante creando), validación de tipo (422), elegir agencia con consentimiento, `GET /viajes` agrupado.

## 2. Specs propuestas

| Propuesta | Contenido | Drivers (ya existen) | Depende de | Decisión que necesito |
| :--- | :--- | :--- | :--- | :--- |
| **A. Sistema ejecutable** (corrige H1 a H5) | Un solo `create_app` que monta todos los routers, arranca los consumidores de cada cola en el ciclo de vida, y expone alta de viaje/itinerario y membresías. Normaliza `tipo`. Base de desarrollo separada de la de tests | `REF-01`, `REF-04`, `REF-05`, `REF-06`, `REF-07` | nada | ¿Va como spec nueva o como enmienda a las existentes? No cambia ningún ADR |
| **B. Cliente web** | Vista agrupada por viaje, gestión manual, novedades, casos, revisión y whitelist, panel del asistente, página «Error 401», informe de analítica. HTML5 + CSS + JS vanilla (Plan Maestro) | `CON-01`, `REF-01`, `REF-03` a `REF-07` | A | Alcance de pantallas; si incluye cotización (depende de F) |
| **C. Cliente móvil con GPS** | Vista liviana, `navigator.geolocation` sobre `Reserva.lugar`, asistente. Meta de carga < 1,4 s desde caché de borde | `QA-USA-01`, `QA-PER-03`, `CON-01`, `REF-07` | A, y E para la meta de 1,4 s | PWA instalable o página móvil simple |
| **D. Correo real** | Adaptador `ApiCorreo` contra un proveedor real, con OAuth, sondeo, tokens cifrados (REF-02 ya fija todo detrás del puerto) | `REF-02`, `QA-SEG-03*`, `CON-02` | A | **Qué proveedor** (Gmail API, Microsoft Graph o IMAP) y credenciales de prueba |
| **E. Identidad regional y borde** (Slice 1) | Alta en región, token firmado validado en el gateway, contención de 50 solicitudes simultáneas, caché de borde | `QA-ESC-01`, `QA-SEG-01`, `QA-PER-02`, `QA-PER-03` | nada | Requiere **código de REF nuevo**: hoy no existe |
| **F. Cotización resiliente** (Slice 2) | Scatter-Gather a 3 adaptadores, Ping/Echo, degradación elegante, caché 800 ms | `QA-PER-02`, `QA-INT-01`, `CON-02` | nada | Código de REF nuevo |
| **G. Novedades de Booking y notificaciones** (Slice 3) | Push de Booking a la cola de novedades (< 5 min) y envío por `ICanal` sumando Instagram | `QA-PER-01`, `QA-INT-02` | A | Código de REF nuevo |

**Problema de nomenclatura:** la política dice que una spec es un requerimiento `REF-01` a `REF-07`, y que E, F y G «no tienen spec en esta tanda». Para escribirlas hay que ampliar la política (por ejemplo `SPEC-QA-<NN>`) o definir nuevos `REF`. Los drivers no se pueden inventar (`listado-drivers-cerrado`), así que A, B y C se redactarían bajo los `REF` y `QA` que ya existen.

## 3. Orden recomendado

1. **A** (sistema ejecutable): sin esto nada de lo demás se puede probar de punta a punta.
2. **B** y luego **C**: dan la interfaz que hoy falta.
3. **D**: el correo real, cuando exista el proveedor y las credenciales.
4. **E, F, G**: completan los 5 slices del Plan Maestro.
