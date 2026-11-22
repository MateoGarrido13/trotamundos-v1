# Interoperabilidad: Adhere to standards

* **Estado:** rechazado
* **Fecha:** 2026-10-28
* **Decisores:** Ramiro Rossi

## Contexto y Declaración del Problema
Se evaluó resolver la integración con proveedores adhiriendo a estándares de interfaz, para reducir la distancia entre los componentes y simplificar la traducción.

## Impulsores de la Decisión (Decision Drivers)
* `QA-INT-01`: la API del hotel nuevo es propietaria.
* Las APIs de los proveedores (Booking y otros) no las controlamos.
* Requisito general del TPE de interoperar por APIs estándar donde existan.

## Opciones Consideradas
* Opción 1: Capa Anti-Corrupción y adaptadores por proveedor ([ADR-007](../ITERACION_1/ADR-007.md), [ADR-IT3-004](ADR-IT3-004.md)).
* Opción 2: Adhere to standards: exigir o adoptar estándares de interfaz para toda integración.

## Resultado de la Decisión
Opción elegida: **"Opción 1: ACL y adaptadores"**, y se rechaza adherir a estándares como táctica de esta iteración, porque casi no aplica: las APIs de los proveedores son propietarias y no podemos imponerles un estándar. Donde un proveedor exponga uno, su adaptador lo aprovechará dentro del propio módulo.

### Consecuencias Positivas (Beneficios)
* El diseño no depende de que los proveedores adopten un estándar.
* La traducción queda concentrada en cada adaptador.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Se mantiene el costo de escribir y mantener un adaptador por proveedor.
* No se reduce la distancia entre componentes ni se simplifica la traducción en los casos en que un estándar existiría.
