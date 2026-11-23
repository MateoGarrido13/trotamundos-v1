"""Módulo de Asistente Virtual (SPEC-REF-07): primer nivel de soporte interactivo.

Corre en nodos propios, **sin estado** y detrás del API Gateway. No lee ni escribe ninguna base, no
llama a la API de la agencia y no importa al Orquestador: solo conoce `dominio.puertos_asistente`.
Lo que hay que recordar entre turnos viaja en un contexto firmado que el cliente devuelve."""
