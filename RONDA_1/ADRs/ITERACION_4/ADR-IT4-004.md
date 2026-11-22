# Seguridad: Sesión con token firmado y de vida corta, validado en el API Gateway

* **Estado:** aceptado
* **Fecha:** 2026-10-29
* **Decisores:** Ramiro Rossi

## Contexto y Declaración del Problema
En la iteración 1 el API Gateway valida la sesión llamando al módulo de registro en cada pedido. Con las cuentas particionadas por región ([ADR-IT4-001](ADR-IT4-001.md)), un viajero cuya cuenta vive en una región y que está en otro continente forzaría una llamada síncrona entre regiones en cada pedido, y la caída de una región impediría usar el sistema aun para cotizar. Además, el alta debe permitir iniciar sesión inmediatamente (`QA-ESC-01`), y el resto del sistema necesita saber quién es el actor (`QA-SEG-02`). Hay que decidir cómo se establece y se valida la sesión.

## Impulsores de la Decisión (Decision Drivers)
* `QA-ESC-01`: los nuevos usuarios inician sesión inmediatamente, sin dependencia entre regiones.
* `QA-PER-02`: la cotización conserva sus 800 ms; no se suma una llamada por pedido.
* `QA-DIS-01`: no agregar una dependencia síncrona nueva entre el borde y la región de la cuenta.
* `QA-SEG-02`: el Orquestador necesita la identidad verificada del actor.
* `CON-01`: el mismo mecanismo sirve a la web y al móvil.

## Opciones Consideradas
* Opción 1: Token de acceso firmado y de vida corta, con el identificador de cuenta y su región. Un token de renovación, guardado como hash en la Base de cuentas y revocable. El API Gateway valida la firma con las claves públicas de las regiones, sin llamar a ninguna (Authenticate actors en el borde).
* Opción 2: Sesión en servidor, consultada en cada pedido al Módulo de registro de la región de la cuenta (situación de la iteración 1).
* Opción 3: Sesión replicada en todas las regiones.

## Resultado de la Decisión
Opción elegida: **"Opción 1: token firmado de vida corta, validado en el API Gateway"**, porque la validación pasa a ser local: no suma ninguna llamada de red a la cotización, no depende de que la región de la cuenta esté disponible mientras el token vive y permite que el alta devuelva la sesión inicial en la misma respuesta. Cerrar sesión o completar una recuperación de contraseña revocan los tokens de renovación. Los de acceso vencen solos. El Gateway autentica (quién es) y el Orquestador autoriza (qué puede hacer sobre ese itinerario, [ADR-IT4-007](ADR-IT4-007.md)). La opción 2 es la que hoy obligaría a cruzar regiones. La opción 3 reintroduce una replicación global con consistencia que no se necesita.

### Consecuencias Positivas (Beneficios)
* Validar la sesión no requiere un salto de red.
* El inicio de sesión inmediato tras el alta no depende de otras regiones.
* El sistema sigue atendiendo a los usuarios con token vigente aunque la región de su cuenta esté degradada.
* La identidad llega verificada al Core, sin que este consulte cuentas.

### Consecuencias Negativas (Trade-offs / Riesgos)
* La revocación no es inmediata para el token de acceso: vale hasta su vencimiento. La vida del token es un parámetro que balancea esa ventana contra la frecuencia de renovación.
* Hay que distribuir y rotar las claves públicas de las regiones entre todos los API Gateway.
* Un token robado sirve hasta que vence.
* Los tokens de renovación son datos sensibles en la Base de cuentas.
* Reemplaza lo decidido en la iteración 1: el módulo de registro ya no valida cada pedido.
