# Interoperabilidad: Configure behavior (conector parametrizable por proveedor)

* **Estado:** rechazado
* **Fecha:** 2026-10-28
* **Decisores:** Yaco Recroa

## Contexto y Declaración del Problema
Para integrar proveedores nuevos se evaluó un conector genérico parametrizado por configuración (por proveedor o por versión de API), en lugar de escribir un adaptador para cada uno.

## Impulsores de la Decisión (Decision Drivers)
* `QA-INT-01`: un hotel nuevo con API propietaria en menos de 2 semanas y en un único módulo.
* Las APIs propietarias difieren en protocolo, formato y semántica, no solo en parámetros.
* Mantener la ACL de la iteración 1 ([ADR-007](../ITERACION_1/ADR-007.md)).

## Opciones Consideradas
* Opción 1: Un adaptador propio por proveedor, que implementa `IProveedor` ([ADR-IT3-004](ADR-IT3-004.md)).
* Opción 2: Configure behavior: un conector genérico parametrizado por proveedor o versión.

## Resultado de la Decisión
Opción elegida: **"Opción 1: un adaptador propio por proveedor"**, y se rechaza el conector parametrizable, porque cada proveedor ya es un adaptador propio y las diferencias entre APIs propietarias superan lo que se expresa con parámetros. Parametrizar sumaría configuración y casos de prueba sin evitar el módulo.

### Consecuencias Positivas (Beneficios)
* Cada API queda aislada en su módulo, sin condicionales por proveedor.
* Los cambios de un proveedor no afectan a otros.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Algo de duplicación entre adaptadores y más módulos para mantener.
* No se dispone de alta de proveedores solo por configuración: cada uno exige código y despliegue.
