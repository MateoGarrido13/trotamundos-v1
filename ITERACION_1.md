# Trotamundos — iteración 1


| Campo                       | Valor                                                                                                  |
| --------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Ronda**                   | 1                                                                                                      |
| **Arranque**                | Greenfield. Se refina el sistema mediante la descomposición que fija la topología del Core.            |
| **Qué toma esta iteración** | La topología del Core para la consulta del viajero, con la escala, los tiempos de respuesta y la frontera de integración del goal. |


El paso 1 de la ronda está en [README.md](README.md).

## Paso 2. Establecer el goal


| Id           | En el goal o afuera                                                                              |
| ------------ | ------------------------------------------------------------------------------------------------ |
| `QA-PER-02`  | En el goal. Nueva cotización desde la web, en 800 ms.                                            |
| `QA-PER-03`  | En el goal. El usuario abre la aplicación móvil y el primer contenido aparece en menos de 1,4 s. |
| `QA-ESC-01`  | En el goal. Registro masivo de usuarios, con la escala y los picos del escenario.                |
| `QA-INT-01`  | En el goal. Integrar la API propietaria de una cadena hotelera nueva en un único módulo de frontera, en menos de 2 semanas, sin alterar el motor de viajes ni la base principal. |
| `QA-PER-01`  | Afuera. Actualización de una API externa.                                                        |
| `QA-PER-04*` | Afuera. Consulta de tendencias, destinos y cancelaciones.                                        |
| `QA-DIS-01`  | Afuera. Caída de un nodo de cotización.                                                          |
| `QA-INT-02`  | Afuera. Incorporar Instagram como canal de propuestas e itinerarios.                             |
| `QA-SEG-01`  | Afuera. Ráfaga de recuperación de contraseña.                                                    |
| `QA-SEG-02`  | Afuera. Registrar una actividad en el itinerario compartido.                                     |
| `QA-SEG-03*` | Afuera. El titular autoriza la lectura de su correo.                                             |
| `QA-EVO-01`  | Afuera. Integrar un medio de transporte que el panel todavía no agrupa.                          |
| `QA-USA-01`  | Afuera. El viajero consulta su viaje en el móvil, con una capacidad nativa como el GPS.          |


**Goal.** El objetivo de esta iteración es definir la topología global del Core de la plataforma Trotamundos y centralizar las consultas que el viajero hace, desde la web o desde el móvil. Una cotización nueva responde en 800 ms desde la web (`QA-PER-02`). Al abrir la aplicación móvil, el primer contenido aparece en menos de 1,4 s (`QA-PER-03`). El Core atiende el registro de `QA-ESC-01`: 100.000 usuarios nuevos por día, con confirmación en menos de 2 segundos. Cuando el negocio instruye integrar la API propietaria de una cadena hotelera nueva (`QA-INT-01`), el cambio ocurre en un único módulo de frontera, en menos de 2 semanas, y el motor de viajes y la base principal siguen iguales.



## Paso 3. Elegir los elementos a refinar


| Elemento   | Por qué este                                                                                                                                                                                           | Movimiento  |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------- |
| El sistema | Reúne la consulta del viajero en la web y en el móvil (`QA-PER-02`, `QA-PER-03`), el registro masivo de `QA-ESC-01` y la frontera por la que entra la API de una cadena hotelera nueva (`QA-INT-01`). La iteración establece la topología de ese Core como descomposición del sistema. | Descomponer |


El sistema se descompone para fijar la topología del Core: el punto en el que el viajero consulta sus reservas agrupadas por viaje, desde la web y desde el móvil.