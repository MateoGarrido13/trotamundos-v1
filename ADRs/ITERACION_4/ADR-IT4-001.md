# Escalabilidad: Partición geográfica de las cuentas por región de origen

* **Estado:** aceptado
* **Fecha:** 2026-10-29
* **Decisores:** Tomas Fontana

## Contexto y Declaración del Problema
`QA-ESC-01` pide un registro sostenido de 100.000 usuarios nuevos por día, con viajeros ubicados en tres continentes, y una confirmación en el cliente en menos de 2 segundos "independientemente del continente de origen". En la iteración 1 las cuentas, los perfiles y las sesiones viven en una única Base primaria, junto con los viajes, y la iteración 2 confirma cada escritura con un commit en dos fases contra la Base pasiva ([ADR-IT2-004](../ITERACION_2/ADR-IT2-004.md)). Ese ADR deja escrito que el commit en dos fases no escala a multirregión sin penalidad de latencia. Con ese esquema, un alta desde otro continente cruzaría el océano hasta el único par de bases, y todas las altas del mundo competirían por el mismo punto de escritura. Hay que decidir dónde viven los datos de las cuentas y dónde se procesa el alta.

## Impulsores de la Decisión (Decision Drivers)
* `QA-ESC-01`: el 100 % de los registros se procesa sin rechazos por saturación ni timeout, y la confirmación demora menos de 2 segundos desde cualquiera de los tres continentes.
* `QA-DIS-01` (heredado de la iteración 2): dentro de cada par de bases se mantiene la consistencia por sobre la latencia y el servicio acumula menos de 5 minutos de inactividad al mes.
* `CON-01`: la web y el móvil comparten el mismo camino de alta.
* El alta no puede degradar el servicio de los usuarios existentes (respuesta de `QA-ESC-01`).

## Opciones Consideradas
* Opción 1: Partición geográfica. Una región por continente de origen. Cada región tiene su Módulo de registro y autenticación y su Base de cuentas (primaria y pasiva, con commit en dos fases dentro de la región). La cuenta vive en la región donde se registra.
* Opción 2: Mantener un único par de bases y servir todas las altas desde un solo sitio (situación de la iteración 1).
* Opción 3: Un único punto de escritura central, con réplicas de lectura en cada continente.
* Opción 4: Una base distribuida entre regiones, con confirmación síncrona en todas ellas ([ADR-IT4-015](ADR-IT4-015.md)).

## Resultado de la Decisión
Opción elegida: **"Opción 1: partición geográfica de las cuentas por región de origen"**, porque saca del camino crítico del alta todo cruce síncrono entre continentes. El viajero escribe en su región, el commit en dos fases sigue siendo el de la iteración 2 pero entre dos nodos de la misma región, y la carga de altas se reparte entre tres pares de bases en lugar de caer en uno. Las opciones 2 y 3 dejan a los viajeros de otros continentes pagando el viaje de ida y vuelta en la confirmación, y la 3 mantiene un único punto de escritura. El identificador de cuenta se genera en la región, con el código de región como prefijo, sin coordinación entre regiones. Ese identificador viaja en el token de sesión ([ADR-IT4-004](ADR-IT4-004.md)) para que el resto del sistema sepa dónde vive la cuenta.

### Consecuencias Positivas (Beneficios)
* La confirmación del alta no depende de ningún enlace entre continentes.
* La capacidad de escritura de cuentas se multiplica por construcción: tres pares de bases en lugar de uno, sin tocar la Base de viajes.
* Se reutilizan Redundant spare, Transactions y Reconfiguration ([ADR-IT2-004](../ITERACION_2/ADR-IT2-004.md), [ADR-IT2-005](../ITERACION_2/ADR-IT2-005.md)) sin cambiar de mecanismo.
* Una región lenta o degradada solo afecta a las cuentas de esa región.

### Consecuencias Negativas (Trade-offs / Riesgos)
* La cuenta queda atada a su región: un viajero que está en otro continente se autentica contra su región de origen, con la latencia de ese enlace. Ese tramo no está en el camino del alta.
* Hay que operar y monitorear tres pares de bases y tres despliegues en lugar de uno.
* La unicidad del correo entre regiones deja de ser gratuita. La resuelve [ADR-IT4-003](ADR-IT4-003.md) con consistencia eventual.
* La caída de una región completa (no la de un nodo, que es lo que cubre `QA-DIS-01`) deja sin servicio a sus cuentas hasta restaurarla. La recuperación ante desastre queda fuera de esta ronda.
* Mover una cuenta de una región a otra, por ejemplo por un cambio de residencia, no está resuelto.
* La cantidad de regiones y su ubicación son decisiones de despliegue: los drivers no las fijan.
