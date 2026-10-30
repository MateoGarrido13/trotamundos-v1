# Trotamundos — Justificación de los ADRs de la iteración 3

*Método ADD · TPE Diseño de Sistemas de Software · 28 de octubre de 2026*

Para cada ADR de la iteración 3 se indica por qué se eligió, qué se perdió y qué alternativa quedó más cerca de ganar. La base son los 15 ADRs (`ADR-IT3-001` a `ADR-IT3-015`), `ITERACION_3.md`, las cifras que acompañan algunas cuentas son hipótesis de ejemplo, no datos del enunciado.

## Ingesta asíncrona

### ADR-IT3-001. Broker con tres colas (vs. llamadas síncronas, un broker por flujo y cola sobre la base)

**Por qué un broker.** La iteración 3 mete al sistema tres flujos que no tienen un usuario esperando (novedades de Booking, correo y notificaciones) y con un requisito de tiempo de otra naturaleza: 5 minutos (`QA-PER-01`) en lugar de 800 ms. Llevarlos de forma síncrona al Orquestador haría competir el pico de las 8 am con la cotización, que es justo lo que `QA-PER-02` prohíbe. La cola convierte un pico de llegada en un backlog que se drena a la velocidad del consumidor, y además hace que `QA-INT-02` sea medible: Instagram es un consumidor más de la cola de notificaciones, sin tocar a los existentes.

**Qué se paga.** Un componente más, latencia extra (que sale del presupuesto de 5 minutos) y consistencia eventual. Además reabre el problema de `QA-DIS-01` en otro lugar: un broker único es un SPOF que se cubre con Redundant spare y Reconfiguration, y el traspaso no es inmediato.

**Qué alternativa quedó más cerca.** La cola sobre la base (outbox con consulta periódica), porque suma una pieza menos para un prototipo. Pierde porque dirige el pico hacia la Base primaria, que ya es el techo de escritura señalado en la iteración 1 y que además paga el commit en dos fases de la iteración 2. También contradice la regla de que la ingesta nunca escribe en la base. El broker por flujo da mejor aislamiento de fallas, pero triplica la operación; con la regla «un solo broker» el aislamiento se reduce a las colas, y eso solo aísla memoria y backlog, no CPU ni E/S (análisis propio).

**Para endurecer el ADR:**

- Decir si el respaldo es hot o warm (el ADR dice «redundante» sin elegir), y si el broker confirma al productor antes o después de replicar. Es el mismo trade-off de ADR-003 de la iteración 1: replicación síncrona sin pérdida pero más lenta, o asíncrona rápida pero que puede perder mensajes aceptados en un failover.
- Fijar la semántica de entrega. Con confirmación del consumidor y redelivery la entrega es al menos una vez, y por eso ADR-IT3-003 necesita idempotencia (análisis propio).
- Dejar escritos los criterios para reabrir la decisión de un broker por flujo: si una cola saturada degrada a otra.

### ADR-IT3-002. Bound queue sizes

**Por qué.** Una cola sin techo convierte un pico en un backlog que crece hasta agotar el recurso del broker, y mientras tanto cada mensaje espera más. Acotar el tamaño pone un límite explícito al retraso. El tamaño tiene una lectura directa contra el driver: el retraso máximo de un mensaje es aproximadamente el tamaño de la cola dividido por la tasa de consumo, así que para cerrar en 5 minutos el tamaño debería ser, como mucho, la tasa de consumo por el presupuesto de tiempo que quede tras la detección y el recorrido por el broker (análisis propio).

**Qué se paga.** El driver pide dos cosas que aquí chocan: entregar todo (100 % de `QA-SEG-03*`) y cerrar en 5 minutos (`QA-PER-01`). Al desbordar, hay que elegir entre retrasar o perder, y la táctica no resuelve la elección, solo la hace visible.

**Para endurecer el ADR:**

- Distinguir los orígenes. Los de tipo pull (el correo, que el adaptador sondea) tienen contrapresión gratuita: si la cola está llena, simplemente no se sondea y no hay pérdida. El riesgo real está en los de tipo push (Booking y los envíos de notificaciones desde el Orquestador), donde el productor no controla cuándo llega el mensaje (análisis propio).
- Definir qué hace el listener cuando la cola está llena, por ejemplo responder con un error de indisponibilidad y confiar en el reintento de Booking, que no controlamos.
- Agregar una cola de mensajes muertos (dead-letter) con aviso a operaciones para los mensajes que agotan los reintentos; hoy el ADR menciona el aviso pero no dónde queda el mensaje.
- Fijar el criterio para dimensionar con pruebas de carga, porque los drivers no dan ningún número.

### ADR-IT3-003. Retry con identificador único (reabre el rechazo de la iteración 2)

**Por qué.** La iteración 2 rechazó Retry por una razón concreta: bloqueaba contra los 800 ms. Esa razón no aplica a una ruta sin usuario esperando, así que reabrirlo es coherente y no una contradicción. Además, con un broker que reentrega los mensajes sin confirmar, «sin Retry» no es una opción neutra: el reintento ya existe de hecho, y lo que se decide es si la idempotencia es explícita (análisis propio). El identificador único por mensaje es lo que evita que un reintento duplique una reserva o un envío.

**Qué se paga.** Los reintentos consumen el presupuesto de 5 minutos. Con backoff exponencial, la espera acumulada crece rápido (por ejemplo 1, 2, 4, 8 y 16 segundos suman 31 segundos solo en esperas, análisis propio). Cada reintento que escribe paga otra vez el commit en dos fases. Y hay que guardar los identificadores ya procesados, con un tiempo de retención que cubra la ventana de reintentos y de reentrega del broker.

**Para endurecer el ADR:**

- Aclarar que son dos políticas (sin Retry en la cotización síncrona y con Retry en la ruta asíncrona) y dónde se aplica cada una, para que no se mezclen en la implementación.
- Fijar un límite de reintentos y un backoff con variación aleatoria, para evitar tormentas cuando un proveedor cae.
- Definir el destino final del mensaje que agota los reintentos (ver la cola de mensajes muertos en ADR-IT3-002).

### ADR-IT3-009. Novedades de Booking por aviso (push) vs. polling

**Por qué.** `QA-PER-01` mide desde que «el listener detecta la actualización». Con push, la detección es inmediata y no hay consultas vacías contra una API externa con cuota. Con polling, la detección llega con un retraso igual a la mitad del intervalo en promedio, y a la escala del sistema (2 millones de usuarios activos por semana) las consultas periódicas por reserva serían muy costosas contra una API con cuota (análisis propio).

**Qué se paga.** Se depende de que Booking ofrezca y cumpla el aviso. Si un aviso se pierde, nadie lo nota: no hay otra vía que lo detecte. Y la medida es débil por diseño: el reloj de 5 minutos arranca en la detección y no en la actualización de Booking, así que cualquier retraso previo queda fuera. El enunciado del TPE pide obtener «detalles de las reservas, actualizaciones y cancelaciones» por APIs estándar, pero no dice si es push o pull.

**Qué alternativa quedó más cerca.** El híbrido (push más un polling lento de reconciliación). Es la mejora más barata del ADR: el aviso da la velocidad y el polling cubre los avisos perdidos.

**Para endurecer el ADR:**

- Autenticar el origen del aviso (firma o secreto compartido) y limitar su tasa: el listener es un endpoint público de Trotamundos que no pasa por el API Gateway de ADR-008 de la iteración 1, y conviene decir explícitamente que existe una segunda entrada pública y cómo se protege (análisis propio).
- Aclarar qué pasa con los avisos que llegan mientras el listener está caído.
- Anotar la limitación de la medida: es una medida desde la detección y no de extremo a extremo.

### ADR-IT3-010. Ingesta y adaptadores de entrada en nodos propios

**Por qué.** El pico de las 8 am de la ingesta no debe compartir nodos con las cotizaciones. Al separarlos por despliegue, la contención desaparece sin necesidad de políticas de prioridad, y por eso se mantiene el rechazo de la Priorización de recursos (ADR-012 de la iteración 1). Los adaptadores de cotización quedan junto al Orquestador porque se invocan en memoria dentro de los 800 ms, y separarlos sumaría un salto de red por cotización.

**Qué se paga.** Más nodos y una segunda forma de desplegar adaptadores. Y la separación es parcial: el Servicio de ingesta entrega al Orquestador, que comparte nodos con la cotización y es el único que escribe en la base con commit en dos fases. Ese paso por el Orquestador es por donde el pico vuelve a llegar a los nodos de la cotización (análisis propio). El texto «el conflicto se evita por separación» es más fuerte de lo que el diseño sostiene.

**Qué alternativa quedó más cerca.** Un servicio por adaptador de entrada. Da más aislamiento, pero cada servicio nuevo suma despliegue y monitoreo, sin un driver que lo pida.

**Para endurecer el ADR:**

- Limitar la tasa a la que la ingesta entrega al Orquestador, o dedicar instancias del Orquestador a la entrada, para que el aislamiento sea real.
- Anotar que la ingesta y el Orquestador comparten la Base primaria: el techo de escritura de la iteración 1 sigue ahí.
- Dejar escrito cuándo se reabre Priorización de recursos: si se llegaran a compartir nodos.

## Extensibilidad del Core

### ADR-IT3-004. Abstract common services (`IProveedor` e `ICanal`)

**Por qué.** `QA-INT-01` y `QA-INT-02` miden lo mismo desde dos lados: que lo nuevo sea un solo módulo y que lo existente no se modifique. Una interfaz común convierte a un hotel o un canal nuevo en una implementación más. Se apoya en la ACL de la iteración 1 (ADR-007), que ya aisla el modelo interno del contrato del proveedor: `IProveedor` solo uniforma lo que ya hacían los adaptadores (traducir y hacer ping).

**Qué se paga.** La interfaz común es un contrato crítico: un cambio en ella afecta a todas las implementaciones. Y `recibirNovedad` obliga a los adaptadores de cotización a implementar algo que no usan, lo que viola la segregación de interfaces. También se solapa con los contratos de la iteración 1 (`ICotizadorHotel`, `IProveedorInventario`), y hay que decidir cuál extiende a cuál.

**Para endurecer el ADR:**

- Separar la interfaz en dos: una común mínima (`ping`, `traducir`) y otra aparte para quienes reciben novedades, de modo que los adaptadores de cotización no carguen con lo que no usan (análisis propio).
- Definir la política de versionado de `IProveedor` e `ICanal`.
- Escribir la jerarquía resultante con los contratos de la iteración 1, para que no queden dos.

### ADR-IT3-005. Polymorphism y Configuration-time binding en el modelo de reservas

**Por qué.** `QA-EVO-01` pide sumar un medio de transporte en 3 meses sin tocar la agrupación. La alternativa obvia, un campo de tipo con condicionales, obliga a reabrir la agrupación con cada medio nuevo. Con `Reserva` abstracta, la agrupación depende de una interfaz estable (identificador, viaje, fechas, estado y resumen) y cada tipo encapsula su validación y su fecha de término.

**Qué se paga.** Indirección y diseño previo, con riesgo de sobrediseñar para una medida de 3 meses y cinco tipos. `Reserva` queda como un contrato crítico, y persistir una jerarquía polimórfica en la base trae su costo de mapeo.

**Punto débil: el Registro de tipos.** El ADR justifica el polimorfismo, pero el Configuration-time binding aporta poco si dar de alta un tipo igual exige escribir una clase y desplegar: la configuración solo registra lo que el código ya contiene (análisis propio). Se justificaría si los tipos se habilitaran por entorno o por región (el TPE pide operar en varios mercados), y el ADR no lo dice.

**Para endurecer el ADR:**

- Decir qué aporta el registro por configuración frente a descubrir las clases al desplegar, o quitarlo.
- Anotar que `Reserva` debe ser estable y qué se considera un cambio compatible.
- Indicar cómo se persisten los tipos y cómo se leen los tipos desconocidos tras un rollback.

### ADR-IT3-011. Split module / Redistribute responsibilities (rechazado)

Su ventaja real sería separar cotización y gestión de viajes para escalarlas por separado, que es el límite de N-Tier admitido en ADR-001 de la iteración 1. Pero ningún driver de la iteración lo exige: la ingesta ya sale del Orquestador (ADR-IT3-010) y el polimorfismo cubre `QA-EVO-01` (ADR-IT3-005). Además, partirlo sumaría un salto de red a una cotización que hoy se resuelve en memoria dentro de los 800 ms, o una sincronización entre dos mitades.

El costo de rechazarlo es que el Orquestador concentra cotización, gestión de viajes, modelo de reservas, novedades, whitelist y mensajes en revisión. Es la tendencia a la baja cohesión que el propio ADR admite.

**Cuándo reabrirlo:** si el Orquestador se vuelve un cuello de botella, o si se decide extraer cotizaciones como servicio (camino incremental ya anotado en ADR-001 de la iteración 1 y en ADR-009, Microservicios).

### ADR-IT3-012. Configure behavior (rechazado)

Su ventaja sería sumar un proveedor con solo configuración, lo que acercaría el esfuerzo de `QA-INT-01` a cero. Pero `QA-INT-01` habla de una API propietaria, y entre APIs propietarias las diferencias son de protocolo, formato y semántica, más que de parámetros. Un conector genérico terminaría con condicionales por proveedor, lo que rompe el aislamiento de la ACL (ADR-007 de la iteración 1) y multiplica los casos de prueba.

Lo que se paga es duplicación entre adaptadores. Esa duplicación se reduce con una biblioteca compartida de infraestructura (cliente HTTP, ping, timeout), sin parametrizar el comportamiento (análisis propio).

**Cuándo reabrirlo:** si varios proveedores resultan ser variantes de un mismo protocolo estándar.

### ADR-IT3-013. Interpret parameters / Shared repositories (rechazado)

Su ventaja sería dar de alta un tipo de reserva por configuración, sin desplegar. Pero se pierde la validación estática y el control por tipo, que es lo que `REF-01` necesita para archivar y resumir cada reserva con coherencia. Con cinco tipos y una medida de 3 meses, el polimorfismo alcanza (ADR-IT3-005).

Se paga con que cada tipo exige código y despliegue.

**Cuándo reabrirlo:** si los tipos pasaran a ser muchos, definidos por terceros o cambiantes por mercado.

### ADR-IT3-014. Adhere to standards (rechazado)

**Justificación débil.** El rechazo se apoya en que las APIs de los proveedores son propietarias. Pero el enunciado del TPE habla de «APIs estándar» en los requerimientos funcionales y en Interoperabilidad, y de «integración fluida» como imperativa. El ADR no puede quedar leído como «el diseño ignora los estándares».

**Lo que sí se sostiene.** Trotamundos no puede imponer un estándar a un proveedor, y `QA-INT-01` se mide sobre una API propietaria. Pero adoptar un estándar donde el proveedor ya lo ofrezca es gratis y reduce el trabajo del adaptador, y el ADR lo dice en su resultado.

**Para endurecer el ADR:**

- Reformular la decisión como «no exigir estándares; aprovechar los que el proveedor exponga dentro de su adaptador» y alinear el título con eso.
- Citar explícitamente la frase del enunciado y explicar por qué no contradice.

### ADR-IT3-015. Increase resources (rechazado)

**Justificación débil.** Presentar Increase resources como alternativa al desacople es forzado: no son alternativas de una misma decisión. Una cola con consumidores sigue necesitando dimensionarlos, y el escalado automático de consumidores es complemento del broker, no su rival (análisis propio). Es el mismo defecto señalado en la iteración 1 al comparar Heartbeat con Redundant spare.

**Lo que sí se sostiene.** Sumar recursos sin desacoplar no ataca la causa: el pico seguiría compitiendo con las cotizaciones. Y cuesta dinero de forma permanente en lugar de pagar solo durante los picos.

**Para endurecer el ADR:**

- Reescribirlo como «escalar solo los consumidores y de forma elástica» y explicar que complementa a ADR-IT3-001 y ADR-IT3-002.
- Anotar que el límite de 5 minutos depende de que la tasa de consumo alcance, y que esa tasa se verifica con pruebas de carga.

## Seguridad del correo

### ADR-IT3-006. Acceso controlado al correo (vs. credenciales y reenvío manual)

**Por qué.** `QA-SEG-03*` exige que el sistema acceda solo con la autorización del titular. Pedir las credenciales del correo deja a Trotamundos custodiando contraseñas, que es el peor activo posible. El reenvío manual no custodia nada, pero contradice `REF-02`: el enunciado pide «sondear y escanear» el correo, no que el usuario reenvíe. Queda el acceso delegado: consentimiento, permisos mínimos, tokens cifrados y revocación.

**Qué alternativa quedó más cerca.** El reenvío manual, que para un prototipo es lo más barato y lo más seguro. Pierde porque rompe la automatización que es el valor del producto.

**Qué se paga.** Fricción en el alta, manejo de claves y renovación de tokens, y datos más sensibles en la base. El sondeo tiene su costo externo: con, por ejemplo, un millón de buzones autorizados sondeados cada 5 minutos serían unas 3.300 consultas por segundo contra los proveedores de correo (cifra de ejemplo, análisis propio), y la frecuencia es un parámetro que el ADR no fija.

**Para endurecer el ADR:**

- Separar la decisión en dos: el consentimiento y los tokens por un lado, y la política de revocación por otro. Hoy cuatro tácticas van en un solo ADR.
- Definir qué ve el usuario cuando el token vence o se revoca: el adaptador deja de leer, pero nadie avisa (análisis propio).
- Resolver la retención tras revocar. Conservar lo incorporado es razonable, pero con un mercado multirregión conviene poder borrar a pedido del titular.

### ADR-IT3-007. Parseo aislado (vs. parsear en el adaptador o en el Orquestador)

**Por qué.** El contenido de un correo es entrada hostil: HTML, adjuntos, plantillas rotas. Parsearlo en el Adaptador de correo pondría el parser junto a los tokens, y un fallo del parser expondría el acceso al buzón. Parsearlo en la ingesta o el Orquestador lo pondría junto a la base. El proceso aislado, sin token ni acceso a datos, es el lugar donde menos daño puede hacer un correo malicioso (análisis propio).

**Qué se paga.** Una pieza más y un salto por el broker. Descartar lo que no valida puede perder reservas legítimas con formatos nuevos, y la extracción por plantillas de proveedores es frágil.

**Para endurecer el ADR:**

- Limitar el consumo del parser (tiempo, memoria y tamaño del mensaje), porque aislar el proceso no evita que un mensaje lo deje colgado.
- Registrar las causas de descarte y contarlas, para detectar cuándo una plantilla de proveedor cambió.
- Aclarar el destino de un mensaje que no parsea: hoy se descarta sin que nadie se entere, y eso choca con el 100 % de `QA-SEG-03*`.

### ADR-IT3-008. Whitelist con Mensajes en revisión (vs. descartar y lista negra)

**Por qué.** Descartar lo que no está en la whitelist pierde reservas legítimas en silencio, que es exactamente lo que `QA-SEG-03*` no tolera. La lista negra invierte el riesgo: acepta todo y filtra lo conocido como malo, y deja entrar lo desconocido, que es lo peligroso. La cola de revisión pone la decisión en manos del titular y conserva la reserva hasta que decide.

**Punto débil: la medida.** El 100 % de `QA-SEG-03*` se cumple «para los usuarios autorizados cuyos remitentes son seguros o fueron aprobados». Es decir, la medida se redefine por diseño: la reserva de un remitente no aprobado no está en el itinerario hasta que el titular actúe. Es una decisión razonable, pero el ADR debería decir que la medida es condicional.

**Qué se paga.** Una pantalla y una tarea para el usuario, almacenamiento de datos de remitentes no verificados y riesgo de acumulación.

**Para endurecer el ADR:**

- Sembrar la whitelist con remitentes conocidos de aerolíneas, hoteles y arrendadoras, para que el primer uso no deje todo en revisión (análisis propio).
- Considerar la autenticidad del remitente (resultado de SPF, DKIM y DMARC): una whitelist por dirección se puede falsificar, y aprobar a un remitente falsificado lo habilita para siempre.
- Definir la retención de los mensajes en revisión y qué se hace cuando nadie los atiende.
