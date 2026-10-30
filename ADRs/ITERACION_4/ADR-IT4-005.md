# Seguridad: Limitación de tasa en el API Gateway y aislamiento del endpoint de recuperación (Detect service denial + Limit event response)

* **Estado:** aceptado
* **Fecha:** 2026-10-29
* **Decisores:** Santiago Otaño

## Contexto y Declaración del Problema
`QA-SEG-01` describe una ráfaga maliciosa de 50 solicitudes simultáneas de recuperación de contraseña contra un mismo endpoint. Si todas llegan al Servicio de autenticación, cada una escribe en la base y dispara un correo, satura el servicio y arrastra al inicio de sesión de los usuarios legítimos. El escenario pide detectar el patrón, denegar lo malintencionado, no saturar el servicio y mantener operativa la plataforma para el resto.

## Impulsores de la Decisión (Decision Drivers)
* `QA-SEG-01`: denegar las solicitudes malintencionadas, prevenir la saturación y mantener activo el servicio de login para los usuarios legítimos.
* `QA-ESC-01`: el límite no puede rechazar el pico legítimo de altas del lanzamiento.
* `CON-01`: el mismo control vale para web y móvil, que entran por el API Gateway ([ADR-008](../ITERACION_1/ADR-008.md)).

## Opciones Consideradas
* Opción 1: Limitación de tasa en el API Gateway, por endpoint y por origen, con un cupo propio para el endpoint de recuperación, y un grupo de recursos separado para la recuperación en el Servicio de autenticación. Al superar el cupo, el Gateway responde "demasiados pedidos" sin pasar el pedido al servicio y deja el evento registrado para el aviso al titular ([ADR-IT4-006](ADR-IT4-006.md)).
* Opción 2: Limitar solo dentro del Servicio de autenticación.
* Opción 3: Exigir un desafío (CAPTCHA) en cada pedido de recuperación.
* Opción 4: No limitar y confiar en la capacidad elástica de los nodos.

## Resultado de la Decisión
Opción elegida: **"Opción 1: limitación de tasa en el Gateway y aislamiento del endpoint de recuperación"**, porque corta la ráfaga antes de que consuma al servicio (denegar cuesta lo que cuesta contar) y detecta el patrón por endpoint y por origen aunque apunte a cuentas distintas. El cupo y los recursos propios de la recuperación impiden que la ráfaga alcance al login. El límite por cuenta, donde se conoce la cuenta destino, lo resuelve [ADR-IT4-006](ADR-IT4-006.md). La opción 2 llega tarde: la ráfaga ya consumió el servicio. La opción 3 agrega fricción a todos y no frena a un atacante que resuelve desafíos; puede sumarse luego como segunda línea. La opción 4 paga capacidad para atender al atacante y no evita el envío de correos.

### Consecuencias Positivas (Beneficios)
* El servicio de autenticación no ve la ráfaga: solo ve lo que el Gateway deja pasar.
* La recuperación y el login tienen cupos y recursos separados: saturar uno no degrada al otro.
* El mismo control protege a la web y al móvil.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Los umbrales y las ventanas son parámetros que hay que calibrar. Uno bajo deniega a usuarios legítimos, uno alto deja pasar la ráfaga.
* Un origen compartido (una red corporativa o la de un aeropuerto) puede dejar a usuarios legítimos del mismo origen sin recuperación.
* Un ataque distribuido en muchos orígenes hacia muchas cuentas no lo frena este límite solo: depende del límite por cuenta.
* Las copias del Gateway comparten contadores: se acepta una consistencia aproximada entre ellas.
* El API Gateway sigue siendo un punto a dimensionar y a hacer redundante ([ADR-008](../ITERACION_1/ADR-008.md)).
* El alta no tiene un tope por total: se limita por origen con un umbral alto, para no rechazar el pico legítimo de `QA-ESC-01`.
