# Interoperabilidad: Abstract common services (IProveedor e ICanal)

* **Estado:** aceptado
* **Fecha:** 2026-10-28
* **Decisores:** Ramiro Rossi

## Contexto y Declaración del Problema
Las iteraciones 1 y 2 dejaron un adaptador (ACL) por proveedor, cada uno con su contrato interno (`ICotizadorHotel`, `IProveedorInventario`, `IProveedorArrendadora`). Ahora hay que sumar adaptadores de entrada (Booking, correo), un hotel nuevo de API propietaria y canales de envío nuevos (Instagram) sin tocar el Core. Sin un contrato común, cada conector nuevo exige entender y adaptar a sus consumidores.

## Impulsores de la Decisión (Decision Drivers)
* `QA-INT-01`: integrar una cadena hotelera nueva en menos de 2 semanas de esfuerzo, en un único módulo de frontera y con 0 impacto en la lógica core.
* `QA-INT-02`: sumar Instagram en menos de 1 semana, con 1 componente nuevo y 0 modificaciones en los consumidores existentes.
* Coherencia con la ACL y Ping/Echo ya decididos en la iteración 1.

## Opciones Consideradas
* Opción 1: Abstract common services: `IProveedor` (`ping()`, `traducir(mensaje)`, `recibirNovedad(mensaje)`) para proveedores e `ICanal` (`enviar(destinatario, propuesta)`) para canales; los contratos específicos extienden a la interfaz común.
* Opción 2: Un contrato independiente por adaptador, sin interfaz común (situación de las iteraciones 1 y 2).
* Opción 3: Una clase base abstracta con lógica compartida (herencia de implementación).

## Resultado de la Decisión
Opción elegida: **"Opción 1: interfaces comunes `IProveedor` e `ICanal`, extendidas por los contratos específicos"**, porque convierte a un hotel o a un canal nuevo en una implementación más de un contrato conocido, ubicada en un único módulo, que es lo que miden `QA-INT-01` y `QA-INT-02`. Los consumidores dependen de la interfaz y no de cada conector.

### Consecuencias Positivas (Beneficios)
* Un hotel nuevo implementa `IProveedor` y el contrato de cotización en un solo módulo; el Orquestador no se modifica.
* Instagram es una implementación de `ICanal`; Email y WhatsApp no cambian.
* Ping/Echo, traducción y recepción de novedades quedan uniformes entre adaptadores.

### Consecuencias Negativas (Trade-offs / Riesgos)
* La interfaz común puede quedarse corta ante particularidades de un proveedor y forzar excepciones o extensiones.
* Los adaptadores de cotización deben implementar `recibirNovedad` aunque no la usen, lo que puede violar la segregación de interfaces.
* Cambiar `IProveedor` o `ICanal` impacta a todas las implementaciones: la interfaz pasa a ser un contrato crítico que hay que versionar con cuidado.
* Se solapa en parte con los contratos de los adaptadores de la iteración 1; hay que reconciliar ambos para no tener dos jerarquías.
