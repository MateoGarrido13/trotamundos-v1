# Trotamundos — iteración 2


| Campo                       | Valor                                                                                                                               |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Ronda**                   | 1                                                                                                                                   |
| **Arranque**                | Refinamiento. Se retoma el Core de la iteración 1 en los drivers que quedaron parciales.                                            |
| **Qué toma esta iteración** | La especificación de la caché y de la interacción con las APIs, y la sincronización de las copias ante la caída del nodo principal. |


El paso 1 de la ronda está en [README.md](README.md). El cierre de la iteración anterior está en [ITERACION_1.md](ITERACION_1.md).

## Paso 2. Establecer el goal


| Id           | En el goal o afuera                                                                                                                                                                                                                                           |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `QA-PER-02`  | En el goal. Nueva cotización desde la web, en 800 ms para el 90 % de las peticiones. Se especifica el uso de la caché y la interacción con las APIs: ante una cota de tiempo, la caché entrega una respuesta por defecto.                                     |
| `QA-PER-03`  | En el goal. El usuario abre la aplicación móvil y el primer contenido aparece en menos de 1,4 s en el 90 % de las sesiones. Esa misma caché entrega la respuesta por defecto ante la cota de tiempo.                                                          |
| `QA-ESC-01`  | Afuera. Sigue parcial y queda para otra iteración. Registro masivo de 100.000 usuarios nuevos por día.                                                                                                                                                        |
| `REF-02`     | Afuera. Sondear el correo y agregar al itinerario las reservas de los mensajes de viaje.                                                                                                                                                                      |
| `REF-03`     | Afuera. Filtrar y armar whitelists de remitentes de correos de viaje.                                                                                                                                                                                         |
| `REF-04`     | Afuera. Agregar, actualizar o eliminar una reserva a mano.                                                                                                                                                                                                    |
| `REF-05`     | Afuera. Resolver un problema con la agencia de viajes preferida.                                                                                                                                                                                              |
| `REF-06`     | Afuera. Consultas analíticas de tendencias, destinos y cancelaciones.                                                                                                                                                                                         |
| `QA-PER-01`  | Afuera. Actualización de una API externa.                                                                                                                                                                                                                     |
| `QA-INT-01`  | Afuera. Integrar la API propietaria de una cadena hotelera nueva.                                                                                                                                                                                             |
| `QA-PER-04*` | Afuera. Consulta de tendencias, destinos y cancelaciones.                                                                                                                                                                                                     |
| `QA-DIS-01`  | En el goal. Caída de un nodo de cotización. La sincronización de las copias prioriza la consistencia por sobre la performance en latencia. Si cae el nodo principal, la carga se delega con la táctica Reconfiguration para seguir atendiendo las peticiones. |
| `QA-INT-02`  | Afuera. Incorporar Instagram como canal de propuestas e itinerarios.                                                                                                                                                                                          |
| `QA-SEG-01`  | Afuera. Ráfaga de recuperación de contraseña.                                                                                                                                                                                                                 |
| `QA-SEG-02`  | Afuera. Registrar una actividad en el itinerario compartido.                                                                                                                                                                                                  |
| `QA-SEG-03*` | Afuera. El titular autoriza la lectura de su correo.                                                                                                                                                                                                          |
| `QA-EVO-01`  | Afuera. Integrar un medio de transporte que el panel todavía no agrupa.                                                                                                                                                                                       |
| `QA-USA-01`  | Afuera. El viajero consulta su viaje en el móvil, con una capacidad nativa como el GPS.                                                                                                                                                                       |


**Drivers ya resueltos:** `REF-01`, `CON-01`, `CON-02`.

**Goal.** El objetivo de esta iteración es especificar el uso de la caché y la interacción con las APIs para la cotización web (`QA-PER-02`) y para el primer contenido del móvil (`QA-PER-03`). Ante una cota de tiempo, la caché entrega una respuesta por defecto. Una cotización nueva responde en 800 ms para el 90 % de las peticiones. Al abrir la aplicación móvil, el primer contenido aparece en menos de 1,4 s en el 90 % de las sesiones. En la sincronización de las copias, que la iteración 1 dejó propuesta, el trade-off prioriza la consistencia por sobre la performance en latencia (`QA-DIS-01`). Si cae el nodo principal, la carga se delega aplicando la táctica Reconfiguration, de modo que el sistema siga atendiendo las peticiones y el servicio acumule menos de 5 minutos de inactividad al mes.

Los pasos siguen el orden del método: este paso fija el goal y el paso 3 elige el elemento a refinar.

## Paso 3. Elegir los elementos a refinar


| Elemento                                                                  | Por qué este                                                                                                                                                                                                                                                                                                | Movimiento |
| ------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| Caché de borde (CDN)                                                      | Está en el camino de Cliente web y de Cliente móvil, antes del API Gateway. Ahí se especifica la respuesta por defecto cuando se alcanza la cota de tiempo: la grilla de la cotización (`QA-PER-02`) y el primer contenido del móvil (`QA-PER-03`). El conector hacia el API Gateway es el de cache miss.   | Refinar    |
| Orquestador de viajes                                                     | En el cache miss la cotización llega a este componente, que dispara en paralelo al Adaptador de aerolíneas, al Adaptador de hoteles y al Adaptador de arrendadoras. La interacción con las APIs de la cotización se coordina aquí, dentro de la cota de `QA-PER-02`.                                        | Refinar    |
| Adaptador de aerolíneas, Adaptador de hoteles y Adaptador de arrendadoras | Son el lado interno de la llamada síncrona a API Proveedor 2 (SOAP), API de hoteles y API de arrendadoras. La cota de espera de cada API se fija en estos adaptadores (`QA-PER-02`).                                                                                                                        | Refinar    |
| Base primaria y Base pasiva                                               | Son las copias del nivel de datos. El conector entre ellas es TCP / replicación binaria continua, asíncrono. Esta iteración fija ese intercambio priorizando la consistencia por sobre la performance en latencia y, si cae la primaria, la reconfiguración que delega la carga en la pasiva (`QA-DIS-01`). | Refinar    |


Se refinan esos componentes de [vistas/C&C_VIEW_IT1.svg](vistas/C&C_VIEW_IT1.svg). Cliente web y Cliente móvil originan los estímulos. API Gateway y Balanceador de Carga encaminan. Módulo de registro queda para `QA-ESC-01`. API Proveedor 2 (SOAP), API de hoteles y API de arrendadoras están fuera de la frontera de Trotamundos.

## Paso 4. Elegir los conceptos de diseño

En esta iteración evaluamos las tácticas que quedaron abiertas de la Iteración 1 y los nuevos conceptos propuestos, enfocados en resolver los *drivers* específicos del *goal*: la cota de tiempo en la caché para la cotización y el móvil (`QA-PER-02`, `QA-PER-03`), la interacción con las APIs de terceros, y el mecanismo de sincronización priorizando la consistencia ante caídas (`QA-DIS-01`).


| Alternativa               | Tipo                     | Beneficia                                                                                                                                                                   | Perjudica                                                                                                                                                      | Queda |
| ------------------------- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- |
| Heartbeat                 | Táctica (disponibilidad) | El componente vigilado emite mensajes periódicos a un monitor.                                                                                                              | El componente a vigilar (API del proveedor) es externo y no está a nuestro alcance modificarlo para emitir latidos. Se paga en Performance(Latencia).         | No    |
| Bound execution times     | Táctica (performance)    | Pone un techo al tiempo de procesamiento. Al alcanzar esa cota, la caché entrega una respuesta por defecto asegurando cumplir los 800 ms y 1.4s (`QA-PER-02`, `QA-PER-03`). | Se sacrifica la exactitud del cómputo. La respuesta por defecto puede quedar desactualizada y se perjudica la Consistencia de los datos.                       | Sí    |
| Retry                     | Táctica (disponibilidad) | Si el silencio de una API es transitorio, repetir el pedido puede tener éxito, con un límite de reintentos.                                                                 | Un timeout largo se paga en Performance(Latencia). Uno corto saca de la grilla una API que aún podía responder y se perjudica la Disponibilidad de ese origen. | No    |
| Transactions              | Táctica (disponibilidad) | Agrupa las actualizaciones de las dos copias para que el intercambio sea atómico, consistente, aislado y durable (`QA-DIS-01`).                                             | El commit en dos fases retiene la escritura hasta que Base primaria y Base pasiva acuerdan. Se paga fuertemente en Performance(Latencia).                      | Sí    |
| Reconfiguration           | Táctica (disponibilidad) | Reasigna responsabilidades a los recursos que siguen funcionando. Si cae la Base primaria, la carga pasa a la Base pasiva y el sistema sigue atendiendo (`QA-DIS-01`).       | El traspaso de la carga no es inmediato: se paga en Performance(Latencia). La función que no puede reasignarse se sacrifica en Disponibilidad.                 | Sí    |
| Graceful degradation      | Táctica (disponibilidad) | Ante la falla de una API o de un nodo se sostienen las funciones críticas y se sueltan las que no lo son (`QA-PER-02`, `QA-DIS-01`).                                         | Se sacrifican las funciones no críticas. Se perjudica la completitud de la respuesta (`QA-PER-02`) a cambio de sostener la Disponibilidad.                     | Sí    |


**Tacticas incorporadas en la iteracion 1:**

- Redundant spare. Un componente duplicado toma el control si falla el primario (hot, warm o cold spare) (`QA-DIS-01`).
- State resynchronization. Mantiene sincronizado el estado entre el componente activo y el de respaldo (`QA-DIS-01`).
- Ping/Echo. El adaptador envía un ping a la API de su productor y el eco indica que esa API responde (`QA-PER-02`).
- Múltiples copias de datos (caché). Guarda cotizaciones previas y respuestas estáticas (`QA-PER-02`, `QA-PER-03`).
- Procesamiento concurrente (Scatter-Gather) con el Orquestador.
- Capa Anti-Corrupción (ACL) / Adaptadores (por API de proveedor).
- API Gateway.

**Justificación de la Selección:**

Para cumplir el *goal* de la iteración, se aceptan las tácticas de la Iteración 1 y se incorporan nuevas decisiones:

* **Bound execution times y Graceful degradation:** Se seleccionan conjuntamente para garantizar que la caché de borde devuelva una respuesta (la grilla por defecto) si el orquestador o las APIs exceden la cota de 800 ms o 1.4s (`QA-PER-02`, `QA-PER-03`). Se acepta la degradación de la respuesta (datos no actualizados en tiempo real) a cambio de cumplir estrictamente el atributo de Performance.

* **Transactions y Reconfiguration:** Para resolver el fallo del nodo principal (`QA-DIS-01`), el *goal* establece que se prioriza la consistencia sobre la latencia. Por ello, se elige *Transactions* (commit en dos fases) garantizando que la copia pasiva (*Redundant spare*) esté exactamente igual que la primaria (*State resynchronization*). Ante la caída, se dispara la táctica de *Reconfiguration* para mover la carga al nodo pasivo, logrando la recuperación en menos de 5 minutos.

* **Rechazo de Heartbeat:** Se descarta esta táctica debido a que el componente que se necesita vigilar (la API del proveedor) es externo al sistema y no está a nuestro alcance modificarlo para que emita latidos hacia nuestro monitor.

* **Rechazo de Retry:** Se descarta el *Retry* porque sumar intentos bloqueantes contra las APIs externas comprometería las estrictas cotas de latencia (800ms) de `QA-PER-02`. Es preferible degradar (*Graceful degradation*) y devolver lo que se tenga o la copia en caché.

Prototipo throwaway: ninguno por ahora.

## Paso 5. Instanciar, asignar y definir interfaces

Se instancian los elementos del paso 3. Cada uno recibe las tácticas que el paso 4 dejó en sí, más las de la iteración 1 que ese paso incorpora. Heartbeat y Retry no se asignan.

La cota de Bound execution times es la del goal: 800 ms en la cotización (`QA-PER-02`) y 1,4 s en el primer contenido del móvil (`QA-PER-03`). Los drivers no fijan en milisegundos la cota de espera de cada API; esa cota es de su adaptador.

### Caché de borde (CDN)


| Elemento             | Responsabilidad                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Interfaz                                                                                                                                                                                                                                                                                                                          |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Caché de borde (CDN) | Guarda copias de la grilla de una fecha, un hospedaje y una compañía, y del primer contenido del móvil (Múltiples copias de datos). Bound execution times pone la cota de 800 ms a la cotización y la de 1,4 s al primer contenido. Si la cota se alcanza antes de que llegue la respuesta fresca, Graceful degradation entrega la respuesta por defecto: la copia que ya tiene, aunque no esté actualizada (`QA-PER-02`, `QA-PER-03`). El cálculo fresco se sacrifica para cerrar dentro de la cota. | Desde Cliente web, por HTTPS REST: fecha, hospedaje y compañía. Hacia Cliente web: la grilla, o la copia por defecto si venció la cota de 800 ms. Desde Cliente móvil, por HTTPS REST: el primer contenido. Hacia Cliente móvil: ese contenido, o su copia por defecto si venció la cota de 1,4 s. Hacia el API Gateway: el conector de cache miss, con el mismo pedido. |


### Orquestador de viajes


| Elemento              | Responsabilidad                                                                                                                                                                                                                                                                                                                                                                                                                         | Interfaz                                                                                                                                                                                                                                                                                                                                                                                                                    |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Orquestador de viajes | En el cache miss coordina la cotización. Scatter-Gather dispara en paralelo la consulta a Adaptador de aerolíneas, Adaptador de hoteles y Adaptador de arrendadoras. Graceful degradation arma la grilla con los orígenes que respondieron y suelta los que no (`QA-PER-02`). La función que se sostiene es devolver la grilla; la que se suelta es la completitud de todos los orígenes. | Desde el Balanceador de Carga: fecha, hospedaje y compañía. Hacia los tres adaptadores, en paralelo: el llamado asíncrono del contrato interno de cada uno. Hacia el API Gateway, de regreso: la grilla consolidada, completa o parcial. Hacia la base que atiende las escrituras, por JDBC: la escritura de viajes. Tras la reconfiguración, esa base es la Base pasiva. |


### Adaptador de aerolíneas, Adaptador de hoteles y Adaptador de arrendadoras

Cada adaptador es la Capa Anti-Corrupción de su API. Traduce el contrato del proveedor al modelo interno. Ping/Echo sale de ese adaptador hacia su API. Con eco, pide el precio por la misma llamada síncrona. Bound execution times corta esa espera en la cota del adaptador. Sin eco, o vencida la cota, el adaptador informa a Orquestador de viajes que ese origen no respondió y el pedido de precio no sigue. Retry no se usa.


| Elemento                  | Responsabilidad                                                                                                                                                                      | Interfaz                                                                                                                                                                                                                                                            |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Adaptador de aerolíneas   | ACL, Ping/Echo y la cota de espera contra API Proveedor 2 (SOAP) (`QA-PER-02`).                                                                                                      | Interna: el contrato que invoca Orquestador de viajes. Externa, síncrona: SOAP hacia API Proveedor 2 (SOAP). Desde esa API: el eco y el precio, o el silencio una vez vencida la cota. Hacia Orquestador de viajes: el precio traducido, o el aviso de que el origen no respondió. |
| Adaptador de hoteles      | ACL, Ping/Echo y la cota de espera contra API de hoteles (`QA-PER-02`).                                                                                                              | Interna: `ICotizadorHotel`, invocado por Orquestador de viajes. Externa, síncrona: hacia API de hoteles. Desde esa API: el eco y el precio, o el silencio una vez vencida la cota. Hacia Orquestador de viajes: el precio traducido, o el aviso de que el origen no respondió.      |
| Adaptador de arrendadoras | ACL, Ping/Echo y la cota de espera contra API de arrendadoras (`QA-PER-02`).                                                                                                         | Interna: el contrato que invoca Orquestador de viajes. Externa, síncrona: hacia API de arrendadoras. Desde esa API: el eco y el precio, o el silencio una vez vencida la cota. Hacia Orquestador de viajes: el precio traducido, o el aviso de que el origen no respondió.         |


### Base primaria y Base pasiva

Base pasiva es el Redundant spare de Base primaria. State resynchronization queda en Transactions: el commit en dos fases. La escritura se retiene hasta que las dos copias acuerdan, y la consistencia queda por encima de la latencia (`QA-DIS-01`). Si Base primaria deja de atender, Reconfiguration delega la carga en Base pasiva. El traspaso no es inmediato. El servicio acumula menos de 5 minutos de inactividad al mes.


| Elemento                      | Responsabilidad                                                                                                                                                                                                                                                                                                           | Interfaz                                                                                                                                                                                                                                                                                                                                                                   |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Base primaria y Base pasiva   | Base primaria atiende las escrituras y Base pasiva es la copia de respaldo (Redundant spare). Transactions confirma la escritura en las dos copias antes de devolver éxito (State resynchronization). Reconfiguration pasa la carga a Base pasiva cuando Base primaria deja de atender (`QA-DIS-01`).                    | Desde Orquestador de viajes, por JDBC: la escritura, hacia la copia que atiende. Entre Base primaria y Base pasiva, por el conector TCP: el commit en dos fases. Base primaria retiene la escritura hasta que Base pasiva acuerda. Cuando Base primaria deja de atender, ese JDBC pasa a Base pasiva. |


### Relaciones permitidas

- Cliente web y Cliente móvil → Caché de borde (CDN).
- Caché de borde (CDN) → API Gateway, por el conector de cache miss.
- API Gateway → Balanceador de Carga → Orquestador de viajes.
- Orquestador de viajes → Adaptador de aerolíneas, Adaptador de hoteles y Adaptador de arrendadoras, en paralelo.
- Adaptador de aerolíneas → API Proveedor 2 (SOAP).
- Adaptador de hoteles → API de hoteles.
- Adaptador de arrendadoras → API de arrendadoras.
- Orquestador de viajes → Base primaria, por JDBC.
- Base primaria → Base pasiva, por TCP, con el commit en dos fases.
- Si Base primaria deja de atender, el JDBC de Orquestador de viajes pasa a Base pasiva.

### Secuencia

**Cotización desde la web** (`QA-PER-02`). Cliente web envía fecha, hospedaje y compañía a Caché de borde (CDN). Caché de borde (CDN) abre la cota de 800 ms. Si tiene la grilla de esos criterios, la devuelve. Si no, el cache miss sigue al API Gateway y el Balanceador de Carga entrega el pedido a Orquestador de viajes. Orquestador de viajes pide el precio a la vez a Adaptador de aerolíneas, Adaptador de hoteles y Adaptador de arrendadoras. Cada uno hace Ping/Echo a su API. Con eco, pide el precio. Si API Proveedor 2 (SOAP) calla vencida la cota de Adaptador de aerolíneas, ese adaptador avisa que el origen no respondió. Orquestador de viajes arma la grilla con lo que devolvieron Adaptador de hoteles y Adaptador de arrendadoras. Si esa grilla llega antes de los 800 ms, Caché de borde (CDN) la guarda y la entrega a Cliente web. Si la cota vence antes, entrega la copia que ya tiene.

**Apertura del móvil** (`QA-PER-03`). Cliente móvil pide el primer contenido a Caché de borde (CDN). Caché de borde (CDN) abre la cota de 1,4 s. Si tiene la copia, la sirve. Si la cota vence antes de que el contenido llegue, entrega la copia que ya tiene de ese primer contenido.

**Caída de Base primaria** (`QA-DIS-01`). Orquestador de viajes escribe en Base primaria por JDBC. Base primaria no confirma hasta que Base pasiva acuerda, por el commit en dos fases sobre TCP. Si Base primaria deja de atender, Reconfiguration delega la carga en Base pasiva. El traspaso no es inmediato. La copia que pasa a atender es Base pasiva, y el servicio acumula menos de 5 minutos de inactividad al mes.
