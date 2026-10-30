# Aplicar Reconfiguration para delegar la carga en la Base pasiva cuando cae la Base primaria

* **Estado:** aceptado
* **Fecha:** 2026-10-28
* **Decisores:** Mateo Garrido

## Contexto y Declaración del Problema
Aun con las copias sincronizadas por el ADR-IT2-004, la caída de la Base primaria dejaría al sistema sin poder atender las escrituras. El sistema es de uso global, debe estar accesible en todo momento y tolera como máximo 5 minutos de inactividad no planificada por mes. Hay que definir qué táctica reasigna la carga a la copia viva.

## Impulsores de la Decisión (Decision Drivers)
* `QA-DIS-01`: si cae el nodo principal, la carga debe delegarse para seguir atendiendo peticiones.
* Menos de 5 minutos de inactividad al mes.
* Ya existe una Base pasiva (*Redundant spare*) con estado consistente gracias al commit en dos fases.

## Opciones Consideradas
* Opción 1: Reconfiguration: reasignar responsabilidades a los recursos que siguen funcionando; el JDBC de Orquestador de viajes pasa a Base pasiva.
* Opción 2: Recuperación manual de la Base primaria (intervención operativa).
* Opción 3: Graceful degradation solamente (modo solo lectura sin promover la pasiva).

## Resultado de la Decisión
Opción elegida: **"Opción 1: Reconfiguration"**, porque aprovecha la copia pasiva ya sincronizada para seguir atendiendo escrituras sin esperar la recuperación de la primaria, acotando la inactividad dentro del presupuesto mensual. La recuperación manual (Opción 2) no garantiza el tiempo, y degradar a solo lectura (Opción 3) sacrifica una función crítica.

Detalle: cuando Base primaria deja de atender, el JDBC de Orquestador de viajes conmuta a Base pasiva, que pasa a ser la copia que atiende. El traspaso no es inmediato. El mecanismo concreto de detección de la caída y de promoción debe definirse en una iteración posterior de detalle.

### Consecuencias Positivas (Beneficios)
* El sistema sigue atendiendo peticiones ante la caída del nodo principal.
* Respeta el presupuesto de 5 minutos al mes siempre que el traspaso sea breve.
* Reutiliza la redundancia y la sincronización ya decididas.

### Consecuencias Negativas (Trade-offs / Riesgos)
* El traspaso no es inmediato: se paga en latencia durante la conmutación.
* La función que no puede reasignarse se sacrifica en disponibilidad durante ese lapso.
* Tras la conmutación no queda otra copia pasiva hasta restaurar un nuevo respaldo; riesgo de falla doble.
* Riesgo de *split-brain* si no se define con precisión cómo se detecta la caída y se evita que la primaria vuelva a aceptar escrituras.
