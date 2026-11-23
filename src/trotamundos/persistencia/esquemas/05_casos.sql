-- SPEC: SPEC-REF-05 / ELEMENTO PASO 5: Orquestador de viajes, agencia preferida y casos (ITERACION_4)
-- La agencia preferida es de la cuenta. El consentimiento es explícito: sin él no se guarda.
CREATE TABLE IF NOT EXISTS preferencia_agencia (
    cuenta_id         TEXT PRIMARY KEY,
    agencia           TEXT NOT NULL,
    consentimiento_en TIMESTAMPTZ NOT NULL
);

-- El caso guarda la agencia vigente al reportar y el pedido tal como se envió (para reintentar).
CREATE TABLE IF NOT EXISTS caso (
    id              TEXT PRIMARY KEY,
    cuenta_id       TEXT NOT NULL,
    itinerario_id   TEXT NOT NULL,
    reserva_id      TEXT NOT NULL,
    agencia         TEXT NOT NULL,
    descripcion     TEXT NOT NULL,
    resumen_dialogo TEXT,
    pedido          JSONB NOT NULL,
    estado          TEXT NOT NULL CHECK (estado IN
                      ('en_tramite', 'abierto', 'en_curso', 'resuelto', 'sin_entregar')),
    creado_en       TIMESTAMPTZ NOT NULL,
    actualizado_en  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS caso_cuenta_idx ON caso (cuenta_id, creado_en);
