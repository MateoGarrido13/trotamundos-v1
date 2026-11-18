# Usabilidad: Seguimiento continuo de la posición GPS del viajero en el servidor

* **Estado:** rechazado
* **Fecha:** 2026-11-17
* **Decisores:** Tomas Fontana

## Contexto y Declaración del Problema
Al diseñar cómo aprovecha el Cliente móvil el GPS del dispositivo (`QA-USA-01`), se evaluó que la aplicación móvil envíe periódicamente en segundo plano sus coordenadas al Orquestador de viajes para que el backend calcule la cercanía a cada reserva y emita notificaciones o reordene la vista desde el servidor.

## Impulsores de la Decisión (Decision Drivers)
* `QA-USA-01`: el viajero consulta su viaje en el móvil aprovechando capacidades nativas como el GPS.
* `QA-PER-03` y `QA-PER-02`: no saturar conexiones móviles lentas (3G en aeropuertos) ni sumar tráfico constante de telemetría de ubicación sobre el API Gateway y el Orquestador de viajes.
* Privacidad: minimizar la recolección de datos personales sensibles que ningún requerimiento funcional pide.

## Opciones Consideradas
* Opción 1: Leer el GPS en el Cliente móvil cuando el viajero consulta su viaje y calcular localmente en el dispositivo la distancia y ruta hacia `Reserva.lugar` ([ADR-IT5-003](ADR-IT5-003.md)).
* Opción 2: Enviar de forma continua la ubicación GPS del dispositivo al backend para calcular proximidad en el servidor.

## Resultado de la Decisión
Opción elegida: **"Opción 1: uso local del GPS en el Cliente móvil"**, y se rechaza el seguimiento continuo en el servidor, porque el estímulo de `QA-USA-01` es que "el viajero consulta su viaje en el móvil", y el cliente ya recibe las coordenadas de cada reserva dentro del atributo `lugar` ([ADR-IT4-009](../ITERACION_4/ADR-IT4-009.md)). Con ambos datos en el teléfono, enviar la ubicación al servidor para restar dos coordenadas es innecesario, consume batería y datos en itinerancia (roaming/3G), multiplica las peticiones sobre el API Gateway para 2 millones de usuarios activos semanales y obliga a custodiar el historial de movimientos físicos de cada viajero.

### Consecuencias Positivas (Beneficios)
* Cero tráfico de telemetría GPS hacia el API Gateway y el Orquestador.
* Menor consumo de batería y de red móvil durante el viaje.
* El servidor nunca almacena la ubicación en tiempo real del viajero.

### Consecuencias Negativas (Trade-offs / Riesgos)
* El sistema no dispara alertas proactivas en segundo plano basadas en geocercas desde el servidor.
* Condición de reapertura: si un requerimiento futuro pidiera alertas automáticas en segundo plano por cercanía geográfica sin que el viajero abra la aplicación.
