-- ============================================================
-- C2 — Policies RLS faltantes (5 tablas que hoy fugan)
-- Patrón idéntico a las 10 policies ya activas en prod.
-- Idempotente (DROP POLICY IF EXISTS) y reversible.
-- Rol del backend: pqrs_backend (NO bypassa RLS).
-- super_admin sigue viendo todo vía app.is_superuser='true'.
-- ============================================================

-- 1) borrador_feedback — policy DIRECTA (tiene cliente_id)
ALTER TABLE borrador_feedback ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_borrador_feedback_policy ON borrador_feedback;
CREATE POLICY tenant_isolation_borrador_feedback_policy ON borrador_feedback
  FOR ALL
  USING (
    cliente_id = current_setting('app.current_tenant_id', true)::uuid
    OR current_setting('app.is_superuser', true) = 'true'
  );

-- 2) pqrs_clasificacion_feedback — policy DIRECTA (tiene cliente_id)
ALTER TABLE pqrs_clasificacion_feedback ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_pqrs_clasificacion_feedback_policy ON pqrs_clasificacion_feedback;
CREATE POLICY tenant_isolation_pqrs_clasificacion_feedback_policy ON pqrs_clasificacion_feedback
  FOR ALL
  USING (
    cliente_id = current_setting('app.current_tenant_id', true)::uuid
    OR current_setting('app.is_superuser', true) = 'true'
  );

-- 3) plantillas_respuesta — policy DIRECTA (tiene cliente_id, 62 filas todas con tenant)
ALTER TABLE plantillas_respuesta ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_plantillas_respuesta_policy ON plantillas_respuesta;
CREATE POLICY tenant_isolation_plantillas_respuesta_policy ON plantillas_respuesta
  FOR ALL
  USING (
    cliente_id = current_setting('app.current_tenant_id', true)::uuid
    OR current_setting('app.is_superuser', true) = 'true'
  );

-- 4) kb_ingestion_log — policy DIRECTA (tiene cliente_id; hoy no fuga pero preventiva)
ALTER TABLE kb_ingestion_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_kb_ingestion_log_policy ON kb_ingestion_log;
CREATE POLICY tenant_isolation_kb_ingestion_log_policy ON kb_ingestion_log
  FOR ALL
  USING (
    cliente_id = current_setting('app.current_tenant_id', true)::uuid
    OR current_setting('app.is_superuser', true) = 'true'
  );

-- 5) audit_log_respuestas — policy por JOIN (NO tiene cliente_id, sí caso_id)
ALTER TABLE audit_log_respuestas ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_audit_log_respuestas_policy ON audit_log_respuestas;
CREATE POLICY tenant_isolation_audit_log_respuestas_policy ON audit_log_respuestas
  FOR ALL
  USING (
    caso_id IN (
      SELECT id FROM pqrs_casos
      WHERE cliente_id = current_setting('app.current_tenant_id', true)::uuid
    )
    OR current_setting('app.is_superuser', true) = 'true'
  );

-- ============================================================
-- ROLLBACK (si algo rompe acceso legítimo):
--   DROP POLICY <nombre> ON <tabla>;
--   ALTER TABLE <tabla> DISABLE ROW LEVEL SECURITY;
-- ============================================================
