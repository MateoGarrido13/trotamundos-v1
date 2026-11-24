-- SPEC-COMP-07: anuncios de viaje nuevos que llegan por el aviso de Booking. Los ven todos los viajeros.
CREATE TABLE IF NOT EXISTS anuncio (
    id           TEXT PRIMARY KEY,           -- booking:<aviso_id>: un aviso repetido no se guarda dos veces
    titulo       TEXT NOT NULL,
    destino      TEXT NOT NULL,
    inicio       DATE NOT NULL,
    fin          DATE NOT NULL,
    proveedor    TEXT NOT NULL,
    detectado_en TIMESTAMPTZ NOT NULL,       -- cuando el listener lo detectó (QA-PER-01)
    recibido_en  TIMESTAMPTZ NOT NULL        -- cuando el Orquestador lo guardó
);
CREATE INDEX IF NOT EXISTS anuncio_recibido_idx ON anuncio (recibido_en DESC);
