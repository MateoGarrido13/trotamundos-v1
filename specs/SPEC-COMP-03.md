# SPEC-COMP-03. Cliente móvil con GPS

* **Estado:** aprobada
* **Fecha:** 2026-11-23
* **Autores:** [sin especificar]

## Trazabilidad

| Tipo | Identificadores |
| :--- | :--- |
| **Drivers** | `CON-01`, `QA-PER-03`, `QA-USA-01`, `REF-07`, `QA-PER-01`, `REF-03` |
| **ADRs** | `ADR-IT5-003`, `ADR-IT2-001`, `ADR-IT2-002`, `ADR-IT4-009`, `ADR-IT4-004`, `ADR-IT4-007`, `ADR-IT6-001` |
| **Elemento del paso 5** | Cliente móvil con módulo local de proximidad GPS: [RONDA_1/ITERACION_5.md](../RONDA_1/ITERACION_5.md) §D.1 |
| **Incremento (Slice)** | Slice 4 de [planes/PLAN_MAESTRO.md](../planes/PLAN_MAESTRO.md) |

## Propósito y Responsabilidad

Versión móvil del panel (`CON-01`). Al abrirse muestra el login en menos de 1,4 s sobre red 3G (`QA-PER-03`). Después del login pide la vista principal y el alta. En la vista del viaje aprovecha el GPS del dispositivo sobre `Reserva.lugar` (`QA-USA-01`): calcula en el propio dispositivo la distancia a cada reserva, ofrece la ruta nativa y destaca la reserva próxima más cercana. Incluye la sección «Novedades», Mensajes en revisión y el panel del Asistente Virtual.

## Drivers que guían el cómo

* **`QA-PER-03`:** First Contentful Paint (FCP) del login en menos de 1,4 s en el 90 % de las sesiones, sobre red móvil 3G. *(Origen: LISTADO_DRIVERS_RONDA_1)*
* **`QA-USA-01`:** el panel muestra el viaje en una interfaz que aprovecha una capacidad nativa. En el prototipo se verifica por la presencia funcional del cálculo con GPS sobre `Reserva.lugar` y su degradación sin error; la métrica de más de 3,5 estrellas en tiendas es de producción. *(Origen: `ADR-IT5-003`)*

## Conceptos de diseño aceptados

* **Cálculo local de proximidad con GPS, diferido tras el login y con degradación** (`ADR-IT5-003`): la obtención de la posición no se ejecuta en la pantalla de login, sino cuando el viajero abre su viaje activo. Con permiso del sistema operativo, el cliente lee las coordenadas y las compara en el propio dispositivo contra el `lugar` de cada reserva: muestra la distancia y el enlace de navegación nativa y destaca la reserva próxima más cercana. Si el usuario deniega el permiso o una reserva no tiene coordenadas, la vista degrada mostrando el itinerario en orden cronológico con el nombre y destino del lugar, sin distancia ni ruta.
* **Bound execution times y Graceful degradation en la Caché de borde** (`ADR-IT2-001`, `ADR-IT2-002`): el primer contenido del móvil lo sirve la caché de borde dentro de 1,4 s; si la respuesta fresca no llega, entrega la copia que ya tiene.
* **`lugar` como parte del contrato `Reserva`** (`ADR-IT4-009`): nombre, destino y coordenadas cuando se conocen.
* **Sesión con token firmado** (`ADR-IT4-004`) y **autorización por itinerario** (`ADR-IT4-007`): como en el cliente web.

## Relaciones Permitidas

* **Recibe llamadas de:** el viajero, desde su teléfono.
* **Invoca:** el API Gateway (la app principal en el prototipo) y la API nativa de geolocalización del dispositivo.
* **Restricciones de frontera:** las coordenadas **nunca salen del dispositivo**: no se envían al API Gateway ni al Orquestador, ni se guardan (`ADR-IT5-005` rechazado). El cliente no inicializa el GPS en el arranque ni en el login.

## Contrato e Interfaces

| Operación / Mensaje | Dirección / Protocolo | Entrada | Salida | Errores / Cota | Origen |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Primer contenido | Cliente hacia la caché de borde | Recursos estáticos del login | Login renderizado | FCP menor a 1,4 s en el 90 % de las sesiones | `ADR-IT2-001` |
| Vista del viaje | Cliente hacia el Gateway | Identidad | Reservas agrupadas, con `lugar` (nombre, destino y, si hay, coordenadas) | Igual que el cliente web | `ADR-IT4-009` |
| Posición | Cliente hacia la API de geolocalización del dispositivo | — | Coordenadas actuales | Permiso denegado o sin señal: la vista degrada | `ADR-IT5-003` |
| Distancia y ruta | Interna al cliente | Coordenadas del dispositivo y del `lugar` | Distancia en línea recta y enlace a la navegación nativa | Sin coordenadas en la reserva: sin distancia ni ruta | `ADR-IT5-003` |

## Reglas de Comportamiento

1. **Arranque liviano:** el login carga solo lo necesario para renderizarse: una página, su hoja de estilos y el script mínimo, sin framework y sin tocar el GPS. *(Origen: `QA-PER-03`, `ADR-IT5-003`)*
2. **GPS diferido:** la posición se pide recién al abrir un viaje activo y solo si el viajero la concede. *(Origen: `ADR-IT5-003`)*
3. **Cálculo local:** la distancia a cada reserva con coordenadas se calcula en el dispositivo, en línea recta. La reserva activa o próxima más cercana se destaca. *(Origen: `ADR-IT5-003`)*
4. **Ruta nativa:** cada reserva con coordenadas ofrece un enlace que abre la navegación del dispositivo. *(Origen: `ADR-IT5-003`)*
5. **Degradación:** sin permiso, sin señal o sin coordenadas en la reserva, la vista muestra el itinerario en orden cronológico con el nombre y el destino del lugar, sin distancia ni ruta y sin mensaje de error. *(Origen: `ADR-IT5-003`)*
6. **Privacidad:** ningún pedido de red lleva coordenadas del dispositivo. *(Origen: `ADR-IT5-003`, `ADR-IT5-005` rechazado)*
7. **Instalable y con copia local:** el cliente declara un manifiesto y registra un service worker que guarda los recursos estáticos, para que el primer contenido salga de la copia local en las aperturas siguientes. Es la simulación de la caché de borde del móvil. *(Origen: `ADR-IT2-001`, `ADR-IT2-002`)*
8. **Itinerario con conectividad intermitente:** una vez cargada la vista del viaje, el cálculo de distancia sigue funcionando sin red. *(Origen: `ADR-IT5-003`)*
9. **Mismas reglas que el cliente web** para claves de operación, «Error 401», servicio no disponible, texto sin HTML, consentimiento visible y confirmación de acciones del asistente. *(Origen: [SPEC-COMP-02](SPEC-COMP-02.md))*
10. **Pantallas:** ingreso, mis viajes, viaje con proximidad, novedades, agencia y problemas, mensajes en revisión, asistente. La cotización y la gestión de miembros no se incluyen. *(Origen: PLAN_MAESTRO §2: la cotización es del cliente web)*

## Criterios de Aceptación

| ID | Dado (Given) | Cuando (When) | Entonces (Then) | Driver / ADR | Verificación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AC-COMP-03-01` | Red 3G simulada (latencia y ancho de banda limitados) y caché vacía | Se abre la aplicación | El login se renderiza (FCP) en menos de 1,4 s | `QA-PER-03` | Test de navegador con estrangulado de red; medición con la API de pintura |
| `AC-COMP-03-02` | Aperturas siguientes | Se abre la aplicación | El primer contenido sale de la copia local, sin pedido de red para el login | `ADR-IT2-001` | Test de navegador |
| `AC-COMP-03-03` | El viajero está en el login | Se inspecciona el uso de geolocalización | No se pidió el GPS | `ADR-IT5-003` | Test de navegador con espía de `geolocation` |
| `AC-COMP-03-04` | El viajero concede el permiso y hay reservas con coordenadas | Abre su viaje activo | Cada reserva con coordenadas muestra su distancia y un enlace de ruta, y la más cercana está destacada | `QA-USA-01` | Test de navegador con posición simulada |
| `AC-COMP-03-05` | El viajero deniega el permiso | Abre su viaje | Ve el itinerario en orden cronológico, con nombre y destino, sin distancia ni error | `ADR-IT5-003` | Test de navegador |
| `AC-COMP-03-06` | Una reserva sin coordenadas | Se muestra la vista | Esa reserva no muestra distancia ni ruta y las demás sí | `ADR-IT4-009` | Test de navegador |
| `AC-COMP-03-07` | Posición del dispositivo conocida | Se abre el viaje y se inspeccionan todos los pedidos de red | Ningún pedido contiene las coordenadas del dispositivo | `ADR-IT5-003` | Test de navegador con registro de pedidos |
| `AC-COMP-03-08` | Vista del viaje ya cargada | Se corta la red y se mueve la posición | La distancia se recalcula | `ADR-IT5-003` | Test de navegador sin conexión |
| `AC-COMP-03-09` | Un participante intenta una acción sin permiso | El backend responde 403 | El cliente presenta «Error 401» | `QA-SEG-02` | Test de navegador |
| `AC-COMP-03-10` | El navegador del teléfono | Se carga el manifiesto | Es válido y permite instalar la aplicación | `CON-01` | Test de navegador |
| `AC-COMP-03-11` | El asistente degrada a menú | El viajero escribe | Se muestra el menú, sin error | `REF-07` | Test de navegador |

## Parámetros Configurables (Valores de Prototipo)

| Parámetro | Valor en el prototipo | Qué controla | ADR que lo declara parámetro |
| :--- | :--- | :--- | :--- |
| `perfil_3g` | 1,6 Mbit/s de bajada, 150 ms de latencia | La red simulada del test de FCP | — (perfil estándar «Slow 4G/3G» de herramientas de prueba) |
| `cota_fcp_ms` | 1400 | Techo del primer contenido | `ADR-IT2-001` |

## Simplificaciones del Prototipo

| Simplificación adoptada | Driver / ADR afectado | Por qué no invalida la decisión arquitectónica |
| :--- | :--- | :--- |
| PWA instalable en vez de aplicación nativa de tienda | `CON-01`, `QA-USA-01`, `ADR-IT5-003` | La capacidad nativa se usa por la API de geolocalización del navegador, en el dispositivo; la decisión (cálculo local, diferido y con degradación) no cambia. La métrica de estrellas en tiendas queda fuera |
| Service worker en lugar de caché de borde (CDN) | `ADR-IT2-001` | Cumple el mismo papel de servir el primer contenido sin ir al origen |

## Dependencia con el backend

`ADR-IT4-009` define `lugar` con **nombre, destino y coordenadas opcionales**. El código del prototipo guarda hoy `lugar` como un texto, sin coordenadas. [SPEC-REF-04](SPEC-REF-04.md) y [SPEC-REF-01](SPEC-REF-01.md) ya fueron enmendadas (2026-11-23) para que `lugar` lleve nombre, destino y, opcionalmente, latitud y longitud. Queda por cambiar el código y su plan: el plan de esta spec parte de una tarea que migra `lugar` en `Reserva`, en la carga manual, en el asistente y en la analítica, antes de tocar el cliente.

## Fuera de Alcance

* Aplicación nativa publicada en tiendas y su calificación.
* Seguimiento continuo de posición (`ADR-IT5-005`, rechazado).
* Mapa embebido: solo se abre la navegación nativa.

## Decisiones tomadas

1. **`lugar` con coordenadas:** se enmiendan `SPEC-REF-01` y `SPEC-REF-04` y el backend para que `lugar` lleve `destino` y, opcionalmente, `latitud` y `longitud` (como fija `ADR-IT4-009`). Las reservas existentes siguen válidas. Va como primera tarea del plan de esta spec.
2. **Verificación:** los criterios `AC-COMP-03-*` se prueban con Playwright (Chromium), con red estrangulada y posición simulada.

## Historial de Cambios

| Fecha | Cambio | Motivo |
| :--- | :--- | :--- |
| 2026-11-23 | Versión inicial (`borrador`) | Pedido del usuario; PWA elegida como cliente móvil |
| 2026-11-23 | Decisión cerrada: enmienda de `REF-04` y `REF-01` | `lugar` estructurado (nombre, destino, coordenadas opcionales); la migración del código se planifica en `PLAN-COMP-03` |
| 2026-11-23 | Paso a `aprobada` (`OK SPEC`) | Aprobación del usuario tras resolver las decisiones de revisión |
| 2026-11-23 | Decisiones: `lugar` con coordenadas y Playwright | Respuesta del usuario |
