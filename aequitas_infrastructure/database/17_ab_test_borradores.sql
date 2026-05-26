-- ═══════════════════════════════════════════════════════════════════════════
-- Migración 17: A/B test shadow mode (Fase 4 sprint RAG real)
--
-- Objetivo: persistir DOS variants de borrador por cada caso del camino B
-- (sin plantilla, Claude genérico): la oficial con_rag (lo que sale en
-- producción tras Fase 3) y una shadow no_rag (baseline pre-RAG, replicando
-- el comportamiento previo). Cuando el abogado envía el caso, un script
-- batch (scripts/ab_test_evaluate.py) compara el texto final con cada
-- variant y llena `similarity_to_edited`.
--
-- El objetivo del experimento: demostrar cuánto baja la tasa de edición
-- del abogado al inyectar contexto RAG. Si with_rag > no_rag en similitud,
-- el RAG ayuda. Mínimo recomendado: ~30 casos por variant para significancia.
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS ab_test_borradores (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  caso_id         UUID NOT NULL REFERENCES pqrs_casos(id)       ON DELETE CASCADE,
  cliente_id      UUID NOT NULL REFERENCES clientes_tenant(id)  ON DELETE CASCADE,

  -- 'with_rag' = la oficial (lo que mostró el dashboard al abogado).
  -- 'no_rag'   = la shadow (replica del comportamiento previo, sin retrieval).
  variant         VARCHAR(20) NOT NULL CHECK (variant IN ('with_rag', 'no_rag')),

  contenido       TEXT NOT NULL,
  -- Para with_rag: lista de docs usados {source_type, source_id, sim_score}.
  -- Para no_rag:   [] (vacío por definición).
  rag_docs        JSONB DEFAULT '[]'::jsonb,

  -- Metadata útil para análisis posterior.
  tipo_caso       VARCHAR(50),
  modelo          VARCHAR(50),
  tokens_in       INT,
  tokens_out      INT,
  latencia_ms     INT,

  -- Evaluación batch (scripts/ab_test_evaluate.py). NULL hasta que se evalúa.
  edited_text          TEXT,
  similarity_to_edited FLOAT,
  evaluated_at         TIMESTAMP WITH TIME ZONE,

  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

  -- Un caso tiene a lo sumo una variant por nombre — UPSERT idempotente.
  CONSTRAINT ab_test_borradores_caso_variant_unique UNIQUE (caso_id, variant)
);

COMMENT ON TABLE ab_test_borradores IS
  'A/B shadow mode del RAG (sprint Fase 4 — 2026-05-26). Cada caso del camino B (sin plantilla) genera ambas variants; evaluador batch compara contra el texto final del abogado.';

-- Índices para queries del evaluador batch.
CREATE INDEX IF NOT EXISTS ab_test_borradores_cliente_idx
  ON ab_test_borradores (cliente_id, created_at DESC);

-- Parcial: solo lo que falta evaluar.
CREATE INDEX IF NOT EXISTS ab_test_borradores_eval_pendiente_idx
  ON ab_test_borradores (caso_id) WHERE evaluated_at IS NULL;

-- RLS (mismo patrón que respuestas_kb y pqrs_casos post-SEC-2026-05-21).
ALTER TABLE ab_test_borradores ENABLE ROW LEVEL SECURITY;
ALTER TABLE ab_test_borradores FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ab_test_borradores_tenant_isolation ON ab_test_borradores;
CREATE POLICY ab_test_borradores_tenant_isolation ON ab_test_borradores
  USING (
    cliente_id::text = current_setting('app.current_tenant_id', true)
    OR current_setting('app.is_superuser', true) = 'true'
  )
  WITH CHECK (
    cliente_id::text = current_setting('app.current_tenant_id', true)
    OR current_setting('app.is_superuser', true) = 'true'
  );

-- Grants idempotentes (mismo patrón que respuestas_kb).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pqrs_backend') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON ab_test_borradores TO pqrs_backend;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aequitas_worker') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON ab_test_borradores TO aequitas_worker;
  END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════
-- Verificación post-migración:
--   \d ab_test_borradores
--   SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='ab_test_borradores';
-- ═══════════════════════════════════════════════════════════════════════════
