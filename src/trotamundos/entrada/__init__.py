"""Nodos de entrada: Adaptador de correo, Gestor de autorización y Parseo aislado
(ADR-IT3-010). Corren separados de los nodos del Orquestador.

Imports prohibidos: `trotamundos.orquestador`. El contacto con el resto del sistema es el
Broker. Solo el Gestor de autorización puede importar `trotamundos.persistencia`
(tokens cifrados en la Base primaria de viajes).
"""
