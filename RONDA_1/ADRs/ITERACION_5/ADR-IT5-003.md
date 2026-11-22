# Usabilidad: Cálculo local de proximidad y ruta con GPS nativo en el Cliente móvil sobre `Reserva.lugar`, con carga diferida y degradación sin coordenadas

* **Estado:** aceptado
* **Fecha:** 2026-11-17
* **Decisores:** Ramiro Rossi

## Contexto y Declaración del Problema
`QA-USA-01` plantea que el viajero consulta su viaje en el dispositivo móvil durante el viaje y el panel muestra una interfaz que aprovecha capacidades nativas como el GPS, buscando una satisfacción mayor a 3,5 estrellas en promedio. En la iteración 4 el contrato `Reserva` incorporó el atributo `lugar` (nombre, destino y coordenadas opcionales, [ADR-IT4-009](../ITERACION_4/ADR-IT4-009.md)), dejando pendiente decidir cómo usa el Cliente móvil la posición del dispositivo sin comprometer el primer despliegue de contenido en menos de 1,4 segundos sobre red 3G de aeropuerto (`QA-PER-03`, [ADR-IT2-001](../ITERACION_2/ADR-IT2-001.md)) ni enviar de forma continua la ubicación del usuario al backend.

## Impulsores de la Decisión (Decision Drivers)
* `QA-USA-01`: aprovechar la capacidad nativa del GPS del dispositivo móvil al consultar el viaje durante el viaje.
* `QA-PER-03`: mantener el First Contentful Paint (FCP) del login en menos de 1,4 segundos en el 90 % de las sesiones bajo red móvil 3G.
* Privacidad del viajero: no transmitir ni almacenar en el servidor el rastro continuo de ubicación del dispositivo si puede resolverse localmente.
* Tolerar reservas sin coordenadas o usuarios que deniegan el permiso de ubicación ([ADR-IT4-009](../ITERACION_4/ADR-IT4-009.md)).

## Opciones Consideradas
* Opción 1: Resolución local en el Cliente móvil con carga diferida posterior al login. La obtención de la posición GPS nativa no se ejecuta en la pantalla de login (preservando el FCP < 1,4 s de `QA-PER-03`), sino recién cuando el viajero abre su viaje activo. Con permiso del sistema operativo, el Cliente móvil lee las coordenadas actuales del GPS y las compara en el propio dispositivo contra el `lugar` de cada reserva del itinerario: muestra la distancia y el enlace de navegación nativa a cada reserva con coordenadas y destaca la reserva próxima más cercana. Si el usuario deniega el permiso de GPS o una reserva no tiene coordenadas en `lugar`, la vista degrada mostrando el itinerario ordenado cronológicamente con el nombre y destino textuales del lugar, sin distancia ni ruta.
* Opción 2: Enviar periódicamente las coordenadas GPS del móvil al Orquestador de viajes para que el servidor calcule las distancias y devuelva el itinerario reordenado ([ADR-IT5-005](ADR-IT5-005.md)).
* Opción 3: Bloquear la vista del viaje en el móvil si el usuario no otorga permiso de GPS o si una reserva carece de coordenadas.

## Resultado de la Decisión
Opción elegida: **"Opción 1: cálculo local de proximidad con GPS en el Cliente móvil, diferido tras el login y con degradación elegante"**, porque aprovecha la capacidad nativa del dispositivo exactamente donde aporta valor al viajero en tránsito (ver a qué distancia está de su hotel, aeropuerto, estación o actividad y abrir la ruta en un toque) sin sumar ni un byte ni un milisegundo al arranque de 1,4 s de `QA-PER-03` ni una llamada adicional al Orquestador. Además, las coordenadas del usuario nunca salen de su teléfono. La opción 2 gasta batería y red 3G enviando posición al servidor sin necesidad ([ADR-IT5-005](ADR-IT5-005.md)). La opción 3 penaliza la usabilidad cuando el viajero está sin señal GPS bajo techo o cargó una reserva manual sin coordenadas.

### Consecuencias Positivas (Beneficios)
* El FCP del login (< 1,4 s en 3G, `QA-PER-03`) queda intacto porque el módulo de geolocalización recién se invoca en la vista del viaje.
* El cálculo de distancia entre el GPS del dispositivo y `Reserva.lugar` ocurre en memoria en el móvil, incluso con conectividad intermitente una vez cargado el itinerario.
* Privacidad por diseño: la ubicación en tiempo real del viajero no se transmite ni se guarda en ninguna base de Trotamundos.
* Degradación limpia cuando faltan coordenadas en `Reserva.lugar` o cuando el usuario rechaza el permiso de ubicación.

### Consecuencias Negativas (Trade-offs / Riesgos)
* La precisión de la distancia en línea recta o el lanzamiento del mapa nativo dependen del hardware GPS del dispositivo y de los permisos del sistema operativo.
* La medida de `QA-USA-01` en el listado (> 3,5 estrellas en tiendas) es una métrica de percepción en producción; en diseño y en el prototipo se verifica mediante la presencia funcional del cálculo nativo de GPS sobre `Reserva.lugar` y su degradación sin error cuando faltan coordenadas o permiso.
