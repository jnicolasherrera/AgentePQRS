-- ═══════════════════════════════════════════════════════════════════════════
-- Migración 16: Knowledge Base RAG (pgvector)
-- Sprint RAG real 2026-05-26 — Fase 1 (infra).
--
-- Objetivo: tabla `respuestas_kb` con embeddings para retrieval semántico
-- de respuestas históricas, plantillas y normativa colombiana. Consumida
-- por `generar_borrador_para_caso` (a implementar en Fase 3).
--
-- Multi-tenant desde día 1: cada fila tiene `cliente_id`, RLS forzado
-- igual que pqrs_casos (filtro explícito + policies efectivas con rol
-- pqrs_backend post-SEC-2026-05-21).
--
-- Imagen Postgres ya cambiada a pgvector/pgvector:pg15 (drop-in compatible).
-- ═══════════════════════════════════════════════════════════════════════════

-- 0. Extensión pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Tabla principal del KB
CREATE TABLE IF NOT EXISTS respuestas_kb (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  cliente_id      UUID NOT NULL REFERENCES clientes_tenant(id) ON DELETE CASCADE,

  -- Origen del documento indexado.
  --   caso_enviado : respuesta histórica aprobada y enviada (pqrs_casos)
  --   plantilla    : plantilla_respuesta activa
  --   normativa    : artículo de normativa colombiana (Decreto 2591/91, Ley 1755/2015, ...)
  source_type     VARCHAR(20) NOT NULL
                  CHECK (source_type IN ('caso_enviado', 'plantilla', 'normativa')),
  source_id       VARCHAR(100) NOT NULL,   -- UUID del caso, id de plantilla, slug del artículo

  -- Etiquetado para filtrado pre-retrieval (acelera la búsqueda vectorial).
  problematica    VARCHAR(100),            -- p.ej. SUPLANTACION_RAPICREDIT (puede ser NULL para normativa)
  tipo_caso       VARCHAR(50),             -- TUTELA / PETICION / QUEJA / RECLAMO / SOLICITUD / NULL

  -- Contenido textual indexado (lo que se mostrará al LLM en el few-shot).
  contenido       TEXT NOT NULL,

  -- Embedding: 1024 dims = voyage-multilingual-2 / voyage-3-large (Voyage AI).
  -- Si en el futuro cambiamos modelo de mayor dim (p.ej. 2048), se agrega
  -- otra columna o se hace ALTER y re-embedding masivo.
  embedding       vector(1024) NOT NULL,
  embedding_model VARCHAR(50) NOT NULL DEFAULT 'voyage-multilingual-2',

  -- Metadata libre: para casos {fecha_envio, score_calidad_inferido, asunto_original, …},
  -- para plantillas {keywords, contexto}, para normativa {fuente, articulo, fecha_vigencia}.
  metadata        JSONB DEFAULT '{}'::jsonb,

  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

  -- Un mismo source no debe indexarse dos veces para el mismo tenant.
  CONSTRAINT respuestas_kb_unique UNIQUE (cliente_id, source_type, source_id)
);

COMMENT ON TABLE respuestas_kb IS
  'Knowledge Base para RAG (Fase 1 sprint 2026-05-26). Indexa respuestas históricas, plantillas y normativa para retrieval semántico en generar_borrador_para_caso.';

-- 2. Índices
-- 2.a — HNSW sobre embedding para ANN (Approximate Nearest Neighbor) con coseno.
--       HNSW > IVFFlat para datasets chicos (no requiere ANALYZE), set-and-forget.
CREATE INDEX IF NOT EXISTS respuestas_kb_embedding_hnsw_idx
  ON respuestas_kb USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- 2.b — Filtros pre-retrieval por tenant + tipo. CRUCIAL: HNSW no aplica
--       filtros eficientemente sin esto; el planner combina los dos índices.
CREATE INDEX IF NOT EXISTS respuestas_kb_cliente_tipo_idx
  ON respuestas_kb (cliente_id, source_type);

CREATE INDEX IF NOT EXISTS respuestas_kb_cliente_problematica_idx
  ON respuestas_kb (cliente_id, problematica) WHERE problematica IS NOT NULL;

-- 3. Trigger updated_at
CREATE OR REPLACE FUNCTION fn_respuestas_kb_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_respuestas_kb_updated_at ON respuestas_kb;
CREATE TRIGGER trg_respuestas_kb_updated_at
  BEFORE UPDATE ON respuestas_kb
  FOR EACH ROW EXECUTE FUNCTION fn_respuestas_kb_set_updated_at();

-- 4. RLS multi-tenant (mismo patrón que pqrs_casos post-SEC-2026-05-21)
ALTER TABLE respuestas_kb ENABLE ROW LEVEL SECURITY;
ALTER TABLE respuestas_kb FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS respuestas_kb_tenant_isolation ON respuestas_kb;
CREATE POLICY respuestas_kb_tenant_isolation ON respuestas_kb
  USING (
    cliente_id::text = current_setting('app.current_tenant_id', true)
    OR current_setting('app.is_superuser', true) = 'true'
  )
  WITH CHECK (
    cliente_id::text = current_setting('app.current_tenant_id', true)
    OR current_setting('app.is_superuser', true) = 'true'
  );

-- 5. Tabla auxiliar: log de ingestion (qué se backfilleó, cuándo, costo)
CREATE TABLE IF NOT EXISTS kb_ingestion_log (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  cliente_id      UUID REFERENCES clientes_tenant(id) ON DELETE CASCADE,
  source_type     VARCHAR(20) NOT NULL,
  documentos      INT NOT NULL,
  tokens_in       INT,                 -- tokens enviados al embedder (estimación de costo)
  embedding_model VARCHAR(50),
  status          VARCHAR(20) NOT NULL CHECK (status IN ('ok', 'partial', 'error')),
  error_msg       TEXT,
  duracion_ms     INT,
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS kb_ingestion_log_cliente_idx
  ON kb_ingestion_log (cliente_id, created_at DESC);

-- 6. Grants (idempotentes — solo si los roles existen)
DO $$
BEGIN
  -- Rol del backend (sin BYPASSRLS) — creado en defensa en profundidad RLS deploy.
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pqrs_backend') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON respuestas_kb TO pqrs_backend;
    GRANT SELECT, INSERT ON kb_ingestion_log TO pqrs_backend;
  END IF;

  -- Rol legado de los workers (sigue con BYPASSRLS — escribe multi-tenant).
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aequitas_worker') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON respuestas_kb TO aequitas_worker;
    GRANT SELECT, INSERT ON kb_ingestion_log TO aequitas_worker;
  END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════
-- Verificación post-migración (manual):
--   SELECT extversion FROM pg_extension WHERE extname='vector';   -- 0.8.x
--   \d respuestas_kb
--   \di respuestas_kb_*
--   SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='respuestas_kb';
-- ═══════════════════════════════════════════════════════════════════════════
