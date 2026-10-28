---
name: skill-sketch
description: >-
  Dibuja una vista arquitectónica informal por vez (contexto, módulos,
  componentes y conectores, asignación, secuencia) en Mermaid y la registra
  en el paso 6 de la iteración ADD. Consulta el catálogo, verifica la
  información, pregunta y escribe solo cuando el usuario aprueba. Usar cuando
  el usuario invoca /skill-sketch o skill-sketch e indica el archivo de la
  iteración.
disable-model-invocation: true
---

# skill-sketch

Dibuja sketch-views y las registra en el paso 6. Una vista por vez, en el mismo chat. Sin aprobación no se escribe.

NO INFIERAS INFORMACION QUE NO SE ESPECIFICO, EN ESOS CASOS PREGUNTAR AL USUARIO CON POSIBLES DATOS

## Fuentes

Al invocar, leer solo:

1. El markdown de iteración que el usuario nombró.
2. Esta skill. El catálogo de vistas es el de abajo.
3. `LISTADO_DRIVERS.md` solo para comprobar un rótulo antes de ponerlo en el diagrama. No editarlo.

Si el usuario no nombra un archivo, preguntar cuál es. No elegir uno. Una iteración por invocación.

## Antes de consultar

El archivo tiene que tener el paso 5 con contenido propio (tablas o prosa), no la plantilla vacía.

Si el paso 5 no está completo, decirlo y terminar. No preguntar el catálogo ni dibujar.

## Catálogo de vistas

Solo estas cinco:

1. Contexto
2. Módulos
3. Componentes y conectores
4. Asignación
5. Secuencia

Una vista fuera de esta lista no se dibuja. Repetir el catálogo y esperar otro nombre.

## Flujo

1. El usuario llama con `/skill-sketch` y el archivo markdown de la iteración, que ya tiene completo el paso 5.
2. La skill consulta qué vistas quiere del catálogo especificado.
3. El usuario indica qué vistas quiere.
4. La skill verifica si tiene la información suficiente. Si no, se mantiene en este paso y consulta.
5. La skill tiene la información suficiente, hace la sketch-view y le pregunta al usuario.
6. El usuario aprueba, o rechaza con las especificaciones y se vuelve al paso 5.
7. Si se aprueba, se pasa a la siguiente indicada. Si no hay más indicadas, finaliza.

Si el mensaje de invocación ya nombra las vistas, ese mensaje es el paso 3. No volver a preguntar el catálogo. Seguir el orden en que las nombró.

Con una vista en curso, no adelantar la siguiente.

Aprobación: el mensaje aprueba la vista mostrada y no pide cambios. Cuentan `aprobada`, `apruebo` y `OK`.

Rechazo: cualquier otro mensaje. Aplicar solo las especificaciones que escribió. Volver a verificar. Si falta algo, permanecer en el paso 4 y consultar. Si alcanza, rehacer esa vista y volver a preguntar. Un rechazo sin especificaciones no se redibuja: preguntar qué hay que cambiar.

No registrar la vista si el mensaje aprueba y a la vez pide un cambio. Eso es un rechazo.

## Información suficiente

Cada ítem tiene que estar escrito en el archivo o en este chat. Transcribir vale. Un hueco detiene el dibujo.

**Contexto.** El sistema como una sola caja. Cada actor y cada sistema externo, con nombre. Cada flecha, con origen, destino y el flujo. Ningún elemento interno del paso 5 entra en esta vista.

**Módulos.** Los elementos de código que van en la vista. Cada flecha, con una relación estática dicha en las fuentes (`importa`, `implementa`, `depende`). Sin instancias de ejecución ni protocolos de red.

**Componentes y conectores.** Los componentes de ejecución, con nombre. Cada conector, con el protocolo escrito en las fuentes y con síncrono o asíncrono. Cuáles son del sistema y cuáles externos.

**Asignación.** Cada artefacto junto al nodo en el que se despliega, los dos nombrados. Las zonas y las rutas de red solo si las fuentes las nombran.

**Secuencia.** Los participantes. Los mensajes en orden, con emisor y receptor. Si el paso 5 tiene más de una secuencia, cuál de ellas es esta vista. Las llamadas externas, distinguibles. El sincronismo y los retornos solo donde la fuente los marca.

## Posibles datos

Preguntar por cada ítem que falte. Un posible dato sale de una celda o una frase del archivo, o de una frase de este chat, y hay que decir de cuál.

Si no hay fuente, hacer la pregunta abierta y decir que no hay un posible dato. No ofrecer un protocolo, un nodo, una zona, una tecnología ni una flecha que no esté escrita.

Un posible dato no entra en el dibujo hasta que el usuario lo acepta.

No citar un rótulo que no esté en `LISTADO_DRIVERS.md`. Si el texto trae un escenario, caso de uso, concern o restricción fuera de ese listado, preguntar. No ponerlo en la vista.

## Cómo se dibuja

Solo Mermaid. Un diagrama por vista. Sin ASCII ni prosa en lugar del diagrama.

La leyenda va dentro del diagrama: un subgrafo `Leyenda`, con un nodo de texto por cada forma usada y otro por cada tipo de línea usado. La línea continua y la punteada se usan cuando la fuente ya dijo qué distingue (síncrono o asíncrono, depende, fluye, llama). No elegir ese significado para tapar un hueco.

El sistema va en un subgrafo con el nombre que trae el archivo. Los sistemas externos quedan afuera. En una secuencia no hay subgrafo: los externos se nombran como en la fuente y la leyenda los lista. La leyenda de la secuencia es una nota sobre el primer participante.

## Registro

Al aprobar, escribir esa vista en el paso 6 del mismo archivo, bajo `## Paso 6. Bosquejar y registrar la decisión`. Crear el paso 6 antes del paso 7 si no existe. No borrar el paso 7 ni el catálogo de decisiones.

Cada vista queda así, antes del catálogo de decisiones:

```markdown
### [Nombre de la vista]

Estructura:

```mermaid
```

Leyenda:

- Recuadros: …
- Flechas: …
- Frontera: …
```

`Leyenda` repite, con las mismas palabras, la leyenda que está dentro del Mermaid. Si el paso 6 todavía tiene el bloque Mermaid vacío de la plantilla, la primera vista lo reemplaza. Si ya hay una subsección con el mismo nombre de vista, reemplazarla.

Volver a leer el fragmento y comprobar que coincide con la vista aprobada.

Después seguir con la siguiente vista indicada, desde la verificación. Si no falta información, mostrar esa sketch-view y preguntar. Si no hay más vistas, terminar y decir cuáles quedaron en el paso 6. No ofrecer una vista que el usuario no indicó.

## Ejemplo de una consulta

El usuario pidió Componentes y conectores. El paso 5 nombra el enlace y no dice el protocolo.

```markdown
Vista 1 de 2. Componentes y conectores.

Falta especificar:
1. Protocolo del enlace entre el gateway y el balanceador. No hay un posible dato en las fuentes. ¿Cuál es?
2. Ese enlace, ¿es síncrono o asíncrono? No hay un posible dato en las fuentes.

No dibujo esta vista hasta que esos puntos estén especificados.
```
