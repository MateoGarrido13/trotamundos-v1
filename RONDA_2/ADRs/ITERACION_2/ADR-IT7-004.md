# ADR-IT7-004 — Time-out y Circuit Breaker hacia los proveedores de modelo de IA

## Contexto

`QA-PER-05` fija que la respuesta al viajero llega en como máximo 35 segundos. `QA-DIS-02` fija que el asistente muestra el número de contacto de la agencia de viajes preferida del usuario cuando ningún proveedor de modelo de IA está disponible. Si cada llamada espera esa cota completa, un proveedor que no responde consume la latencia del módulo que atiende al viajero y retiene el hilo de ejecución.

## Impulsores

- `QA-PER-05`: la respuesta al viajero no supera los 35 segundos.
- `QA-DIS-02`: el número de contacto de la agencia de viajes preferida es lo que ve el viajero cuando el proveedor de modelo no atiende.
- `REF-07`: el asistente sigue siendo el primer nivel de soporte.

## Opciones

| Opción | Descripción |
| --- | --- |
| Opción 1 | Time-out (detección de fallas) sobre la llamada al proveedor de modelo, con cota interior a los 35 segundos. Al agotarse, se libera el hilo y se muestra el número de contacto de la agencia de viajes preferida (`QA-DIS-02`). Si el time-out se repite cinco veces seguidas, Circuit Breaker (prevención de fallas) pasa a Abierto, corta las llamadas a ese proveedor y muestra el mismo número de inmediato, sin espera, hasta que el proveedor se recupere. |
| Opción 2 | Esperar en cada petición hasta los 35 segundos y recién entonces mostrar el número de contacto. |
| Opción 3 | Reintentar la llamada al proveedor dentro de la misma petición del viajero. |

## Decisión

**Opción 1 elegida.** El time-out detecta que el proveedor no responde antes de agotar los 35 segundos de `QA-PER-05`, libera el hilo y entrega el número de contacto de la agencia de viajes preferida. El Circuit Breaker cuenta esos time-out consecutivos. A la quinta vez pasa a Abierto y la respuesta por defecto sale en 0 ms, sin volver a llamar al proveedor, hasta que ese proveedor se recupere.

## Consecuencias

- Positivo: el viajero recibe el número de contacto de la agencia de viajes preferida antes de los 35 segundos. Con el cortacircuitos abierto no paga ni siquiera la cota del time-out.
- Negativo: mientras el cortacircuitos está abierto, el viajero no obtiene una respuesta generativa aunque el proveedor se haya recuperado en el instante anterior al próximo intento. La quinta falla consecutiva es el umbral que abre el circuito.

## Relación con otros ADRs

- `ADR-IT7-002`: la cota de 35 segundos sigue siendo el máximo que espera el viajero. Este ADR impide que la llamada al proveedor consuma esa cota entera.
- `ADR-IT6-004`: el número de contacto de `QA-DIS-02` ya estaba decidido. Aquí se fija cuándo se emite.
