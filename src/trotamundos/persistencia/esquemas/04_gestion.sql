-- SPEC: SPEC-REF-04 / ELEMENTO PASO 5: Operaciones manuales de reserva, Módulo de control de
-- acceso y auditoría, contrato `Reserva` (ITERACION_4)
-- Se aplica después de 01_viajes.sql. Es idempotente.

-- Itinerario: contenedor de viajes. El individual usa la cuenta del viajero como identificador.
ALTER TABLE viaje ADD COLUMN IF NOT EXISTS itinerario_id TEXT;
UPDATE viaje SET itinerario_id = viajero_id WHERE itinerario_id IS NULL;
CREATE INDEX IF NOT EXISTS viaje_itinerario_idx ON viaje (itinerario_id, estado);

-- Contrato `Reserva` (ADR-IT4-009) y baja lógica (ADR-IT4-008).
ALTER TABLE reserva ADD COLUMN IF NOT EXISTS origen TEXT NOT NULL DEFAULT 'manual'
    CHECK (origen IN ('manual', 'correo', 'proveedor'));
ALTER TABLE reserva ADD COLUMN IF NOT EXISTS creado_por TEXT;
ALTER TABLE reserva ADD COLUMN IF NOT EXISTS editada_manualmente BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE reserva ADD COLUMN IF NOT EXISTS baja_en TIMESTAMPTZ;

-- Membresías: solo relacionan identificadores. La Base de viajes no guarda cuentas.
CREATE TABLE IF NOT EXISTS membresia (
    itinerario_id TEXT NOT NULL,
    cuenta_id     TEXT NOT NULL,
    rol           TEXT NOT NULL CHECK (rol IN ('organizador', 'participante')),
    PRIMARY KEY (itinerario_id, cuenta_id)
);

-- Auditoría de la decisión, permitida o denegada, en la misma transacción que la escritura.
CREATE TABLE IF NOT EXISTS auditoria (
    id            BIGSERIAL PRIMARY KEY,
    cuenta_id     TEXT NOT NULL,
    itinerario_id TEXT NOT NULL,
    operacion     TEXT NOT NULL,
    permiso       TEXT NOT NULL,
    resultado     TEXT NOT NULL CHECK (resultado IN ('permitido', 'denegado', 'rechazado')),
    reserva_id    TEXT,
    clave         TEXT,
    motivo        TEXT,
    momento       TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS auditoria_itinerario_idx ON auditoria (itinerario_id, momento);

-- Clave de operación generada por el cliente: un reintento no duplica (ADR-IT4-008).
CREATE TABLE IF NOT EXISTS clave_operacion (
    cuenta_id TEXT NOT NULL,
    clave     TEXT NOT NULL,
    resultado JSONB NOT NULL,
    creada_en TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (cuenta_id, clave)
);

-- Novedades del proveedor. Una reserva editada a mano no se pisa: la novedad queda pendiente.
CREATE TABLE IF NOT EXISTS novedad (
    id            TEXT PRIMARY KEY,
    itinerario_id TEXT NOT NULL,
    reserva_id    TEXT NOT NULL,
    proveedor     TEXT NOT NULL DEFAULT '',
    cambios       JSONB NOT NULL,
    estado        TEXT NOT NULL CHECK (estado IN ('pendiente', 'aplicada')),
    recibida_en   TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS novedad_itinerario_idx ON novedad (itinerario_id, estado);
