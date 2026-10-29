# Seguridad: Acceso controlado al correo del titular

* **Estado:** aceptado
* **Fecha:** 2026-10-28
* **Decisores:** Tomas Fontana

## Contexto y Declaración del Problema
Para agregar reservas automáticamente (`REF-02`) el sistema debe leer el correo del titular, que contiene información personal. El acceso debe existir solo con la autorización expresa del titular, no ir más allá de lo necesario y poder retirarse cuando el titular quiera.

## Impulsores de la Decisión (Decision Drivers)
* `QA-SEG-03*`: el titular autoriza la lectura de su correo; el sistema accede solo con esa autorización y agrega las reservas a su itinerario.
* `CON-02`: la integración con el correo es por API.
* Seguridad y privacidad de datos personales (requisito del TPE).

## Opciones Consideradas
* Opción 1: Gestor de autorización del correo: consentimiento del titular, permisos mínimos, tokens cifrados y revocación (Authorize / Authenticate actors + Limit exposure + Encrypt data + Revoke access, tomadas como una sola decisión).
* Opción 2: Pedir y guardar las credenciales del correo del usuario.
* Opción 3: Reenvío manual de los mensajes a una casilla de Trotamundos.

## Resultado de la Decisión
Opción elegida: **"Opción 1: Gestor de autorización con consentimiento, permisos mínimos, tokens cifrados y revocación"**, porque es la única que permite leer solo con la autorización del titular sin custodiar sus credenciales. El Adaptador de correo no lee sin token vigente. Al revocar, deja de leerse el correo y la reserva ya incorporada al itinerario se conserva.

### Consecuencias Positivas (Beneficios)
* El titular controla el acceso y puede retirarlo en cualquier momento.
* Permisos mínimos: se reduce lo que expone una filtración.
* Los tokens se guardan cifrados; nunca se almacenan contraseñas.

### Consecuencias Negativas (Trade-offs / Riesgos)
* Agrega fricción en el alta del usuario (flujo de autorización).
* Costo de procesamiento y de manejo de claves (almacenamiento, rotación y renovación de tokens).
* Los tokens cifrados se guardan en la base, que pasa a contener datos más sensibles.
* Conservar lo ya incorporado al revocar es una decisión de diseño con impacto en privacidad; queda pendiente definir si el titular puede pedir también su eliminación.
* Cada proveedor de correo implementa la autorización a su manera, lo que se refleja en el adaptador.
