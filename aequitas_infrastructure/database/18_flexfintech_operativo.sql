-- ═══════════════════════════════════════════════════════════════════════════
-- Migración 18: FlexFintech operativo (sprint 2026-05-27)
--
-- 5 partes en una sola transacción (rollback automático ante error):
--   1) tipo_workflow en config_buzones, pqrs_casos, plantillas_respuesta
--      (PQRS vs ATENCION_CLIENTE para los "dos universos" FlexFintech).
--   2) email_respuesta_override en pqrs_casos
--      (admin puede editar el destinatario antes de enviar).
--   3) documento_peticionante (cédula plana) en pqrs_casos
--      (necesario para nombrar carpetas SharePoint {cedula}_{fecha}/).
--   4) tabla historico_email_cedula (multi-tenant con RLS)
--      (mapeo histórico email→cedula extraído de los Excel Flex/).
--   5) procesar_desde en config_buzones (cutoff date para el worker —
--      evita reprocesar mails históricos al activar un nuevo buzón).
--
-- Aplica a TODOS los tenants vía DDL — pero FlexFintech es el primer/único
-- que la usa funcionalmente. Recovery y Demo quedan con defaults
-- (tipo_workflow='PQRS', procesar_desde=NULL → comportamiento idéntico al
-- pre-migración).
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────
-- Parte 1: tipo_workflow
-- ─────────────────────────────────────────────────────────────────────────

ALTER TABLE config_buzones
  ADD COLUMN IF NOT EXISTS tipo_workflow VARCHAR(30) NOT NULL DEFAULT 'PQRS';

ALTER TABLE config_buzones
  DROP CONSTRAINT IF EXISTS config_buzones_tipo_workflow_check;
ALTER TABLE config_buzones
  ADD CONSTRAINT config_buzones_tipo_workflow_check
  CHECK (tipo_workflow IN ('PQRS', 'ATENCION_CLIENTE'));

COMMENT ON COLUMN config_buzones.tipo_workflow IS
  'Tipo de workflow que el worker aplica a los emails de este buzón. PQRS=clasificación legal con SLA; ATENCION_CLIENTE=consultas operativas sin plazo legal. Sprint FlexFintech 2026-05-27.';


ALTER TABLE pqrs_casos
  ADD COLUMN IF NOT EXISTS tipo_workflow VARCHAR(30) NOT NULL DEFAULT 'PQRS';

ALTER TABLE pqrs_casos
  DROP CONSTRAINT IF EXISTS pqrs_casos_tipo_workflow_check;
ALTER TABLE pqrs_casos
  ADD CONSTRAINT pqrs_casos_tipo_workflow_check
  CHECK (tipo_workflow IN ('PQRS', 'ATENCION_CLIENTE'));

CREATE INDEX IF NOT EXISTS pqrs_casos_workflow_idx
  ON pqrs_casos (cliente_id, tipo_workflow);

COMMENT ON COLUMN pqrs_casos.tipo_workflow IS
  'Workflow al que pertenece el caso (heredado del buzón de origen). Usado por dashboard y métricas para separar PQRS de Atención al Cliente.';


ALTER TABLE plantillas_respuesta
  ADD COLUMN IF NOT EXISTS tipo_workflow VARCHAR(30) NOT NULL DEFAULT 'PQRS';

ALTER TABLE plantillas_respuesta
  DROP CONSTRAINT IF EXISTS plantillas_respuesta_tipo_workflow_check;
ALTER TABLE plantillas_respuesta
  ADD CONSTRAINT plantillas_respuesta_tipo_workflow_check
  CHECK (tipo_workflow IN ('PQRS', 'ATENCION_CLIENTE'));

CREATE INDEX IF NOT EXISTS plantillas_respuesta_workflow_idx
  ON plantillas_respuesta (cliente_id, tipo_workflow, problematica)
  WHERE is_active = TRUE;

COMMENT ON COLUMN plantillas_respuesta.tipo_workflow IS
  'Workflow al que aplica la plantilla. El selector de plantillas filtra por (cliente_id, problematica, tipo_workflow). Default PQRS para no romper plantillas legacy.';


-- ─────────────────────────────────────────────────────────────────────────
-- Parte 2: email_respuesta_override en pqrs_casos
-- ─────────────────────────────────────────────────────────────────────────

ALTER TABLE pqrs_casos
  ADD COLUMN IF NOT EXISTS email_respuesta_override TEXT NULL;

COMMENT ON COLUMN pqrs_casos.email_respuesta_override IS
  'Si está seteado, el endpoint enviar-lote usa este email como destinatario en lugar de email_origen. Editable por admins/super_admin vía PATCH /casos/{id}/destinatario. Cambios auditados en audit_log_respuestas action=DESTINATARIO_EDITADO.';


-- ─────────────────────────────────────────────────────────────────────────
-- Parte 3: cédula plana
-- ─────────────────────────────────────────────────────────────────────────

ALTER TABLE pqrs_casos
  ADD COLUMN IF NOT EXISTS documento_peticionante VARCHAR(20) NULL;

CREATE INDEX IF NOT EXISTS pqrs_casos_documento_idx
  ON pqrs_casos (documento_peticionante)
  WHERE documento_peticionante IS NOT NULL;

COMMENT ON COLUMN pqrs_casos.documento_peticionante IS
  'Cédula del peticionante en texto plano (numeric only, sin puntos ni guiones). Extraída del cuerpo o del histórico email→cedula. Necesaria para nombrar carpetas SharePoint {cedula}_{fecha}/. Coexiste con documento_peticionante_hash para compatibilidad.';


-- ─────────────────────────────────────────────────────────────────────────
-- Parte 4: tabla historico_email_cedula (multi-tenant, RLS)
-- ─────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS historico_email_cedula (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  cliente_id    UUID NOT NULL REFERENCES clientes_tenant(id) ON DELETE CASCADE,
  email         VARCHAR(255) NOT NULL,
  cedula        VARCHAR(20)  NOT NULL,
  nombre        VARCHAR(255),
  primera_vez   TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  ultima_vez    TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  fuente        VARCHAR(50) DEFAULT 'manual',
  metadata      JSONB DEFAULT '{}'::jsonb,
  CONSTRAINT historico_email_cedula_unique UNIQUE (cliente_id, email)
);

CREATE INDEX IF NOT EXISTS historico_email_cedula_lookup_idx
  ON historico_email_cedula (cliente_id, lower(email));

CREATE INDEX IF NOT EXISTS historico_email_cedula_cedula_idx
  ON historico_email_cedula (cliente_id, cedula);

ALTER TABLE historico_email_cedula ENABLE ROW LEVEL SECURITY;
ALTER TABLE historico_email_cedula FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS historico_email_cedula_tenant_isolation ON historico_email_cedula;
CREATE POLICY historico_email_cedula_tenant_isolation ON historico_email_cedula
  USING (
    cliente_id::text = current_setting('app.current_tenant_id', true)
    OR current_setting('app.is_superuser', true) = 'true'
  )
  WITH CHECK (
    cliente_id::text = current_setting('app.current_tenant_id', true)
    OR current_setting('app.is_superuser', true) = 'true'
  );

COMMENT ON TABLE historico_email_cedula IS
  'Mapeo histórico email→cédula por tenant. Poblado desde los Excel Flex/ (~miles de pares). Consultado al ingresar un caso nuevo para autocompletar documento_peticionante cuando el body no incluye la cédula.';


-- ─────────────────────────────────────────────────────────────────────────
-- Parte 5: procesar_desde en config_buzones (cutoff date)
-- ─────────────────────────────────────────────────────────────────────────

ALTER TABLE config_buzones
  ADD COLUMN IF NOT EXISTS procesar_desde TIMESTAMP WITH TIME ZONE NULL;

COMMENT ON COLUMN config_buzones.procesar_desde IS
  'Cutoff date — el worker solo procesa mails con receivedDateTime >= procesar_desde. NULL = sin filtro (procesa cualquier mail unread). Usado al activar un buzón nuevo sobre una bandeja con mucho histórico unread que NO queremos reprocesar.';


-- ─────────────────────────────────────────────────────────────────────────
-- Parte 6: grants idempotentes a los roles existentes
-- ─────────────────────────────────────────────────────────────────────────

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pqrs_backend') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON historico_email_cedula TO pqrs_backend;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aequitas_worker') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON historico_email_cedula TO aequitas_worker;
  END IF;
END $$;


COMMIT;

-- ═══════════════════════════════════════════════════════════════════════════
-- Verificación post-migración (manual):
--
-- 1) Nuevas columnas
--   \d config_buzones       -- tipo_workflow + procesar_desde
--   \d pqrs_casos           -- tipo_workflow + email_respuesta_override + documento_peticionante
--   \d plantillas_respuesta -- tipo_workflow
--
-- 2) Nueva tabla
--   \d historico_email_cedula
--   SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='historico_email_cedula';
--
-- 3) Defaults aplican a filas existentes
--   SELECT count(*) FROM pqrs_casos WHERE tipo_workflow = 'PQRS';  -- todas
--   SELECT count(*) FROM config_buzones WHERE tipo_workflow = 'PQRS';  -- todas
--
-- 4) Comportamiento backward-compatible
--   - obtener_plantilla() debe seguir matcheando aunque no filtre por tipo_workflow (la app v1 lo agregará).
--   - master_worker_outlook sin cambios funcionales hasta que se agregue la lógica de iteración por workflow.
-- ═══════════════════════════════════════════════════════════════════════════
