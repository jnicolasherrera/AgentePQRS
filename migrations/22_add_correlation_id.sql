-- ═══════════════════════════════════════════════════════════════
-- Migración 22: Agrega correlation_id a pqrs_casos
-- ═══════════════════════════════════════════════════════════════
-- Trazabilidad Kafka → caso → respuesta → audit.
--
-- Detectado durante smoke E2E del sprint Tutelas (2026-04-24): el
-- `db_inserter.insert_pqrs_caso` incluía esta columna en su INSERT
-- pero nunca existió en el schema real (ni en prod ni en el baseline).
-- `models.py:PqrsCaso` la declara como `correlation_id: Mapped[uuid.UUID]`
-- pero el ORM es "reflejo, no fuente de verdad".
--
-- Esta migración formaliza la columna en el schema con:
-- - NOT NULL + DEFAULT gen_random_uuid() para que filas históricas
--   se queden con un UUID distinto cada una (retrocompat 100%).
-- - Índice para queries de trazabilidad por correlation_id.
--
-- Origen del requisito: worker_ai_consumer.py lee `correlation_id`
-- del mensaje Kafka y lo propaga al caso insertado, permitiendo que
-- logs externos (CloudWatch, SSE Redis) se correlacionen con la fila.
-- ═══════════════════════════════════════════════════════════════

ALTER TABLE pqrs_casos
    ADD COLUMN IF NOT EXISTS correlation_id UUID NOT NULL DEFAULT gen_random_uuid();

CREATE INDEX IF NOT EXISTS idx_pqrs_correlation
    ON pqrs_casos(correlation_id);

COMMENT ON COLUMN pqrs_casos.correlation_id IS
    'UUID de trazabilidad. Permite rastrear evento Kafka → caso → respuesta → audit. Default gen_random_uuid() para retrocompat con filas históricas.';
