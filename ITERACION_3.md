# Trotamundos — iteración 3


| Campo                       | Valor                                                                                                                                                                  |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Ronda**                   | 1                                                                                                                                                                      |
| **Arranque**                | Refinamiento. Se retoma el Core de las iteraciones 1 y 2 y se extiende con la ingesta de información externa.                                                         |
| **Qué toma esta iteración** | La entrada de información externa al modelo de viaje: novedades de proveedores, conectores nuevos, un medio de transporte nuevo, el canal de Instagram y el correo. |


El paso 1 de la ronda está en [README.md](README.md). El cierre de la iteración anterior está en [ITERACION_2.md](ITERACION_2.md).

## Paso 2. Establecer el goal


| Id           | En el goal o afuera                                                                                                                                                                               |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `QA-PER-01`  | En el goal. Actualización de una API externa (Booking). La app refleja las novedades en la sección "Novedades" en 5 minutos como máximo desde que el listener detecta la actualización.           |
| `QA-INT-01`  | En el goal. Integrar la API propietaria de una cadena hotelera nueva en menos de 2 semanas de esfuerzo, con la modificación en un único módulo de frontera y 0 impacto en la lógica core.        |
| `QA-EVO-01`  | En el goal. Integrar un medio de transporte que el panel todavía no agrupa en el viaje, en un plazo de 3 meses de esfuerzo de desarrollo.                                                         |
| `QA-INT-02`  | En el goal. Incorporar Instagram como canal de envío de propuestas e itinerarios, en menos de 1 semana, con 1 componente nuevo y 0 modificaciones en los consumidores existentes.                 |
| `QA-SEG-03*` | En el goal. El titular autoriza la lectura de su correo. El sistema accede solo con esa autorización y agrega las reservas a su itinerario.                                                       |
| `REF-02`     | En el goal. Sondear y escanear el correo del usuario y agregar al itinerario las reservas de los mensajes de viaje.                                                                               |
| `REF-03`     | En el goal. Filtrar y armar whitelists de remitentes seguros para los correos de viaje.                                                                                                           |
| `QA-ESC-01`  | Afuera. Sigue parcial desde la iteración 1 y queda para la iteración 4, junto con el registro, el acceso y los datos de usuario.                                                                  |
| `QA-SEG-01`  | Afuera. Ráfaga de recuperación de contraseña. Queda para la iteración 4.                                                                                                                          |
| `QA-SEG-02`  | Afuera. Registrar una actividad en el itinerario compartido. Queda para la iteración 4, sobre el modelo de reservas que fija esta iteración.                                                      |
| `QA-PER-04*` | Afuera. Consulta de tendencias, destinos y cancelaciones. Queda para la iteración 4.                                                                                                              |
| `REF-04`     | Afuera. Agregar, actualizar o eliminar una reserva a mano. Queda para la iteración 4.                                                                                                             |
| `REF-05`     | Afuera. Resolver un problema con la agencia de viajes preferida. Queda para la iteración 4.                                                                                                       |
| `REF-06`     | Afuera. Consultas analíticas de tendencias, destinos y cancelaciones. Queda para la iteración 4.                                                                                                  |
| `QA-USA-01`  | Afuera. El viajero consulta su viaje en el móvil, con una capacidad nativa como el GPS. Queda para la iteración 4.                                                                                |


**Drivers ya resueltos:** `REF-01`, `CON-01`, `CON-02` (iteración 1) y `QA-PER-02`, `QA-PER-03`, `QA-DIS-01` (iteración 2).

**Goal.** El objetivo de esta iteración es definir cómo entra al modelo de viaje la información que viene de afuera de Trotamundos y cómo se extiende el Core sin tocarlo. Las novedades de las APIs de los proveedores se reflejan en la sección "Novedades" en 5 minutos como máximo desde que el listener detecta la actualización (`QA-PER-01`). Un conector nuevo, como el de una cadena hotelera, se integra en menos de 2 semanas y en un único módulo de frontera (`QA-INT-01`). Un medio de transporte nuevo queda agrupado en el viaje junto con las reservas existentes en un plazo de 3 meses (`QA-EVO-01`). Instagram se suma como canal de propuestas e itinerarios en menos de 1 semana, en un componente nuevo y sin modificar a los consumidores (`QA-INT-02`). Con la autorización del titular (`QA-SEG-03*`), el sistema sondea su correo, aplica las whitelists de remitentes (`REF-03`) y agrega las reservas de los mensajes de viaje a su itinerario (`REF-02`).

## Paso 3. Elegir los elementos a refinar


| Elemento                                                                  | Por qué este                                                                                                                                                                                                                                                                                                                                                                   | Movimiento  |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------- |
| Adaptador de aerolíneas, Adaptador de hoteles y Adaptador de arrendadoras | Son la Capa Anti-Corrupción de cada API y el lugar donde se suma un conector nuevo sin tocar el Core (`QA-INT-01`). Hoy solo hacen llamadas síncronas desde el Orquestador de viajes: no escuchan actualizaciones del proveedor (`QA-PER-01`). La iteración define cómo se agrega un adaptador y cómo reciben novedades.                                                         | Refinar     |
| Orquestador de viajes                                                     | Agrupa las reservas por viaje (`REF-01`) y es quien recibe lo que entra de afuera. Hoy el modelo de reserva no distingue tipos de medio de transporte, y esa distinción es lo que mide `QA-EVO-01`. La iteración lo descompone para exponer el modelo de reservas y el punto donde las novedades y las reservas del correo se incorporan al viaje (`QA-PER-01`, `REF-02`).        | Descomponer |
| Capa de integración (elementos nuevos)                                    | La vista de componentes de la iteración 1 no tiene un módulo asíncrono de ingesta, un adaptador de correo, un adaptador del proveedor de anuncios (Booking) ni un servicio de notificaciones. Son los elementos que cubren `QA-PER-01`, `REF-02`, `REF-03`, `QA-SEG-03*` y `QA-INT-02`, y se instancian en el paso 5 dentro del refinamiento de los adaptadores y del orquestador. | Instanciar  |


Se refinan esos elementos de [vistas/C&C_VIEW_IT1.svg](vistas/C&C_VIEW_IT1.svg). Cliente web, Cliente móvil, Caché de borde (CDN), API Gateway y Balanceador de Carga encaminan y no cambian. Módulo de registro y Base primaria y Base pasiva quedan para `QA-ESC-01` y los datos de usuario de la iteración 4. API Proveedor 2 (SOAP), API de hoteles, API de arrendadoras y el correo están fuera de la frontera de Trotamundos.
