# Trotamundos — Justificación de los ADRs de la iteración 1

*Método ADD · TPE Diseño de Sistemas de Software · 28 de octubre de 2026*

Para cada ADR de la iteración 1 se indica por qué se eligió, qué se perdió y qué alternativa quedó más cerca de ganar. La base son los 13 ADRs, `ITERACION_1.md`, `LISTADO_DRIVERS.md` y el enunciado del TPE. Donde la justificación del repo es débil, se marca como tal. Las cuentas y observaciones que no están en el repo son análisis propio.

## Estilo del Core

### ADR-001. N-Tier (vs. Microservicios y Micro-kernel)

**Por qué N-Tier.** El goal de la iteración es la topología del Core, con `REF-01`, `CON-01`, `QA-PER-02/03` y `QA-ESC-01`. El registro masivo suena exigente, pero 100.000 altas por día son unas 1,2 por segundo en promedio. Aun con un pico de lanzamiento de 50 veces, un clúster stateless detrás de un balanceador lo absorbe. El requisito difícil de `QA-ESC-01` es otro: cuenta creada y login inmediato sin rechazos. Eso pide consistencia «leer lo que acabo de escribir», y una base primaria única la da gratis.

El contexto del TPE también pesa: es un prototipo grupal con alcance acotado, y N-Tier mantiene bajo el costo operativo.

**Qué se paga.** Registro, orquestador y adaptadores se despliegan y escalan juntos. Los picos domingo-lunes y las disrupciones golpean sobre todo a las cotizaciones, no al registro, y N-Tier no puede escalar cotizaciones por separado. La propia tabla del Paso 4 admite que «se sacrifica Escalabilidad». La base única de escritura es el techo real, y el Paso 7 lo deja como pendiente (`QA-ESC-01`, Partially).

**Salida futura.** Registro, orquestador y adaptadores ya son elementos separados en el Paso 5. Si el escalado desigual se vuelve un problema, extraer cotizaciones como servicio es un camino incremental.

### ADR-009. Microservicios (rechazado)

Su ventaja real para este caso sería escalar cotizaciones de forma independiente en los picos y desplegar adaptadores sin tocar el resto (`QA-INT-01`, `QA-EVO-01`). Pero hoy esos escenarios están fuera del goal. En cambio, sumaría:

- **Saltos de red:** más hops dentro de un presupuesto de 800 ms (`QA-PER-02`).
- **Consistencia:** consistencia eventual justo donde `QA-ESC-01` pide login inmediato.
- **Operación:** gateway, descubrimiento, trazabilidad distribuida y una base por servicio, para un equipo que debe acotar el alcance del prototipo.

**Cuándo reabrirlo:** al entrar `REF-06`/`QA-PER-04*` (analítica pesada) o cuando crezca el número de proveedores.

### ADR-011. Micro-kernel (rechazado)

Esta es la alternativa que mejor encaja con `QA-INT-01`, `QA-INT-02`, `QA-EVO-01` y los futuros medios de transporte: un plugin por proveedor, canal o medio. Pero esos escenarios no están en el goal, y el ADR solo cita `QA-ESC-01` y `QA-PER-02`. Conviene que el ADR nombre esos escenarios como lo que se resigna.

Contra el micro-kernel está que el Core debe servir 250.000 usuarios concurrentes en varias instancias. Un plugin defectuoso dentro del proceso anfitrión también amenaza la disponibilidad (`QA-DIS-01`). La extensibilidad que ofrecía se recupera de forma localizada con la ACL (ADR-007), sin convertir todo el sistema en kernel.

## Disponibilidad

### ADR-002. Redundant spare

**Por qué.** 5 minutos de inactividad al mes equivalen a \~99,988 % de disponibilidad. Con una sola falla de un nodo que tarde en recuperarse (un cold spare, por ejemplo) se consume todo el presupuesto, así que solo sirve la variante hot. El clúster del Paso 5, con nodos idénticos que sirven tráfico, es en la práctica redundancia activa. Además, el costo de duplicar se amortiza, porque esos mismos nodos dan la capacidad que `QA-PER-02` (250.000 concurrentes) y `QA-ESC-01` ya exigen.

**Qué se paga.** Dinero, y complejidad de balanceo y sesión. «Sin perder peticiones en vuelo» funciona para cotizaciones, que son lecturas reintentables, pero no para altas. Estas necesitan una clave de idempotencia (análisis propio, no está en el repo).

**Para endurecer el ADR:**

- Elegir explícitamente entre hot, warm y cold; hoy dice «hot, warm o cold» sin decidir.
- Comparar contra otra recuperación (warm spare, activo-activo) y no contra Heartbeat. Heartbeat detecta fallas y Redundant spare las recupera, así que no son alternativas de la misma decisión.
- Citar `QA-PER-02` y `QA-ESC-01` como drivers, porque son los que justifican el clúster dentro del goal (`QA-DIS-01` está afuera).

### ADR-003. State resynchronization (propuesto)

**Por qué se necesita.** Un respaldo sin el estado del activo no puede asumir el tráfico sin pérdida. El tier de negocio es en la práctica stateless, porque las sesiones y los viajes viven en la base. Lo que realmente hay que sincronizar es el par primario/pasivo de la BD (Tier 3).

**Por qué sigue «propuesto».** Falta elegir el mecanismo, y ahí está el trade-off real:

- **Replicación síncrona:** da RPO cero, pero suma un viaje de ida y vuelta a cada escritura. Intra-región es barato, pero entre continentes entra en tensión con los 2 s de `QA-ESC-01`.
- **Replicación asíncrona:** es rápida, pero un failover puede perder altas ya confirmadas.

El checksum del Paso 5 sirve para detectar divergencia, no para replicar, así que no resuelve esta elección por sí solo.

### ADR-004. Ping/Echo (vs. Heartbeat)

**Por qué.** Con `CON-02`, las APIs de aerolíneas, hoteles, arrendadoras y correo son de terceros, y no se les puede exigir que emitan latidos. El ping parte del adaptador, que es lo único que Trotamundos controla. Además, los health checks del balanceador sobre los nodos (`QA-DIS-01`) son también Ping/Echo, así que se usa un solo mecanismo de detección en todo el sistema.

**Qué se paga.** La secuencia del Paso 5 hace el ping por cada cotización y antes del pedido de precio. Eso suma al menos un viaje de red a cada rama dentro de los 800 ms y multiplica las llamadas a APIs externas con cuota, bajo 250.000 concurrentes. Es la parte más discutible de la decisión. Un ping periódico que mantenga un estado de salud por proveedor, o un timeout con corte de circuito, da la misma protección sin ese costo en el camino crítico.

### ADR-010. Heartbeat (rechazado)

Su ventaja es detectar fallas silenciosas sin tráfico de requests y con menos overhead por chequeo. Pero exige que el vigilado emita mensajes, y eso no se puede pedir a terceros. Adoptarlo solo para nodos internos obligaría a mantener dos mecanismos de detección, cuando Ping/Echo ya cubre ambos casos.

## Performance

### ADR-005. Caché (vs. Priorización de recursos)

**Por qué.** El presupuesto de 800 ms al p90 lo domina la latencia de proveedores externos, no el cómputo local. Los picos son correlacionados (todos buscan alternativas por la misma disrupción), así que una misma combinación fecha-hospedaje-compañía se repite mucho y un acierto evita todo el fan-out. La caché de borde también sirve los recursos estáticos del login móvil (`QA-PER-03`), aunque el ADR solo cita `QA-PER-02`.

**Qué se paga.** Consistencia. En viajes un precio desactualizado es un problema de negocio. Como el diseño solo reemplaza la copia cuando se escribe una cotización nueva, una entrada con aciertos continuos nunca se refresca. Hace falta un TTL corto y revalidar el precio al reservar. La clave también debe incluir moneda y mercado, por la vocación multi-región del TPE. Y las combinaciones poco populares casi no se benefician de la caché.

### ADR-006. Scatter-Gather (vs. Priorización de recursos)

**Por qué.** Consultar secuencialmente a aerolíneas, hoteles y arrendadoras suma sus latencias. En paralelo, el total lo fija el más lento. Priorizar hilos no acorta ninguna de esas esperas.

**Qué se paga.** Amplifica la cola de latencia. Si las tres ramas fueran independientes y cada una cumpliera su p90, solo el 73 % (0,9³) de las cotizaciones tendría las tres a tiempo. Por eso el deadline y la grilla parcial con «los orígenes que respondieron» son parte necesaria de la decisión y no un detalle. Hace falta E/S no bloqueante, para no multiplicar los hilos por tres bajo 250.000 concurrentes. Y el ping de ADR-004 alarga cada rama.

### ADR-012. Priorización de recursos (rechazado)

Beneficia cuando las transacciones compiten con reportes pesados (`REF-06`, `QA-PER-04*`), y ambos están fuera del goal. Tampoco ataca la latencia dominante, que es la de proveedores externos. Cuando la analítica entre al alcance, probablemente convenga separar la carga (réplica de lectura, almacén analítico) antes que repartir hilos sobre la misma base primaria.

## Interoperabilidad

### ADR-007. ACL / Adaptadores (vs. Service Discovery)

**Por qué.** Cada proveedor llega con su propio contrato (JSON, XML, REST, SOAP) y el modelo interno no debe adoptarlo. Esto sostiene directamente `QA-INT-01` (menos de 2 semanas y un único módulo de frontera). También sostiene `QA-EVO-01`, porque un medio de transporte nuevo implementa el contrato interno (`IProveedorInventario`) en vez de tocar el orquestador. Service Discovery no resuelve el problema.

**Qué se paga:**

- Una capa de traducción, con costo de CPU despreciable frente a la red.
- Un modelo canónico que puede quedar en el mínimo común denominador entre proveedores.
- Un adaptador por contraparte para mantener.
- Los adaptadores corren en el mismo proceso que el orquestador, así que uno lento o roto puede agotar los hilos compartidos. Falta aislarlos (bulkhead).

### ADR-008. API Gateway (vs. Service Discovery)

**Por qué.** `CON-01` obliga a servir web y móvil, y el gateway concentra en un solo lugar la validación de sesión, el enrutamiento y la caché de borde (ADR-005). Sin él, ambos clientes duplicarían esa lógica y quedaría expuesto el tier de negocio. También es el lugar natural para limitar tasa frente a ráfagas como `QA-SEG-01`.

**Qué se paga:**

- **Punto único de falla:** se mitiga con una copia que toma el control, la misma táctica que ADR-002.
- **Un hop más** dentro del presupuesto de 800 ms.
- **Validación de sesión por request:** hoy consulta al módulo de registro y a la base, lo cual es un punto caliente con 250.000 concurrentes. Tokens firmados validados en el gateway lo aliviarían.

**Alternativa que no se evaluó.** Un gateway por cliente (BFF). Podría servir al móvil en 3G con payloads más livianos (`QA-PER-03`, `QA-USA-01`), a costa de mantener dos gateways.

### ADR-013. Service Discovery (rechazado)

Con un único gateway y un clúster detrás de un balanceador, los endpoints internos son estáticos. El balanceador ya hace de descubrimiento del lado del servidor, así que el componente solo sumaría infraestructura. **Cuándo reabrirlo:** si se migra a microservicios (ADR-009) o si el autoescalado de los picos crea instancias con direcciones dinámicas que el balanceador no cubra.

## Observaciones transversales

- **Listas de opciones mezcladas.** ADR-002, 003 y 010 comparan tácticas de categorías distintas (detección vs. recuperación). El rechazo de Heartbeat se entiende, pero no es un trade-off real contra Redundant spare. Conviene comparar dentro de la misma categoría.
- **Drivers fuera del goal.** `QA-DIS-01` se cita en ADR-002/003/004/010 pese a estar fuera del goal. Los drivers que sí justifican el clúster son `QA-PER-02` y `QA-ESC-01`.
- **Estilos rechazados sin sus escenarios.** ADR-009 y 011 no nombran `QA-INT-01`, `QA-INT-02` ni `QA-EVO-01`, que son lo que se resigna al descartarlos. Nombrarlos hace el trade-off honesto y deja claro cuándo reabrir la decisión.
- **Riesgos sin mitigación escrita.** El ping en el camino crítico, la caché sin TTL y la validación de sesión por request.
