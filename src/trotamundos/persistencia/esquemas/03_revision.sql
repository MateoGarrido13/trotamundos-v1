-- SPEC: SPEC-REF-03 / ELEMENTO PASO 5: Filtro de remitentes, whitelist y Mensajes en revisión (ITERACION_3)
-- Los guarda el Orquestador de viajes en la Base primaria (ADR-IT3-008).
CREATE TABLE IF NOT EXISTS remitente_seguro (
    titular_id  TEXT NOT NULL,
    remitente   TEXT NOT NULL,
    PRIMARY KEY (titular_id, remitente)
);

-- Un mensaje descartado conserva solo su identificador y su fecha (reserva = '{}').
CREATE TABLE IF NOT EXISTS mensaje_revision (
    titular_id  TEXT NOT NULL,
    id_mensaje  TEXT NOT NULL,
    remitente   TEXT NOT NULL,
    reserva     JSONB NOT NULL,
    estado      TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'descartado')),
    creado_en   TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (titular_id, id_mensaje)
);
CREATE INDEX IF NOT EXISTS mensaje_revision_remitente_idx
    ON mensaje_revision (titular_id, remitente, estado);
