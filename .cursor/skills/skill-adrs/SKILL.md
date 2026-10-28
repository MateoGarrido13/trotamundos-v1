---
name: skill-adrs
description: >-
  Registra en el markdown de una iteración ADD, con los pasos completos hasta
  el 5, las ADR confirmadas bajo el formato de ADR_TEMPLATE.md. Una ADR por
  vez: pregunta lo no especificado, ofrece posibles datos y escribe en el
  mismo archivo solo cuando el usuario responde "OK ADR". Usar cuando el
  usuario invoca /skill-ADRs o skill-ADRs e indica el archivo de la iteración.
disable-model-invocation: true
---

# skill-ADRs

Registra ADR en el archivo de la iteración. Una por vez. Sin confirmación no se escribe.

NO INFIERAS INFORMACION QUE NO SE ESPECIFICO, EN ESOS CASOS PREGUNTAR AL USUARIO CON POSIBLES DATOS

## Fuentes

Al invocar, leer solo:

1. El markdown de iteración que el usuario nombró.
2. `ADR_TEMPLATE.md` en la raíz del repositorio. El formato de cada ADR es el de ese archivo.
3. `LISTADO_DRIVERS.md` solo para comprobar un rótulo antes de citarlo. No editarlo.

Si el usuario no nombra un archivo, preguntar cuál es. No elegir uno por su cuenta. Una iteración por invocación.

## Antes de detectar

El archivo tiene que tener los pasos 2, 3, 4 y 5 con contenido propio (tablas o prosa), no la plantilla vacía. El paso 1 puede estar en ese archivo o en `README.md`.

Si falta alguno de los pasos 2 a 5, decir cuál falta y terminar. No armar una cola de ADR.

## Qué cuenta como ADR

Una ADR es una elección explícita. Detectarla en el archivo y en este chat. No fabricar una elección a partir de un driver, un goal o una responsabilidad.

Entran en la cola, en este orden:

1. **Paso 4.** Cada fila cuya columna `Queda` afirma la elección (`sí`, `queda`, `elegida` u otra marca explícita). El nombre de esa alternativa es la opción elegida. Las otras filas son opciones consideradas solo si el propio paso dice que son alternativas de la misma decisión. Si la tabla mezcla decisiones y no dice cómo agruparlas, preguntar el agrupamiento antes de redactar.
2. **Paso 5.** Una frase que elige (`se elige`, `se asigna`, `la interfaz es`) y que no es la instanciación de una fila ya encolada del paso 4. Si solo asigna responsabilidades y no hay alternativa descartada, preguntar si es una ADR. No encolarla en silencio.
3. **Este chat.** Una frase del usuario que decide (`decidimos`, `vamos con`, `la ADR es`) y que todavía no está en el archivo.

Saltar lo que ya está registrado en el archivo como ADR (mismo título o la misma opción en `Resultado de la Decisión`).

Si no hay ninguna, decirlo y preguntar qué decisión registrar. No proponer una decisión nueva.

## Campos

Copiar la estructura de `ADR_TEMPLATE.md`. El título de la iteración sigue siendo el único `#`. Cada ADR va como:

```markdown
## ADR-NNN. [Título]

* **Estado:** …
* **Fecha:** YYYY-MM-DD
* **Decisores:** …

## Contexto y Declaración del Problema
…

## Impulsores de la Decisión (Decision Drivers)
* …

## Opciones Consideradas
* Opción 1: …

## Resultado de la Decisión
Opción elegida: **"…"**, porque …

### Consecuencias Positivas (Beneficios)
* …

### Consecuencias Negativas (Trade-offs / Riesgos)
* …
```

`NNN` sigue al mayor `ADR-NNN` ya presente en el archivo. Si no hay, empieza en `ADR-001`.

Un campo se llena solo si el texto está en el archivo o en este chat, y se copia. Transcribir celdas vale: `Beneficia` y `Perjudica` de la fila elegida pueden ser consecuencias; los ids del goal o de esa fila pueden ser impulsores, citados con su rótulo de `LISTADO_DRIVERS.md`.

No rellenar para llegar a tres opciones. Las que no estén escritas no existen todavía.

Un campo sin texto queda `[sin especificar]`. No usar la fecha de hoy, `aceptado`, nombres del repositorio ni un trade-off verosímil para tapar el hueco.

## Posibles datos

Preguntar por cada campo `[sin especificar]`. Un posible dato tiene que salir de una de estas tres fuentes, y hay que decir de cuál:

- una celda o frase del archivo de la iteración, o una frase de este chat
- el enum de estado de `ADR_TEMPLATE.md`: `propuesto`, `aceptado`, `rechazado`, `obsoleto`, `reemplazado por ADR-XXX`
- la fecha de hoy, únicamente para el campo Fecha

Si no hay fuente, hacer la pregunta abierta y decir que no hay un posible dato. No ofrecer una tecnología, un patrón, un beneficio ni un riesgo que no esté ya escrito.

Un posible dato no queda escrito en el borrador hasta que el usuario lo acepta.

No citar un rótulo que no esté en `LISTADO_DRIVERS.md`. Si el texto trae un escenario, caso de uso, concern o restricción fuera de ese listado, preguntar. No incorporarlo como impulsor.

## Flujo

1. El usuario llama con `/skill-ADRs` y menciona el archivo de la iteración.
2. Por cada ADR detectada en el chat, mostrar el borrador completo y quedar a la espera. No registrar todavía.
3. El usuario confirma con `OK ADR` y se continúa con la siguiente ADR detectada, o pide modificaciones y se vuelve al paso 2.
4. Cuando todas las ADR detectadas están registradas, terminar.

`OK ADR` es esa frase, con mayúsculas o minúsculas, sola o con espacios alrededor. Cualquier otro mensaje es una modificación: cambiar solo lo que el usuario dijo, volver a preguntar lo que siga sin especificar y mostrar el borrador de nuevo.

No escribir la ADR si queda un `[sin especificar]`, aunque el mensaje diga `OK ADR`. Repetir las preguntas.

Al recibir `OK ADR` con el borrador completo:

- Escribir esa ADR en el mismo archivo, al final, bajo `## ADRs`. Crear la sección si no existe. No borrar los pasos 6 ni 7 si ya están.
- Volver a leer el fragmento escrito y comprobar que coincide con el borrador confirmado.
- Presentar la siguiente de la cola.

No abrir una segunda detección al terminar. Una decisión nueva solo entra si el usuario la enuncia después.

## Ejemplo de un turno

El paso 4 dice que queda «API por viaje» y perjudica la operación. No hay fecha ni decisores.

```markdown
## ADR-001. API por viaje

* **Estado:** [sin especificar]
* **Fecha:** [sin especificar]
* **Decisores:** [sin especificar]

## Contexto y Declaración del Problema
[párrafo copiado del paso 2 o del paso 4]

## Impulsores de la Decisión (Decision Drivers)
* `CON-02` — [texto copiado de la celda]

## Opciones Consideradas
* Opción 1: API por viaje

## Resultado de la Decisión
Opción elegida: **"API por viaje"**, porque [sin especificar].

### Consecuencias Positivas (Beneficios)
* [sin especificar]

### Consecuencias Negativas (Trade-offs / Riesgos)
* [texto copiado de la celda Perjudica]

Falta especificar:
1. Estado. Posibles datos, del enum de ADR_TEMPLATE.md: propuesto, aceptado, rechazado, obsoleto, reemplazado por ADR-XXX.
2. Fecha. Posible dato: YYYY-MM-DD (hoy). ¿Es la fecha de la decisión?
3. Decisores. No están en el archivo ni en el chat. ¿Quiénes deciden?
4. El porque. No hay justificación escrita. ¿Cuál es?
5. Beneficios. No hay un posible dato en las fuentes. ¿Cuáles se registran?

No registro esta ADR hasta que esos campos estén especificados y confirmes con "OK ADR". Si querés cambiar algo del borrador, decilo y lo rehago.
```
