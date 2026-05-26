-- ============================================================
-- 17_borrador_feedback.sql — Tabla de feedback de borradores IA
--
-- El código del backend (casos.py:432-442) ya intenta poblar esta tabla
-- en cada BORRADOR_EDITADO con similarity_score IA-vs-editado, pero el
-- INSERT falla silente en try/except porque la tabla no existía.
-- Esta migración la crea + agrega usuario_id (que faltaba en el INSERT).
--
-- Habilita métricas de eficiencia por abogado:
--   - similarity promedio (cuánto cambia el borrador IA antes de enviarlo)
--   - % de borradores editados vs aceptados tal cual
--
-- Idempotente.
-- ============================================================

CREATE TABLE IF NOT EXISTS borrador_feedback (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caso_id          UUID REFERENCES pqrs_casos(id) ON DELETE CASCADE,
  cliente_id       UUID,
  tipo_caso        VARCHAR(50),
  usuario_id       UUID REFERENCES usuarios(id) ON DELETE SET NULL,
  original_ai      TEXT,
  editado_usuario  TEXT,
  similarity_score NUMERIC(4,3),   -- 0.000 (totalmente reescrito) a 1.000 (idéntico)
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE  borrador_feedback IS
  'Feedback de cuánto edita el usuario el borrador generado por IA. '
  'Insertado por casos.py al guardar un borrador editado. Habilita métricas '
  'de calidad/eficiencia por abogado (similarity promedio).';
COMMENT ON COLUMN borrador_feedback.similarity_score IS
  'Similitud Jaccard/SequenceMatcher entre original_ai y editado_usuario. '
  '1.0 = sin cambios; 0.0 = totalmente reescrito.';

CREATE INDEX IF NOT EXISTS idx_borrador_feedback_cliente_usuario_fecha
  ON borrador_feedback (cliente_id, usuario_id, created_at DESC);
