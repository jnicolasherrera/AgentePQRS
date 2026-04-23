-- ═══════════════════════════════════════════════════════════════
-- Migración 18: Columna y CHECK extendido de semaforo_sla
-- ═══════════════════════════════════════════════════════════════
-- Contexto:
-- * Sprint Tutelas S1+S2+S3 necesita los estados NARANJA (<10%
--   SLA restante) y NEGRO (vencido sin respuesta, para tutelas).
-- * La columna `semaforo_sla` existió históricamente en prod como
--   cambio ad-hoc sin migración versionada. Nunca se commiteó una
--   SQL que la creara; el baseline schema-only del 2026-04-23 lo
--   confirma (no aparece en prod ni en el repo). Esta migración la
--   formaliza.
-- * La 14 original referenciaba `NEW.semaforo_sla := 'VERDE'`; el fix
--   en `migrations/14_regimen_sectorial.sql` removió esa línea para
--   no romper el trigger mientras la columna no existiera. Con esta
--   18 la columna queda creada; la 14 sigue sin tocarla porque el
--   default 'VERDE' aplica al INSERT — misma semántica, menos
--   acoplamiento.
-- ═══════════════════════════════════════════════════════════════

ALTER TABLE pqrs_casos
    ADD COLUMN IF NOT EXISTS semaforo_sla VARCHAR(20) DEFAULT 'VERDE';

ALTER TABLE pqrs_casos
    DROP CONSTRAINT IF EXISTS pqrs_casos_semaforo_sla_check;

ALTER TABLE pqrs_casos
    ADD CONSTRAINT pqrs_casos_semaforo_sla_check
    CHECK (semaforo_sla IN ('VERDE', 'AMARILLO', 'NARANJA', 'ROJO', 'NEGRO'));

COMMENT ON COLUMN pqrs_casos.semaforo_sla IS
    'Estado visual del SLA. Default VERDE. Migrada desde ad-hoc (histórica migración "09" nunca commiteada, recuperada aquí). Extendida en sprint Tutelas con NARANJA (<10% restante) y NEGRO (vencido sin respuesta).';
