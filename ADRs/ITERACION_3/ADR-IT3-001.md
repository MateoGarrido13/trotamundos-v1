# Intermediario asíncrono: un broker con tres colas (novedades, correo y notificaciones)

* **Estado:** aceptado
* **Fecha:** 2026-10-28
* **Decisores:** Tomas Fontana

## Contexto y Declaración del Problema
La iteración 3 hace entrar al sistema información que viene de afuera: novedades de Booking, mensajes del correo del titular y pedidos de envío de propuestas por distintos canales. Hoy el Orquestador de viajes solo atiende llamadas síncronas con un usuario esperando (cotización, 800 ms). Si la ingesta y los envíos se resolvieran contra el Orquestador de forma directa, un pico (por ejemplo el de las 8 am) compartiría recursos con la cotización y bloquearía a los productores. Hay que decidir cómo se desacoplan quienes producen información de quienes la consumen.

## Impulsores de la Decisión (Decision Drivers)
* `QA-PER-01`: la app refleja la novedad en "Novedades" en 5 minutos como máximo desde que el listener detecta la actualización.
* `QA-PER-02`: la cotización sigue respondiendo en 800 ms; la ingesta no puede degradarla.
* `REF-02`: sondeo y escaneo del correo del titular.
* `QA-INT-02`: Instagram se suma como canal con 1 componente nuevo y 0 modificaciones en los consumidores existentes.
* `QA-DIS-01` (heredado de la iteración 2): no introducir un punto único de falla nuevo.

## Opciones Consideradas
* Opción 1: Use an intermediary: un único broker con tres colas separadas (novedades, correo, notificaciones), hecho redundante.
* Opción 2: Llamadas síncronas directas de los productores al Orquestador de viajes.
* Opción 3: Un broker independiente por flujo (tres brokers).
* Opción 4: Cola sobre la base de datos (tabla de eventos en la Base primaria, con consulta periódica).

## Resultado de la Decisión
Opción elegida: **"Opción 1: un único broker con tres colas separadas, redundante"**, porque desacopla en el tiempo a productores y consumidores sin bloquear al Orquestador, absorbe el pico de las 8 am sin tocar la ruta de 800 ms de `QA-PER-02` y permite sumar consumidores o canales nuevos (`QA-INT-02`) sin modificar a los existentes. Las colas separadas evitan que un flujo se mezcle con otro. La redundancia se logra reutilizando Redundant spare y Reconfiguration (iteraciones 1 y 2): si cae el nodo principal, el de respaldo toma las colas.

### Consecuencias Positivas (Beneficios)
* La ingesta y los envíos no bloquean al Orquestador de viajes; la cotización no usa el broker y queda intacta.
* El pico se absorbe en la cola en lugar de trasladarse a los consumidores.
* Un canal o un consumidor nuevo se conecta al broker sin cambios en los que ya existen.
* Un solo componente de mensajería para operar, monitorear y asegurar, en vez de tres.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Suma un componente de infraestructura y latencia al recorrido; esa latencia consume parte de los 5 minutos de `QA-PER-01`.
* La consistencia pasa a ser eventual: el cliente puede ver la novedad unos instantes después de su generación.
* Con un único broker, un nodo caído es un SPOF hasta que Reconfiguration complete el traspaso; ese traspaso no es inmediato y los mensajes en vuelo dependen de Retry con identificador único ([ADR-IT3-003](ADR-IT3-003.md)).
* Las tres colas comparten el mismo broker: un flujo saturado puede afectar a los otros si comparten recursos. Se mitiga acotando cada cola ([ADR-IT3-002](ADR-IT3-002.md)).
* Aumenta la complejidad operativa y de pruebas (productores, consumidores, orden y duplicados).
