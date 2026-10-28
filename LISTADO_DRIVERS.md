# Listado de drivers

Registro los escenarios con un rótulo estable para citarlos después en las iteraciones y en los ADR. El esquema es `QA-<atributo>-<nn>`: PER rendimiento, DIS disponibilidad, ESC escalabilidad, INT interoperabilidad, SEG seguridad, EVO modificabilidad, USA usabilidad. El número tiene dos dígitos y corre dentro de cada atributo. Los requerimientos funcionales son `REF-01` a `REF-06`. Las restricciones son `CON-01` y `CON-02`.

El texto de cada campo es el que levantamos. En este paso lo ordeno en la plantilla, con las mismas etiquetas y el mismo orden de campos.

## Índice

| Rótulo | Atributo | Estímulo |
| :--- | :--- | :--- |
| `QA-PER-01` | Performance(Latencia) | Actualizacion de API externa(Booking) |
| `QA-PER-02` | Performance(Latencia) | Nueva cotización de viaje seleccionando fecha,hospedaje y compañía. |
| `QA-PER-03` | Performance(Latencia) | El usuario abre la aplicacion mobile. |
| `QA-PER-04*` | Performance(Latencia) | Consulta de tendencias, destinos y cancelaciones de los viajes |
| `QA-DIS-01` | Disponibilidad | Caída abrupta o falta de respuesta de un nodo de procesamiento de cotizacion |
| `QA-ESC-01` | Escalabilidad | Registro masivo sostenido de 100.000 nuevos usuarios diarios. |
| `QA-INT-01` | Interoperabilidad | La empresa firma un acuerdo comercial e instruye integrar la API propietaria de una nueva cadena de hoteles al sistema. |
| `QA-INT-02` | Interoperabilidad | Solicitud de incorporar Instagram como nuevo canal de envío de propuestas e itinerarios a leads/clientes. |QA-USA-
| `QA-SEG-01` | Seguridad y Privacidad (Security) | Ráfaga maliciosa de 50 solicitudes simultáneas de recuperación de contraseña/correo dirigidas a un mismo endpoint. |
| `QA-SEG-02` | Seguridad y Privacidad (Security) | Intento de registrar una nueva actividad (ej. reserva de excursión) dentro del itinerario del viaje compartido. |
| `QA-SEG-03*` | Seguridad y Privacidad (Security) | El titular autoriza la lectura de su correo para detectar mensajes de viaje |
| `QA-EVO-01` | Modificabilidad | Pedido de integrar un medio de transporte que el panel todavía no agrupa en el viaje |
| `QA-USA-01` | Usabilidad | El viajero consulta su viaje en el móvil, que dispone de capacidades nativas como el GPS |
| `REF-01` | Requerimiento funcional | Los elementos del panel se agrupan por viaje y, al completarse, se archivan o salen de la vista principal. |
| `REF-02` | Requerimiento funcional | Sondear y escanear el correo del usuario y agregar al itinerario las reservas de los mensajes de viaje. |
| `REF-03` | Requerimiento funcional | Filtrar y crear whitelists de remitentes seguros para correos de viaje. |
| `REF-04` | Requerimiento funcional | El cliente agrega, actualiza o elimina una reserva a mano en el panel. |
| `REF-05` | Requerimiento funcional | Integración con la agencia de viajes preferida para resolver un problema. |
| `REF-06` | Requerimiento funcional | Consultas analíticas de tendencias, destinos y cancelaciones para el equipo de datos. |
| `CON-01` | Restricción | Las dos versiones son necesarias: web y móvil. |
| `CON-02` | Restricción | La integración con aerolíneas, hoteles, arrendadoras y correo es por APIs. |

## Escenario de Atributo de Calidad: Performance(Latencia) — QA-PER-01

**Rótulo:** `QA-PER-01`

| Campo | Descripción / Redacción Técnica |
| :--- | :--- |
| **Atributo:** | Performance(Latencia) |
| **Origen:** | API Externa |
| **Estímulo:** | Actualizacion de API externa(Booking) |
| **Artefacto:** | Modulo de comunicacion asincrono con los proveedores de anuncios de viajes. |
| **Contexto:** | Operativa normal, 8am. cuando estas empresas cargan sus nuevos viajes |
| **Respuesta:** | El usuario ve expuestos en una seccion "Novedades" los viajes recientes incorporados a la plataforma |
| **Medida de respuesta:** | El tiempo promedio con el que la app refleja las actualizaciones es maximo 5 minutos desde que el listener detecta una actualizacion. |

## Escenario de Atributo de Calidad: Performance(Latencia) — QA-PER-02

**Rótulo:** `QA-PER-02`

| Campo | Descripción / Redacción Técnica |
| :--- | :--- |
| **Atributo:** | Performance(Latencia) |
| **Origen:** | Usuario autenticado desde su navegador |
| **Estímulo:** | Nueva cotización de viaje seleccionando fecha,hospedaje y compañía. |
| **Artefacto:** | Frontend Web y Servicio de consultas |
| **Contexto:** | Conexión de red estandar y sistema operando bajo una carga de 250.000 usuarios concurrentes |
| **Respuesta:** | El sistema valida la sesion y ejecuta la consulta distribuida contra los servicios de inventario, consolida los precios y el navegador renderiza la grilla de resultados. |
| **Medida de respuesta:** | EL tiempo de respuesta total es de 800ms para el 90% de las peticiones |

## Escenario de Atributo de Calidad: Performance(Latencia) — QA-PER-03

**Rótulo:** `QA-PER-03`

| Campo | Descripción / Redacción Técnica |
| :--- | :--- |
| **Atributo:** | Performance(Latencia) |
| **Origen:** | Usuario desde su dispositivo movil(Android/iOS) |
| **Estímulo:** | El usuario abre la aplicacion mobile. |
| **Artefacto:** | App nativa. |
| **Contexto:** | Conexion de red movil 3G en un aeropuerto |
| **Respuesta:** | LA aplicacion renderiza el formulario de login |
| **Medida de respuesta:** | First Contentful Paint (FCP) en menos de 1.4 segundos en el 90% de las sesiones |

## Escenario de Atributo de Calidad: Performance(Latencia) — QA-PER-04*

**Rótulo:** `QA-PER-04*`

| Campo | Descripción / Redacción Técnica |
| :--- | :--- |
| **Atributo:** | Performance(Latencia) |
| **Origen:** | Equipo de datos |
| **Estímulo:** | Consulta de tendencias, destinos y cancelaciones de los viajes |
| **Artefacto:** | Consultas analíticas de Trotamundos |
| **Contexto:** | El panel está en operación: 2 millones de usuarios activos por semana, 15 millones de cuentas, y un pico de domingo a lunes, de jueves a viernes o de una disrupción de viajes |
| **Respuesta:** | El equipo de datos obtiene las tendencias, los destinos y las cancelaciones |
| **Medida de respuesta:** | El informe en promedio es procesado y generado antes de los 10 segundos |

## Escenario de Atributo de Calidad: Disponibilidad — QA-DIS-01

**Rótulo:** `QA-DIS-01`

| Campo | Descripción / Redacción Técnica |
| :--- | :--- |
| **Atributo:** | Disponibilidad |
| **Origen:** | Infraestructura interna |
| **Estímulo:** | Caída abrupta o falta de respuesta de un nodo de procesamiento de cotizacion |
| **Artefacto:** | Sistema de Balanceo de Carga, Módulo de Cotizaciones y Base de Datos. |
| **Contexto:** | Operación normal bajo uso global concurrente (24/7). |
| **Respuesta:** | El sistema detecta el fallo mediante pruebas de salud (health checks), aísla el nodo caído, redirige el tráfico entrante hacia instancias saludables sin perder las peticiones en vuelo, y alerta al equipo de operaciones. |
| **Medida de respuesta:** | El servicio se recupera para el usuario final de forma transparente, acumulando menos de 5 minutos de tiempo de inactividad total al mes. |

## Escenario de Atributo de Calidad: Escalabilidad — QA-ESC-01

**Rótulo:** `QA-ESC-01`

| Campo | Descripción / Redacción Técnica |
| :--- | :--- |
| **Atributo:** | Escalabilidad |
| **Origen:** | Nuevos viajeros ubicados en 3 continentes diferentes. |
| **Estímulo:** | Registro masivo sostenido de 100.000 nuevos usuarios diarios. |
| **Artefacto:** | API de Registros y Base de Datos |
| **Contexto:** | Semana de lanzamiento oficial de la app móvil en las tiendas (alta concurrencia, distribución geográfica dispersa). |
| **Respuesta:** | El sistema procesa la creación de las cuentas, aprovisiona los perfiles y permite a los nuevos usuarios iniciar sesión inmediatamente, sin bloquear ni degradar el servicio de los usuarios existentes. |
| **Medida de respuesta:** | El 100% de los registros se procesan exitosamente (0 rechazos por saturación o timeout) y la confirmación de cuenta en el cliente demora menos de 2 segundos, independientemente del continente de origen. |

## Escenario de Atributo de Calidad: Interoperabilidad — QA-INT-01

**Rótulo:** `QA-INT-01`

| Campo | Descripción / Redacción Técnica |
| :--- | :--- |
| **Atributo:** | Interoperabilidad |
| **Origen:** | Equipo de Negocio / Equipo de Desarrollo. |
| **Estímulo:** | La empresa firma un acuerdo comercial e instruye integrar la API propietaria de una nueva cadena de hoteles al sistema. |
| **Artefacto:** | Capa de Integración / Ingesta de Trotamundos. |
| **Contexto:** | Tiempo de desarrollo (Evolución del producto), con el sistema core ya en producción operando normalmente. |
| **Respuesta:** | El equipo de ingeniería analiza la documentación del proveedor, desarrolla el conector, lo despliega y comienza a recibir reservas sin alterar el motor de viajes ni la base de datos principal de Trotamundos. |
| **Medida de respuesta:** | La integración requiere menos de 2 semanas de esfuerzo de desarrollo y la modificación del código ocurre en un único módulo de frontera (0 impacto en la lógica core) el 100% de las veces. |

## Escenario de Atributo de Calidad: Interoperabilidad — QA-INT-02

**Rótulo:** `QA-INT-02`

| Campo | Descripción / Redacción Técnica |
| :--- | :--- |
| **Atributo:** | Interoperabilidad |
| **Origen:** | Equipo de Comunicaciones / Marketing. |
| **Estímulo:** | Solicitud de incorporar Instagram como nuevo canal de envío de propuestas e itinerarios a leads/clientes. |
| **Artefacto:** | Servicio de Notificaciones |
| **Contexto:** | Sistema en producción con usuarios activos operando normalmente y canales de comunicación previos (ej. Email, WhatsApp) funcionando. |
| **Respuesta:** | El sistema integra la API de Instagram encapsulándola en un nuevo adaptador independiente, procesando los envíos de forma asíncrona sin alterar el código de los canales existentes ni bloquear el hilo de ejecución principal. |
| **Medida de respuesta:** | La integración requiere menos de 1 semana de esfuerzo de desarrollo, impacta exclusivamente en 1 componente nuevo (0 modificaciones en consumidores existentes) y la latencia de los canales previos presenta 0% de degradación. |

## Escenario de Atributo de Calidad: Seguridad y Privacidad (Security) — QA-SEG-01

**Rótulo:** `QA-SEG-01`

| Campo | Descripción / Redacción Técnica |
| :--- | :--- |
| **Atributo:** | Seguridad y Privacidad (Security) |
| **Origen:** | Atacante externo |
| **Estímulo:** | Ráfaga maliciosa de 50 solicitudes simultáneas de recuperación de contraseña/correo dirigidas a un mismo endpoint. |
| **Artefacto:** | Servicio de Autenticación / Login y API Gateway. |
| **Contexto:** | Sistema en producción operando con volúmenes normales de usuarios registrados activos. |
| **Respuesta:** | El sistema detecta el patrón de peticiones, deniega las solicitudes malintencionadas, previene la saturación del servicio, notifica al propietario legítimo de la cuenta sobre la actividad sospechosa y mantiene la plataforma operativa para el resto de los usuarios. |
| **Medida de respuesta:** | El 100% de los accesos no autorizados son rechazados, y la disponibilidad del servicio de login para usuarios legítimos se mantiene activo. |

## Escenario de Atributo de Calidad: Seguridad y Privacidad (Security) — QA-SEG-02

**Rótulo:** `QA-SEG-02`

| Campo | Descripción / Redacción Técnica |
| :--- | :--- |
| **Atributo:** | Seguridad y Privacidad (Security) |
| **Origen:** | Usuario legítimo autenticado con rol de participante en un viaje grupal. |
| **Estímulo:** | Intento de registrar una nueva actividad (ej. reserva de excursión) dentro del itinerario del viaje compartido. |
| **Artefacto:** | Servicio de Gestión de Itinerarios y Módulo de Control de Acceso. |
| **Contexto:** | Sistema en producción con usuarios autenticados activamente y permisos de grupo previamente configurados. |
| **Respuesta:** | El sistema valida los permisos del usuario para el itinerario específico, persiste la nueva actividad, actualiza la vista para los demás miembros designados del grupo y registra la transacción. |
| **Medida de respuesta:** | En el 100% de las solicitudes autorizadas, son procesadas exitosamente, no asi para aquellos que no posean permisos seran redirigidosa una pagina de "Error 401" |

## Escenario de Atributo de Calidad: Seguridad y Privacidad (Security) — QA-SEG-03*

**Rótulo:** `QA-SEG-03*`

| Campo | Descripción / Redacción Técnica |
| :--- | :--- |
| **Atributo:** | Seguridad y Privacidad (Security) |
| **Origen:** | Viajero titular del correo |
| **Estímulo:** | Autoriza la lectura de su correo para detectar mensajes de viaje |
| **Artefacto:** | Procesamiento de correo |
| **Contexto:** | Operación normal del panel. Las reservas del viajero llegan por correo y deben sumarse a su itinerario |
| **Respuesta:** | El sistema accede a ese correo solo con la autorización del titular, detecta los mensajes de viaje y agrega esas reservas a su itinerario |
| **Medida de respuesta:** | EL 100% de usuarios autorizados y que han registrado su email, ven reflejadas las reservas en sus itinerarios. |

## Escenario de Atributo de Calidad: Modificabilidad — QA-EVO-01

**Rótulo:** `QA-EVO-01`

| Campo | Descripción / Redacción Técnica |
| :--- | :--- |
| **Atributo:** | Modificabilidad |
| **Origen:** | Equipo que evoluciona el producto |
| **Estímulo:** | Pedido de integrar un medio de transporte que el panel todavía no agrupa en el viaje |
| **Artefacto:** | Panel de reservas agrupadas por viaje |
| **Contexto:** | El panel ya agrupa hoteles, autos, vuelos, trenes y autobuses, y está en operación |
| **Respuesta:** | Las reservas del medio nuevo quedan agrupadas en el viaje junto con las reservas ya existentes |
| **Medida de respuesta:** | El equipo de desarrollo incorpora un nuevo medio de transporte en el plazo de 3 meses de ezfuerzo de desarrollo |

## Escenario de Atributo de Calidad: Usabilidad — QA-USA-01

**Rótulo:** `QA-USA-01`

| Campo | Descripción / Redacción Técnica |
| :--- | :--- |
| **Atributo:** | Usabilidad |
| **Origen:** | Viajero desde su dispositivo móvil |
| **Estímulo:** | Consulta su viaje en el móvil, que dispone de capacidades nativas como el GPS |
| **Artefacto:** | Aplicación móvil del panel |
| **Contexto:** | El viajero usa el móvil durante el viaje |
| **Respuesta:** | El panel muestra el viaje en una interfaz que aprovecha esa capacidad nativa |
| **Medida de respuesta:** | El nivel de satisfaccion de los usuarios en las app store es mayor a 3.5 estrellas en promedio

## Requerimientos funcionales

**Rótulo:** `REF-01` — Ciclo de vida del viaje

Los elementos en el panel de control deben poder agruparse por viaje y, una vez que el viaje se completa, archivarse o eliminarse automáticamente de la vista principal.

**Rótulo:** `REF-02` — Procesamiento de correo

El sistema debe sondear y escanear el correo electrónico de los usuarios en busca de correos relacionados con viajes para agregar automáticamente las reservas al itinerario.

**Rótulo:** `REF-03` — Filtros y whitelists

Debe permitir filtrar y crear listas de remitentes seguros (whitelists) para ciertos correos electrónicos de viaje.

**Rótulo:** `REF-04` — Gestión manual

Los clientes deben poder agregar, actualizar o eliminar sus reservas existentes de forma manual dentro del panel.

**Rótulo:** `REF-05` — Resolución de problemas

El sistema debe integrarse con la agencia de viajes preferida del usuario para facilitar una rápida resolución de problemas.

**Rótulo:** `REF-06` — Analítica de datos

Trotamundos recopilará datos analíticos de los viajes (tendencias, destinos, cancelaciones) para su monetización por parte del equipo de datos, implicando la ejecución de consultas analíticas pesadas.

## Restricciones

**Rótulo:** `CON-01`

Las dos versiones son necesarias: web y móvil.

**Rótulo:** `CON-02`

La integración con aerolíneas, hoteles, arrendadoras y correo es por APIs.
