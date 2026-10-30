# Seguridad: Recuperación de contraseña con token de un solo uso, respuesta uniforme y aviso al titular

* **Estado:** aceptado
* **Fecha:** 2026-10-29
* **Decisores:** Tomas Fontana

## Contexto y Declaración del Problema
Aun con la limitación de tasa del Gateway ([ADR-IT4-005](ADR-IT4-005.md)), lo que pasa por el endpoint de recuperación no debe poder usarse para tomar una cuenta, averiguar qué correos están registrados ni inundar de correos a un titular. `QA-SEG-01` pide además notificar al propietario legítimo de la cuenta sobre la actividad sospechosa y que el 100 % de los accesos no autorizados sea rechazado. Hay que decidir cómo funciona la recuperación dentro del Servicio de autenticación.

## Impulsores de la Decisión (Decision Drivers)
* `QA-SEG-01`: rechazar el 100 % de los accesos no autorizados, notificar al propietario legítimo y mantener el login disponible.
* `QA-INT-02` (heredado de la iteración 3): los envíos salen por la cola de notificaciones y los canales `ICanal`, de forma asíncrona.
* `QA-ESC-01`: el mecanismo vive en la región de la cuenta y no agrega cruces entre regiones.

## Opciones Consideradas
* Opción 1: En el Servicio de autenticación: (a) la respuesta es idéntica exista o no la cuenta; (b) hay un solo pedido de recuperación vigente por cuenta, decidido con una actualización atómica en la Base de cuentas, de modo que 50 pedidos simultáneos dejan pasar uno solo; (c) el token es aleatorio, de un solo uso y con vencimiento, se guarda como hash y se envía solo al correo registrado, nunca en la respuesta; (d) completar la recuperación revoca los tokens de renovación; (e) al superarse el límite por cuenta se publica un aviso de actividad sospechosa en la cola de notificaciones, por el canal Email, un aviso por ventana.
* Opción 2: Preguntas de seguridad como mecanismo de recuperación.
* Opción 3: Enviar un correo por cada pedido recibido.

## Resultado de la Decisión
Opción elegida: **"Opción 1: token de un solo uso, respuesta uniforme, un pedido vigente por cuenta y aviso al titular"**, porque el rechazo del 100 % de los accesos no autorizados queda garantizado por construcción: nadie obtiene el token sin acceso al buzón del titular, y la respuesta no distingue cuentas existentes de inexistentes. La actualización atómica resuelve la simultaneidad, que es el centro del escenario: sin ella, 50 pedidos concurrentes podrían pasar la verificación a la vez. El aviso al titular reutiliza la cola de notificaciones y el canal Email de la iteración 3 ([ADR-IT3-001](../ITERACION_3/ADR-IT3-001.md), [ADR-IT3-004](../ITERACION_3/ADR-IT3-004.md)). La opción 2 expone respuestas que suelen averiguarse. La opción 3 convierte la ráfaga en una inundación de correos contra el titular.

### Consecuencias Positivas (Beneficios)
* Un atacante no obtiene acceso ni información sobre qué cuentas existen.
* La ráfaga produce, como mucho, un correo de recuperación y un aviso por ventana.
* Se reutiliza la ruta asíncrona de la iteración 3, con Retry e identificador único ([ADR-IT3-003](../ITERACION_3/ADR-IT3-003.md)).

### Consecuencias Negativas (Trade-offs / Riesgos)
* `ICanal.enviar` pasa a transportar también avisos del sistema: el parámetro `propuesta` de [ADR-IT3-004](../ITERACION_3/ADR-IT3-004.md) se entiende como mensaje. Es un cambio a un contrato crítico.
* El correo de recuperación sale por el Broker, que está en el sitio del Core: si no está disponible, el pedido espera con Retry y la recuperación se demora. El inicio de sesión no depende de esa ruta.
* Si el titular no tiene acceso a su correo, no hay recuperación: otros factores no se definen en esta ronda.
* Un atacante puede lograr que el titular reciba un aviso por ventana: una molestia acotada, no una inundación.
* La respuesta uniforme impide mostrar un mensaje preciso al usuario legítimo que escribió mal su correo.
* La actualización atómica por pedido admitido paga el commit en dos fases local. Para la recuperación no hay medida de tiempo en el escenario.
* El vencimiento del token, el tamaño de la ventana y el cupo por cuenta son parámetros.
