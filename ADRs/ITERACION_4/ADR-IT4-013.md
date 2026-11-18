# Seguridad: Bloqueo de cuenta tras N intentos de recuperación o inicio de sesión

* **Estado:** rechazado
* **Fecha:** 2026-10-29
* **Decisores:** Ramiro Rossi

## Contexto y Declaración del Problema
Frente a la ráfaga maliciosa de 50 solicitudes simultáneas de recuperación de contraseña de `QA-SEG-01`, se evaluó la táctica clásica de bloquear la cuenta afectada tras superar un umbral de intentos consecutivos en una ventana corta.

## Impulsores de la Decisión (Decision Drivers)
* `QA-SEG-01`: el 100 % de los accesos no autorizados son rechazados **y la disponibilidad del servicio de login para usuarios legítimos se mantiene activa**.
* Evitar que un mecanismo defensivo permita a un atacante externo denegar el servicio al propietario legítimo de la cuenta.

## Opciones Consideradas
* Opción 1: Limitación de tasa por endpoint y origen en el API Gateway con recursos separados para recuperación ([ADR-IT4-005](ADR-IT4-005.md)) más un único pedido de recuperación vigente por cuenta decidido de forma atómica y respuesta uniforme ([ADR-IT4-006](ADR-IT4-006.md)).
* Opción 2: Bloquear la cuenta destino tras N solicitudes de recuperación o intentos fallidos.

## Resultado de la Decisión
Opción elegida: **"Opción 1: limitación de tasa, aislamiento de recursos y único pedido vigente por cuenta, sin bloqueo de la cuenta"**, y se rechaza el bloqueo de cuenta tras N intentos, porque la dirección de correo electrónico no es un secreto: cualquier atacante que la conozca podría disparar N pedidos de recuperación a propósito para dejar bloqueado al viajero legítimo justo durante su viaje. Eso convierte la defensa en un vector de denegación de servicio contra el titular y contradice directamente la medida de respuesta de `QA-SEG-01` ("la disponibilidad del servicio de login para usuarios legítimos se mantiene activo").

### Consecuencias Positivas (Beneficios)
* Un atacante que envía una ráfaga contra el correo de una víctima no logra impedir que el titular legítimo inicie sesión con su contraseña actual.
* El abuso se contiene por cupo de origen y por la actualización atómica que admite un solo token de recuperación vigente.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Al no bloquearse la cuenta, el endpoint de login debe sostener su propia limitación de tasa por origen y hashing costoso de credenciales para mitigar intentos de adivinación de contraseña.
* Condición de reapertura: solo como suspensión temporal del factor de recuperación (nunca del login con credencial válida), que ya queda implícita al admitir un único pedido vigente hasta su vencimiento ([ADR-IT4-006](ADR-IT4-006.md)).
