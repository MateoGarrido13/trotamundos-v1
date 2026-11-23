-- SPEC-COMP-01: el viaje tiene nombre (lo elige quien lo crea).
ALTER TABLE viaje ADD COLUMN IF NOT EXISTS nombre TEXT NOT NULL DEFAULT '';
