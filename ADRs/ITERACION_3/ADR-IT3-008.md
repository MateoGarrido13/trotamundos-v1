# Seguridad: Whitelist de remitentes con cola de "Mensajes en revisión"

* **Estado:** aceptado
* **Fecha:** 2026-10-28
* **Decisores:** Mateo Garrido

## Contexto y Declaración del Problema
`REF-03` pide filtrar y armar whitelists de remitentes seguros. Esto entra en tensión con `QA-SEG-03*`, cuya medida es el 100 % de las reservas de usuarios autorizados: un mensaje legítimo de un remitente fuera de la whitelist, si se descarta, es una reserva perdida sin que el titular lo sepa. Hay que decidir qué se hace con esos mensajes.

## Impulsores de la Decisión (Decision Drivers)
* `REF-03`: whitelists de remitentes seguros.
* `QA-SEG-03*`: no perder reservas legítimas de usuarios autorizados y mantener el acceso seguro.
* El titular decide en quién confía.

## Opciones Consideradas
* Opción 1: Los mensajes fuera de la whitelist quedan en "Mensajes en revisión"; el titular aprueba al remitente (lo suma a la whitelist) y la reserva entra al itinerario.
* Opción 2: Descartar los mensajes de remitentes fuera de la whitelist.
* Opción 3: Aceptar todo y filtrar solo por lista negra de remitentes.

## Resultado de la Decisión
Opción elegida: **"Opción 1: cola de Mensajes en revisión con aprobación del titular"**, porque cumple la whitelist sin perder reservas legítimas en silencio. El Filtro de remitentes ubica la whitelist y los mensajes en revisión entre el Parseo aislado y la ingesta; los datos los guarda el Orquestador de viajes. Lo que se descarta es solo el contenido que no pasa la validación del parseo ([ADR-IT3-007](ADR-IT3-007.md)).

### Consecuencias Positivas (Beneficios)
* El 100 % de `QA-SEG-03*` se cumple para usuarios cuyos remitentes son seguros o fueron aprobados.
* El titular ve y decide sobre lo que quedó fuera.
* Una aprobación enriquece la whitelist para los mensajes siguientes.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Carga de usuario: pantalla nueva en web y móvil y decisiones manuales.
* Se almacenan reservas normalizadas de remitentes no verificados, con costo de almacenamiento, retención a definir y riesgo de remitentes falsificados si el titular aprueba sin cuidado.
* La cola de revisión puede acumularse sin límite si el titular no la atiende.
* Una reserva que espera aprobación no está en el itinerario: el viajero puede perder información a tiempo.
