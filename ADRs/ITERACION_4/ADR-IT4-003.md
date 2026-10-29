# Escalabilidad: Enrutamiento por región y unicidad de cuentas entre regiones, acotada y reconciliada

* **Estado:** aceptado
* **Fecha:** 2026-10-29
* **Decisores:** Mateo Garrido

## Contexto y Declaración del Problema
Con las cuentas particionadas por región ([ADR-IT4-001](ADR-IT4-001.md)) aparecen dos problemas. Primero, a qué región va el inicio de sesión de una cuenta existente. Segundo, cómo se evita que el mismo correo quede registrado en dos regiones sin volver a atar el alta a un enlace entre continentes. Verificar la unicidad con un commit global es lo que rechaza [ADR-IT4-015](ADR-IT4-015.md).

## Impulsores de la Decisión (Decision Drivers)
* `QA-ESC-01`: confirmación en menos de 2 segundos independientemente del continente, y 0 rechazos por timeout.
* Reutilizar Scatter-Gather ([ADR-IT1-006](../ITERACION_1/ADR-006.md)), Bound execution times ([ADR-IT2-001](../ITERACION_2/ADR-IT2-001.md)) y Graceful degradation ([ADR-IT2-002](../ITERACION_2/ADR-IT2-002.md)) en lugar de sumar componentes.
* `QA-DIS-01`: una región que no responde no puede detener las altas de las demás.

## Opciones Consideradas
* Opción 1: Enrutar por proximidad en el borde. El cliente guarda la región de su cuenta. Si no la conoce (dispositivo nuevo), el API Gateway consulta en paralelo a las regiones, con una cota, y sigue con la que responde. En el alta, la API de registros consulta la unicidad del correo, por su huella, a las otras regiones en paralelo y con una cota. Si alguna no responde, el alta sigue y la cuenta queda marcada como "unicidad pendiente". Una verificación asíncrona, con Retry, la confirma o detecta el duplicado.
* Opción 2: Un directorio global de cuentas (correo a región), replicado en todas las regiones.
* Opción 3: Asignar la región por hash del correo, de modo que una sola región decida la unicidad de cada correo.
* Opción 4: Unicidad solo dentro de cada región, sin verificación entre regiones.

## Resultado de la Decisión
Opción elegida: **"Opción 1: enrutamiento por proximidad y verificación de unicidad en paralelo, acotada y reconciliada"**, porque reutiliza tácticas ya decididas, no agrega un componente replicado y hace que el alta nunca espere más que la cota. La opción 3 ata el alta a la región del hash, que puede estar en otro continente, y reintroduce el cruce síncrono. La opción 2 suma un almacén global con su propio problema de consistencia, que con tres regiones es más costoso que consultarlas en paralelo. La opción 4 deja pasar duplicados sin detectarlos. Si una región no responde dentro de la cota, el alta no se rechaza: se degrada la verificación, no el servicio.

### Consecuencias Positivas (Beneficios)
* El alta suma, como máximo, una consulta en paralelo acotada, del orden de un viaje de ida y vuelta a la región más lejana (estimación propia, de cientos de milisegundos).
* Si una región cae, las altas de las demás siguen.
* No hay un componente nuevo: se reutilizan Scatter-Gather, Bound execution times, Graceful degradation y Retry.
* El correo no viaja en claro entre regiones: se consulta por su huella.

### Consecuencias Negativas (Trade-offs / Riesgos)
* La unicidad es eventual: hay una ventana en la que dos regiones pueden aceptar el mismo correo.
* El mecanismo para resolver un duplicado detectado tarde (qué cuenta queda, cómo se avisa al titular) se fija en el diseño detallado. La regla de partida es bloquear la cuenta más reciente y avisar por el canal Email.
* El inicio de sesión desde un dispositivo nuevo cuesta una consulta paralela a todas las regiones.
* Cada alta genera consultas hacia las otras regiones. El volumen es bajo, pero hay que dimensionarlo.
* La cota de la verificación es un parámetro: demasiado larga consume parte de los 2 segundos, demasiado corta aumenta las altas con unicidad pendiente.
