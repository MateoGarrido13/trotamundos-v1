# Escalabilidad: Módulo de registro y autenticación en nodos propios, con Base de cuentas propia y escalado horizontal elástico

* **Estado:** aceptado
* **Fecha:** 2026-10-29
* **Decisores:** Yaco Recroa

## Contexto y Declaración del Problema
La iteración 1 desplegó el registro, el orquestador y los adaptadores "como la misma capa", y la Base primaria guarda las cuentas junto con los viajes. `QA-ESC-01` exige procesar el pico de altas de la semana de lanzamiento "sin bloquear ni degradar el servicio de los usuarios existentes". Si el alta comparte nodos con el Orquestador de viajes y base con los viajes, el pico de registros compite con la cotización (800 ms, `QA-PER-02`) y con las escrituras de viajes, que pagan el commit en dos fases. Es el mismo problema que [ADR-IT3-010](../ITERACION_3/ADR-IT3-010.md) resolvió para la ingesta. Hay que decidir dónde se despliega el alta y dónde guarda sus datos.

## Impulsores de la Decisión (Decision Drivers)
* `QA-ESC-01`: 0 rechazos por saturación o timeout y confirmación en menos de 2 segundos, sin degradar a los usuarios existentes.
* `QA-PER-02`: la cotización conserva sus 800 ms.
* `QA-DIS-01`: no sumar un acople nuevo entre el alta y las escrituras de viajes.
* Evitar políticas de prioridad entre altas y cotizaciones ([ADR-012](../ITERACION_1/ADR-012.md)).

## Opciones Consideradas
* Opción 1: Nodos propios para el Módulo de registro y autenticación en cada región, con una Base de cuentas separada de la Base de viajes. Los nodos son idénticos y sin estado propio, y se suman o se quitan según la carga (Increase resources, aplicada a un componente ya aislado).
* Opción 2: Mantener el registro en la misma capa y sobre la misma base que el Orquestador, sumando nodos al clúster conjunto.
* Opción 3: Nodos propios para el registro, pero compartiendo la Base primaria con los viajes.
* Opción 4: Nodos compartidos, con Prioritize events entre altas y cotizaciones.

## Resultado de la Decisión
Opción elegida: **"Opción 1: nodos propios y Base de cuentas propia, con escalado horizontal elástico"**, porque separa por despliegue y por datos lo que compite por recursos. El pico de altas no consume los nodos del Orquestador ni escribe en la Base de viajes, y por eso se mantiene el rechazo de la priorización de recursos. El estado vive en la Base de cuentas y no en el nodo, así que cualquier nodo atiende cualquier alta y el clúster crece o se achica con la carga. Increase resources se acepta acá y no contradice [ADR-IT3-015](../ITERACION_3/ADR-IT3-015.md): allí el problema era el acoplamiento entre productores y consumidores, y acá es el volumen de un componente que ya quedó aislado. Sigue siendo N-Tier ([ADR-001](../ITERACION_1/ADR-001.md)). Es una separación de despliegue, no un cambio de estilo, y no reabre [ADR-009](../ITERACION_1/ADR-009.md).

### Consecuencias Positivas (Beneficios)
* Un pico de altas no puede consumir nodos ni base del Core: `QA-PER-02` y `QA-DIS-01` quedan como estaban.
* El registro escala de forma independiente del resto.
* La Base de viajes deja de guardar cuentas, perfiles y sesiones, y queda dedicada a viajes y reservas.
* El Módulo de registro y autenticación se despliega y se prueba por separado.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Más nodos, más costo y más monitoreo.
* El 0 de rechazos depende de que la capacidad elástica llegue a tiempo: hay que fijar umbrales de escalado y capacidad de reserva con pruebas de carga.
* Mientras la Base de cuentas de una región conmuta a su pasiva (Reconfiguration, no inmediata), el alta espera. El cliente reintenta con la misma clave de operación y no se duplica la cuenta, pero esa ventana consume el presupuesto de 5 minutos al mes.
* La integridad entre cuentas y viajes ya no la garantiza una clave foránea: queda en la aplicación.
* Suma otra pieza desplegable por separado, junto con la ingesta. Si siguen multiplicándose, hay que reabrir [ADR-009](../ITERACION_1/ADR-009.md).
* Corrige lo que dijo el paso 5 de la iteración 1 sobre desplegar registro y orquestador como una misma capa.
