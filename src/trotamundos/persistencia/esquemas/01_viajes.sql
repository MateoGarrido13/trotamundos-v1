-- SPEC: SPEC-REF-01 / ELEMENTO PASO 5: Base primaria y Base pasiva (ITERACION_1, ITERACION_2)
-- La Base de viajes no guarda cuentas, perfiles ni sesiones.
-- Los campos propios de cada tipo de reserva van en `datos`: un medio nuevo no migra el esquema.
CREATE TABLE IF NOT EXISTS viaje (
    id            TEXT PRIMARY KEY,
    viajero_id    TEXT NOT NULL,
    estado        TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'archivado')),
    archivado_en  TIMESTAMP
);
CREATE INDEX IF NOT EXISTS viaje_viajero_idx ON viaje (viajero_id, estado);

CREATE TABLE IF NOT EXISTS reserva (
    identificador TEXT PRIMARY KEY,
    viaje_id      TEXT NOT NULL REFERENCES viaje (id),
    tipo          TEXT NOT NULL,
    inicio        TIMESTAMP NOT NULL,
    fin           TIMESTAMP NOT NULL,
    estado        TEXT NOT NULL,
    lugar         TEXT,
    datos         JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS reserva_viaje_idx ON reserva (viaje_id);
