# Trotamundos — iteración 1


| Campo                       | Valor                                                                                                  |
| --------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Ronda**                   | 1                                                                                                      |
| **Arranque**                | Greenfield. Se refina el sistema mediante la descomposición que fija la topología del Core.            |
| **Qué toma esta iteración** | La topología del Core para la consulta del viajero, con la escala y los tiempos de respuesta del goal. |


El paso 1 de la ronda está en [README.md](README.md).

## Paso 2. Establecer el goal


| Id           | En el goal o afuera                                                                              |
| ------------ | ------------------------------------------------------------------------------------------------ |
| `REF-01`     | En el goal. Las reservas se agrupan por viaje y, al completarse, se archivan o salen de la vista principal. |
| `QA-PER-02`  | En el goal. Nueva cotización desde la web, en 800 ms.                                            |
| `QA-PER-03`  | En el goal. El usuario abre la aplicación móvil y el primer contenido aparece en menos de 1,4 s. |
| `QA-ESC-01`  | En el goal. Registro masivo de 100.000 usuarios nuevos por día.                                  |
| `QA-DIS-01`  | En el goal. Caída de un nodo de cotización, con menos de 5 minutos de inactividad al mes.        |
| `CON-01`     | En el goal. Las dos versiones son necesarias: web y móvil.                                       |
| `CON-02`     | En el goal. La integración con aerolíneas, hoteles, arrendadoras y correo es por APIs.           |
| `REF-02`     | Afuera. Sondear el correo y agregar al itinerario las reservas de los mensajes de viaje. |
| `REF-03`     | Afuera. Filtrar y armar whitelists de remitentes de correos de viaje. |
| `REF-04`     | Afuera. Agregar, actualizar o eliminar una reserva a mano. |
| `REF-05`     | Afuera. Resolver un problema con la agencia de viajes preferida. |
| `REF-06`     | Afuera. Consultas analíticas de tendencias, destinos y cancelaciones. |
| `QA-PER-01`  | Afuera. Actualización de una API externa.                                                        |
| `QA-INT-01`  | Afuera. Integrar la API propietaria de una cadena hotelera nueva. |
| `QA-PER-04*` | Afuera. Consulta de tendencias, destinos y cancelaciones.                                        |
| `QA-INT-02`  | Afuera. Incorporar Instagram como canal de propuestas e itinerarios.                             |
| `QA-SEG-01`  | Afuera. Ráfaga de recuperación de contraseña.                                                    |
| `QA-SEG-02`  | Afuera. Registrar una actividad en el itinerario compartido.                                     |
| `QA-SEG-03*` | Afuera. El titular autoriza la lectura de su correo.                                             |
| `QA-EVO-01`  | Afuera. Integrar un medio de transporte que el panel todavía no agrupa.                          |
| `QA-USA-01`  | Afuera. El viajero consulta su viaje en el móvil, con una capacidad nativa como el GPS.          |


**Goal.** El objetivo de esta iteración es definir la topología global del Core de la plataforma Trotamundos para que las reservas se agrupen por viaje y, al completarse, se archiven o salgan de la vista principal (`REF-01`). Las dos versiones son necesarias, web y móvil (`CON-01`). Una cotización nueva responde en 800 ms desde la web (`QA-PER-02`). Al abrir la aplicación móvil, el primer contenido aparece en menos de 1,4 s (`QA-PER-03`). El Core atiende el registro de `QA-ESC-01`: 100.000 usuarios nuevos por día, con confirmación en menos de 2 segundos. Ante la caída de un nodo de cotización, el servicio se recupera de forma transparente y acumula menos de 5 minutos de inactividad al mes (`QA-DIS-01`). La integración con aerolíneas, hoteles, arrendadoras y correo es por APIs (`CON-02`).



## Paso 3. Elegir los elementos a refinar


| Elemento   | Por qué este                                                                                                                                                                                           | Movimiento  |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------- |
| El sistema | Reúne `REF-01` en la web y en el móvil (`CON-01`, `QA-PER-02`, `QA-PER-03`), el registro masivo de `QA-ESC-01`, la continuidad de `QA-DIS-01` y las APIs de `CON-02`. La iteración establece la topología de ese Core como descomposición del sistema. | Descomponer |


El sistema se descompone para fijar la topología del Core: el punto en el que el viajero consulta sus reservas agrupadas por viaje, desde la web y desde el móvil.

## Paso 4. Elegir los conceptos de diseño

| Alternativa | Tipo | Beneficia | Perjudica | Queda |
| ----------- | ---- | --------- | --------- | ----- |
| N-Tier (capas / three-tier) | Estilo | Separa presentación, lógica de negocio y datos, sobre una base tradicional y probada (`QA-ESC-01`, `CON-01`, `CON-02`). | Las capas se escalan juntas con menos granularidad que servicios independientes. | Sí |
| Microservicios | Estilo | Servicios independientes y cohesivos (ej. Usuarios, Cotizaciones). | Suma complejidad operativa y de coordinación distribuida. | No |
| Micro-kernel (plugins) | Estilo | Kernel mínimo con funcionalidades acoplables; alta extensibilidad local. | Menos apto para despliegues distribuidos de alta concurrencia (`QA-ESC-01`, `QA-PER-02`). | No |
| Redundant spare | Táctica (disponibilidad) | Un componente duplicado toma el control si falla el primario (hot, warm o cold spare) (`QA-DIS-01`). | Costo de mantener componentes duplicados. | Sí |
| State resynchronization | Táctica (disponibilidad) | Mantiene sincronizado el estado entre el componente activo y el de respaldo (ej. checksum o hash) (`QA-DIS-01`). | Tráfico y lógica extra para sincronizar. | Sí |
| Heartbeat / Ping-Echo | Táctica (disponibilidad) | Detecta fallos silenciosos con mensajes periódicos a un monitor. | Agrega mensajería de monitoreo. | No |
| Múltiples copias de datos (caché) | Táctica (performance) | Guarda cotizaciones previas y respuestas estáticas (`QA-PER-02`). | Los datos pueden estar desactualizados; hay que invalidar. | Sí |
| Procesamiento concurrente (Scatter-Gather) | Táctica (performance) | Paraleliza consultas a varios orígenes y evita sumar latencias en forma lineal (`QA-PER-02`). | Más complejidad de coordinación y manejo de respuestas parciales. | Sí |
| Priorización de recursos | Táctica (performance) | Da más hilos a transacciones críticas (ej. cotizaciones web) frente a reportes analíticos. | Requiere políticas de asignación. | No |
| Capa Anti-Corrupción (ACL) / Adaptadores | Táctica (interoperabilidad) | Aísla el modelo de dominio interno del contrato externo (`CON-02`). | Una capa extra de traducción. | Sí |
| API Gateway | Táctica (interoperabilidad) | Unifica el punto de entrada para clientes móviles y web (`CON-01`). | Es un punto único que hay que dimensionar y hacer redundante. | Sí |
| Service Discovery | Táctica (interoperabilidad) | Registro dinámico de endpoints internos, sin IPs fijas. | Componente adicional de infraestructura. | No |

Tácticas que quedan: Redundant spare, State resynchronization, Múltiples copias de datos (caché), Procesamiento concurrente (Scatter-Gather), Capa Anti-Corrupción (ACL) / Adaptadores y API Gateway.

Prototipo throwaway: ninguno por ahora.