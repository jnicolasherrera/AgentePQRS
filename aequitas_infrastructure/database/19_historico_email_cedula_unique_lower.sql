-- ═══════════════════════════════════════════════════════════════════════════
-- Migración 19: UNIQUE case-insensitive en historico_email_cedula
--
-- Fix bug_015 del ultrareview PR #11.
--
-- Problema: la migración 18 dejó `UNIQUE (cliente_id, email)` que es
-- case-sensitive (Postgres default), mientras que el índice de lookup ya
-- estaba en `lower(email)`. Si un futuro writer no lowercases (p.ej. el
-- lookup runtime que se agregue), pueden colarse duplicados case-distinto
-- ('Juan@x.com' vs 'juan@x.com') y la dedup queda rota.
--
-- Fix: reemplazar la constraint con un índice único expression-based.
-- El índice de lookup separado queda redundante → DROP.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- Defensivo: lowercase de cualquier email no-normalizado actual (no debería
-- haber porque el seed normaliza, pero por las dudas — evita conflict UNIQUE
-- al crear el índice nuevo).
UPDATE historico_email_cedula SET email = lower(email)
WHERE email != lower(email);

-- Reemplazar UNIQUE (case-sensitive) por UNIQUE INDEX expression-based.
ALTER TABLE historico_email_cedula
  DROP CONSTRAINT IF EXISTS historico_email_cedula_unique;

CREATE UNIQUE INDEX IF NOT EXISTS historico_email_cedula_unique_lower
  ON historico_email_cedula (cliente_id, lower(email));

-- El lookup index separado queda redundante (el UNIQUE nuevo ya cubre la
-- misma columna expression).
DROP INDEX IF EXISTS historico_email_cedula_lookup_idx;

COMMIT;
