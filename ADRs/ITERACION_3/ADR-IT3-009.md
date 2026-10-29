# Performance: Novedades de Booking por aviso (push) a un listener

* **Estado:** aceptado
* **Fecha:** 2026-10-28
* **Decisores:** Ramiro Rossi

## Contexto y Declaración del Problema
Las actualizaciones de las APIs de proveedores (Booking) deben reflejarse en la sección "Novedades". Hay que decidir cómo se entera Trotamundos de una actualización: si el proveedor avisa, o si Trotamundos consulta periódicamente.

## Impulsores de la Decisión (Decision Drivers)
* `QA-PER-01`: la app refleja la novedad en 5 minutos como máximo desde que el listener detecta la actualización.
* `QA-PER-02`: la consulta periódica a miles de recursos no debe competir con la cotización.
* Booking es un tercero: no controlamos su API.

## Opciones Consideradas
* Opción 1: Push: Booking notifica a un listener (Adaptador de anuncios) de Trotamundos.
* Opción 2: Polling periódico de Trotamundos contra la API de Booking.
* Opción 3: Híbrido: push más polling de reconciliación.

## Resultado de la Decisión
Opción elegida: **"Opción 1: push a un listener"**, porque el aviso llega al momento y sin consultas vacías, y la medida de `QA-PER-01` corre desde que el listener detecta la actualización. El Adaptador de anuncios, que es ese listener, la traduce al modelo interno y la deja en la cola de novedades con identificador único ([ADR-IT3-001](ADR-IT3-001.md)). Usa Ping/Echo contra Booking, ya decidido en la iteración 1.

### Consecuencias Positivas (Beneficios)
* Mínima latencia de detección y sin tráfico de consulta inútil.
* El listener solo habla con el broker, así que el pico no llega al Orquestador.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Se depende de que Booking soporte el aviso y lo entregue de forma confiable; un aviso perdido no se detecta (no hay polling de reconciliación).
* Hay un endpoint público que exponer, autenticar y proteger.
* La medida de 5 minutos solo cubre desde la detección: el retraso previo del proveedor queda fuera.
* Si el listener no está disponible cuando Booking avisa, la novedad se pierde, salvo que Booking reintente.
