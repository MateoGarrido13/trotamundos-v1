-- SPEC: SPEC-REF-06 / ELEMENTO PASO 5: Base analítica (ITERACION_5)
-- Base distinta de la de viajes y de las de cuentas. No guarda correos ni credenciales ni
-- identificadores de cuentas, reservas, viajes o itinerarios.

-- Histórico: permite recalcular una dimensión nueva (ADR-IT5-002). La clave primaria es el
-- identificador del evento: así el Proyector descarta los repetidos.
CREATE TABLE IF NOT EXISTS evento (
    id           TEXT PRIMARY KEY,
    tipo         TEXT NOT NULL CHECK (tipo IN ('alta', 'modificacion', 'baja', 'archivado')),
    tipo_reserva TEXT NOT NULL DEFAULT '',
    destino      TEXT NOT NULL DEFAULT '',
    inicio       TIMESTAMP,
    fin          TIMESTAMP,
    origen       TEXT NOT NULL DEFAULT '',
    estado       TEXT NOT NULL DEFAULT '',
    ocurrido_en  TIMESTAMPTZ NOT NULL,
    dia          DATE NOT NULL
);

-- Preagregación incremental por tipo de evento, destino, día y tipo de reserva. El informe
-- lee estos contadores, no el histórico.
CREATE TABLE IF NOT EXISTS contador (
    dia          DATE NOT NULL,
    destino      TEXT NOT NULL,
    tipo_reserva TEXT NOT NULL,
    tipo_evento  TEXT NOT NULL,
    cantidad     BIGINT NOT NULL,
    PRIMARY KEY (dia, destino, tipo_reserva, tipo_evento)
);
CREATE INDEX IF NOT EXISTS contador_tipo_dia_idx ON contador (tipo_evento, dia);
