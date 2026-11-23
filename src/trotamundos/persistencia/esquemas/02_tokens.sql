-- SPEC: SPEC-REF-02 / ELEMENTO PASO 5: Gestor de autorización del correo (ITERACION_3)
-- Tokens de acceso al correo, cifrados, en la Base primaria de viajes (ADR-IT3-006).
-- Solo los usa el Gestor de autorización. El token nunca se guarda en claro.
CREATE TABLE IF NOT EXISTS token_correo (
    titular_id     TEXT PRIMARY KEY,
    token_cifrado  BYTEA NOT NULL,
    vence          TIMESTAMPTZ NOT NULL
);
