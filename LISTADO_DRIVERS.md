# Listado de drivers

Registro los escenarios con un rótulo estable para citarlos después en las iteraciones y en los ADR. El esquema es `QA-<atributo>-<nn>`: PER rendimiento, DIS disponibilidad, ESC escalabilidad, INT interoperabilidad, SEG seguridad. El número tiene dos dígitos y corre dentro de cada atributo.

El texto de cada campo es el que levantamos. En este paso lo ordeno en la plantilla, con las mismas etiquetas y el mismo orden de campos.

## Índice

| Rótulo | Atributo | Estímulo |
| :--- | :--- | :--- |
| `QA-PER-01` | Performance(Latencia) | Actualizacion de API externa(Booking) |
| `QA-PER-02` | Performance(Latencia) | Nueva cotización de viaje seleccionando fecha,hospedaje y compañía. |
| `QA-PER-03` | Performance(Latencia) | El usuario abre la aplicacion mobile. |
| `QA-DIS-01` | Disponibilidad | Caída abrupta o falta de respuesta de un nodo de procesamiento de cotizacion |
| `QA-ESC-01` | Escalabilidad | Registro masivo sostenido de 100.000 nuevos usuarios diarios. |
| `QA-INT-01` | Interoperabilidad | La empresa firma un acuerdo comercial e instruye integrar la API propietaria de una nueva cadena de hoteles al sistema. |
| `QA-INT-02` | Interoperabilidad | Solicitud de incorporar Instagram como nuevo canal de envío de propuestas e itinerarios a leads/clientes. |
| `QA-SEG-01` | Seguridad y Privacidad (Security) | Ráfaga maliciosa de 50 solicitudes simultáneas de recuperación de contraseña/correo dirigidas a un mismo endpoint. |
| `QA-SEG-02` | Seguridad y Privacidad (Security) | Intento de registrar una nueva actividad (ej. reserva de excursión) dentro del itinerario del viaje compartido. |

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
