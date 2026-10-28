# Trotamundos — Justificación de los ADRs de la iteración 2

*Método ADD · TPE Diseño de Sistemas de Software · 28 de octubre de 2026*

Para cada ADR de la iteración 2 se indica por qué se eligió, qué se perdió y qué alternativa quedó más cerca de ganar. La base son los 6 ADRs (`ADR-IT2-01` a `ADR-IT2-06`), `ITERACION_2.md`.

## Performance: la cota de tiempo y la respuesta por defecto

### ADR-IT2-01. Bound execution times en la Caché de borde (vs. cota solo en el orquestador y sin cota)

**Por qué la cota en el borde.** El goal es cerrar la cotización en 800 ms al p90 (`QA-PER-02`) y el primer contenido móvil en 1,4 s al p90 (`QA-PER-03`). La latencia dominante es la de proveedores externos, que Trotamundos no controla, así que ningún tuning interno puede garantizar esos números. La única forma de garantizarlos es que alguien corte la espera y responda igual. La caché de borde es el único elemento que ve el tiempo de punta a punta (gateway, balanceador, orquestador y adaptadores) y atiende a web y móvil con una misma política. Una cota solo en el orquestador no cubre el tramo hacia el borde ni el caso móvil.

**Qué se paga.** La tabla del Paso 4 lo admite: se sacrifica la exactitud del cómputo y se perjudica la consistencia de lo que se muestra. Hay además tres puntos que el repo no resuelve (análisis propio):

- **Qué pasa sin copia.** «Entrega la copia que ya tiene» supone que existe una copia. Una combinación fecha-hospedaje-compañía que nadie consultó antes no tiene respuesta por defecto. El ADR no dice qué se devuelve en ese caso (grilla parcial, error controlado, mensaje de reintento).
- **Dónde empieza a contar la cota.** Si los 800 ms corren desde que el pedido llega a la caché, el navegador suma además su propia ida y vuelta hasta el borde, y el usuario percibe más de 800 ms. La cota interna debería ser menor que el objetivo.
- **Contenido personal en el borde.** Si el «primer contenido» móvil incluye datos del itinerario del usuario y no solo recursos estáticos, la clave de caché debe distinguir usuarios, por `QA-SEG-02`/`QA-SEG-03*`. En la iteración 1 el ADR-005 hablaba de recursos estáticos del login móvil.

**Alternativa que quedó más cerca de ganar.** La cota solo en el orquestador es más simple de configurar y probar, pero deja `QA-PER-03` sin dueño.

**Para endurecer el ADR:** fijar la cota interna con margen respecto del objetivo, definir la respuesta cuando no hay copia y aclarar qué entra en el «primer contenido» móvil.

### ADR-IT2-02. Graceful degradation (vs. error al vencer la cota y cota extendida)

**Por qué.** Cumple junto con el ADR-IT2-01: la cota decide *cuándo* cortar y la degradación decide *qué* se entrega. La función crítica es devolver una grilla o el primer contenido dentro de la cota. Lo que se suelta es la completitud y la frescura. La cuenta del ADR-006 de la iteración 1 muestra por qué es necesario: con tres ramas independientes que cumplan su p90, solo el 73 % (0,9³) de las cotizaciones tiene las tres a tiempo. La grilla parcial es entonces un caso frecuente y no una excepción rara. Un error o una espera más larga incumplen la latencia en ese 27 %.

**Qué se paga.** Precios que pueden estar desactualizados y grillas incompletas, justo en las disrupciones, cuando el viajero más decide con esos datos. Además (análisis propio):

- **La grilla parcial no debería quedar como copia por defecto.** La secuencia del Paso 5 dice que la caché guarda la grilla fresca si llega a tiempo, sin distinguir si es completa o parcial. Una grilla parcial guardada con el mismo TTL se serviría después como «respuesta por defecto» a otros usuarios, sin las aerolíneas que justo estaban lentas.
- **Hay dos relojes.** La cota del orquestador para reunir las ramas debe vencer antes que la de la caché. Si no, la caché siempre responde con la copia vieja mientras el orquestador todavía calcula la fresca.
- **Hace falta decir que el dato puede no ser reciente.** El repo no define cómo se informa al usuario que está viendo una grilla parcial o una copia.

**Alternativa que quedó más cerca de ganar.** Extender la cota hasta que responda la API más lenta es lo único que da respuestas completas. Pero convierte al proveedor más lento en el techo de la latencia de todo el sistema.

**Para endurecer el ADR:** TTL distinto para grillas parciales (o no guardarlas), una antigüedad máxima para servir copias y una marca visible de «dato no actualizado».

### ADR-IT2-03. Cota de espera por adaptador, sin Retry (vs. Retry y espera sin cota propia)

**Por qué.** Los tres adaptadores corren en paralelo (Scatter-Gather) y cada uno es la ACL de su proveedor. Es el lugar natural para decidir cuánto esperar a ese proveedor sin afectar a los demás. Sin cota propia, un solo proveedor mudo consume toda la cota del borde y arrastra a los otros dos. El Retry se descarta por aritmética: un reintento cuesta como mínimo otra espera completa de esa API, y con 800 ms de presupuesto total no queda margen (ver ADR-IT2-06). Además, bajo 250.000 concurrentes, reintentar contra APIs con cuota multiplicaría la carga justo cuando están más lentas.

**Qué se paga.** Una falla transitoria que un reintento habría resuelto se convierte en una grilla parcial. Y el ADR no fija el valor de la cota de cada adaptador, porque los drivers no lo definen. Quedan además tres puntos (análisis propio):

- **El ping y el precio comparten una sola cota.** Con el Ping/Echo del ADR-004 de la iteración 1, cada rama hace dos llamadas síncronas en serie (eco y precio). La cota del adaptador debe cubrir ambas, y el costo del ping en el camino crítico que ya señalaba la justificación del ADR-004 sigue vigente.
- **La cota limita el tiempo, no la concurrencia.** Los adaptadores corren en el mismo proceso que el orquestador, y uno lento puede agotar hilos compartidos aunque cada espera esté acotada. Sigue pendiente aislarlos (bulkhead), como marcaba la justificación del ADR-007.
- **No se evaluó el corte de circuito.** Tras varios silencios seguidos, dejar de llamar a esa API un tiempo da la misma protección que Retry sin gastar la cota en cada pedido.

**Alternativa que quedó más cerca de ganar.** Un reintento acotado, solo si quedan milisegundos de cota y solo ante errores rápidos y explícitos (por ejemplo un 503 inmediato). Esa variante cuesta poco y no choca con la latencia, pero el ADR-IT2-06 rechaza Retry en bloque sin distinguir el tipo de falla.

## Disponibilidad de datos

### ADR-IT2-04. Transactions: commit en dos fases entre Base primaria y Base pasiva (vs. replicación asíncrona y semisíncrona)

**Por qué.** El goal fija el trade-off: la consistencia va por encima de la latencia (`QA-DIS-01`). Con este ADR queda decidido el mecanismo que el ADR-003 había dejado «propuesto». De las dos opciones que ese ADR planteaba, se elige la síncrona: RPO cero, es decir, ninguna escritura confirmada se pierde si cae la primaria. Esto también protege a `QA-ESC-01`. Un alta confirmada seguiría existiendo tras un failover, y el login inmediato de ese usuario no fallaría. El costo de latencia lo pagan solo las escrituras (altas, viajes). La cotización de `QA-PER-02` es una lectura y no pasa por este camino.

**Qué se paga.** Lo que el ADR-003 ya advertía: cada escritura suma un viaje de ida y vuelta a la pasiva. Intra-región es barato, pero entre regiones entra en tensión con los 2 s de `QA-ESC-01` y con la vocación multi-región del enunciado. Además (análisis propio):

- **Disponibilidad al revés.** Con una sola pasiva y escritura síncrona, si cae la pasiva la primaria no puede confirmar nada. Para no consumir los 5 minutos mensuales por una falla del respaldo, hace falta definir un timeout y qué se hace entonces (por ejemplo, seguir sin respaldo temporalmente y reconocer ese riesgo).
- **El nombre exagera la herramienta.** El commit en dos fases clásico coordina varios gestores de recursos con un coordinador, y tiene su propio problema de bloqueo si ese coordinador cae. Entre un primario y su réplica, lo habitual es la replicación síncrona nativa de la base (la primaria no confirma hasta que la réplica confirma). Da la misma garantía de consistencia sin coordinador. Conviene que el ADR aclare cuál de las dos se implementa.

**Alternativa que quedó más cerca de ganar.** La replicación semisíncrona con timeout: casi todo el tiempo se comporta como síncrona, pero degrada a asíncrona si la pasiva no responde, evitando el bloqueo de escrituras. Es más tolerante pero admite una ventana en la que una falla pierde escrituras confirmadas.

**Para endurecer el ADR:** elegir el mecanismo concreto, definir el timeout y el comportamiento si la pasiva no responde, y actualizar el conector TCP de la vista de componentes, que en la iteración 1 figuraba como replicación asíncrona.

### ADR-IT2-05. Reconfiguration: conmutación a la Base pasiva (vs. recuperación manual y modo solo lectura)

**Por qué.** 5 minutos de inactividad al mes equivalen a ~99,988 % de disponibilidad (5 de 43.200 minutos). Una caída de la primaria con recuperación manual puede gastar ese presupuesto de una sola vez. Con la pasiva ya al día gracias al ADR-IT2-04, promoverla es la forma más corta de seguir atendiendo escrituras. El modo solo lectura mantiene vivas las lecturas pero sacrifica altas y reservas, una función crítica. El ADR-002 sostenía que solo la variante hot cabe en el presupuesto. La pasiva tiene los datos al día pero debe promoverse, así que es en la práctica un warm spare, y el tiempo del traspaso es lo que hay que acotar.

**Qué se paga.** El propio ADR lo dice: el traspaso no es inmediato y se paga en latencia, y lo que no puede reasignarse queda sin servicio durante ese lapso. Quedan además tres puntos (análisis propio):

- **Quién detecta la caída.** El repo no dice qué observa que la primaria dejó de atender ni cuánto tarda en decidirlo. Ese tiempo de detección, más la promoción y el cambio de conexión JDBC, es lo que consume el presupuesto de 5 minutos. Podría reutilizarse el Ping/Echo del ADR-004, que ya se usa en los health checks del balanceador.
- **Split-brain.** Si la primaria no cayó sino que quedó aislada y vuelve, dos bases podrían aceptar escrituras. Hace falta un mecanismo que impida a la antigua primaria seguir escribiendo (fencing).
- **Sin respaldo tras la conmutación.** Después del traspaso hay una sola copia hasta reconstruir un nuevo respaldo, y una segunda falla en ese período ya no tiene recuperación.

**Una inconsistencia en el enunciado del goal.** `QA-DIS-01` se describe en `ITERACION_2.md` como la «caída de un nodo de cotización», pero la reconfiguración se aplica a la base de datos. La caída de un nodo del tier de negocio ya está cubierta por el clúster con balanceador (ADR-002). Conviene aclarar en el escenario que lo que se refina acá es el nivel de datos.

**Alternativa que quedó más cerca de ganar.** La recuperación manual es la más barata y sin riesgo de split-brain, pero no garantiza el presupuesto mensual.

## Táctica rechazada

### ADR-IT2-06. Retry (rechazado)

Su ventaja es recuperar fallas transitorias y mejorar la completitud de la grilla. Pero cada intento se paga en latencia, y la cota total es de 800 ms. Un timeout largo rompe `QA-PER-02`. Uno corto descarta una API que todavía podía responder, y eso perjudica la disponibilidad de ese origen. Con 250.000 concurrentes y APIs con cuota, un reintento masivo durante una disrupción amplifica la carga sobre proveedores ya degradados.

**Qué se paga.** Las fallas transitorias terminan en grilla parcial.

**Alternativa que quedó más cerca de ganar.** Un reintento acotado, solo ante errores rápidos y explícitos y con margen de cota. El ADR rechaza Retry en bloque, sin distinguir esos casos.

**Cuándo reabrirlo:** como reintento acotado, o como reintento asíncrono fuera del camino de la cotización (para completar la caché, no la respuesta actual).

