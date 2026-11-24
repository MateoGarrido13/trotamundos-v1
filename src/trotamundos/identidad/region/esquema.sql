-- SPEC-COMP-05: Base de cuentas de una región (ADR-IT4-001, ADR-IT4-002).
-- Cada región tiene su base (con su pasiva); ninguna se sincroniza con otra.
CREATE TABLE IF NOT EXISTS cuenta (
    id                 text PRIMARY KEY,
    correo             text NOT NULL,
    huella             text NOT NULL UNIQUE,
    clave_hash         text NOT NULL,
    unicidad_pendiente boolean NOT NULL DEFAULT false,
    creada             timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS token_renovacion (
    huella    text PRIMARY KEY,
    cuenta_id text NOT NULL REFERENCES cuenta(id),
    vence     timestamptz NOT NULL,
    revocado  boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS token_renovacion_cuenta ON token_renovacion (cuenta_id);

-- Un solo pedido vigente por cuenta (ADR-IT4-006): la fila de la cuenta se pisa solo si ya se usó o venció.
CREATE TABLE IF NOT EXISTS recuperacion (
    cuenta_id   text PRIMARY KEY REFERENCES cuenta(id),
    token_huella text NOT NULL,
    vence       timestamptz NOT NULL,
    usado       boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS recuperacion_token ON recuperacion (token_huella);

CREATE TABLE IF NOT EXISTS intento_recuperacion (
    cuenta_id text NOT NULL,
    momento   timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS intento_recuperacion_cuenta ON intento_recuperacion (cuenta_id, momento);

CREATE TABLE IF NOT EXISTS aviso_recuperacion (
    cuenta_id text PRIMARY KEY,
    desde     timestamptz NOT NULL
);
