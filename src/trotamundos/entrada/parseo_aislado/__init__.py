# SPEC: SPEC-REF-02
# ELEMENTO PASO 5: Parseo aislado (ITERACION_3)
# ADRs: ADR-IT3-007
# DRIVERS: QA-SEG-03*, REF-02
"""Parseo aislado. Corre como proceso real del sistema operativo, sin token ni acceso a la base.

Imports prohibidos: persistencia, config, gestor_autorizacion, broker."""
