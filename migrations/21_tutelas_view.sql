-- ═══════════════════════════════════════════════════════════════
-- Migración 21: MATERIALIZED VIEW tutelas_view polimórfica
-- ═══════════════════════════════════════════════════════════════
-- Expone los casos TUTELA con los campos extraídos de
-- metadata_especifica JSONB como columnas planas, para consumo fácil
-- por el frontend y la BI sin tener que derivar cada vez.
--
-- ⚠️ IMPORTANTE — RLS NO HEREDA:
-- PostgreSQL NO propaga Row-Level Security de la tabla base a las
-- materialized views. Los SELECT sobre tutelas_view NO están aislados
-- por tenant a nivel DB. Cualquier consumidor que acceda a esta vista
-- DEBE filtrar explícitamente por cliente_id, o acceder mediante un
-- wrapper SQL/función que incorpore el filtro.
--
-- Alternativas consideradas y descartadas:
-- * Vista normal (no materializada): RLS sí hereda, pero el overhead
--   de parsear JSONB en cada query pesa. Preferimos materializar con
--   refresh periódico + filtro explícito.
-- * Row-level VIEW con SECURITY DEFINER function wrapper: agrega
--   latencia no justificable para la SLA operativa de tutelas.
--
-- Refresh: la vista se refresca manualmente por cron o por el worker
-- después de ingestar una tutela nueva. REFRESH CONCURRENTLY requiere
-- un índice UNIQUE (creado abajo).
-- ═══════════════════════════════════════════════════════════════

DROP MATERIALIZED VIEW IF EXISTS tutelas_view;

CREATE MATERIALIZED VIEW tutelas_view AS
SELECT
    c.id,
    c.cliente_id,
    c.numero_radicado,
    c.email_origen,
    c.asunto,
    c.estado,
    c.nivel_prioridad,
    c.fecha_recibido,
    c.fecha_vencimiento,
    c.semaforo_sla,
    c.tipo_caso,
    c.asignado_a,
    c.fecha_asignacion,
    c.alerta_2h_enviada,
    c.numero_radicado   AS radicado_interno,
    -- Campos derivados de metadata_especifica JSONB:
    (c.metadata_especifica->>'expediente')                    AS expediente,
    (c.metadata_especifica->>'juzgado')                       AS juzgado,
    (c.metadata_especifica->>'accionante')                    AS accionante,
    (c.metadata_especifica->>'accionado')                     AS accionado,
    (c.metadata_especifica->>'plazo_informe_horas')::INTEGER  AS plazo_informe_horas,
    (c.metadata_especifica->>'plazo_tipo')                    AS plazo_tipo,
    (c.metadata_especifica->>'derechos_invocados')            AS derechos_invocados,
    -- Columnas tutela-específicas de pqrs_casos:
    c.tutela_informe_rendido_at,
    c.tutela_fallo_sentido,
    c.tutela_riesgo_desacato,
    c.documento_peticionante_hash,
    -- Estado de borrador / aprobación:
    c.borrador_estado,
    c.aprobado_por,
    c.aprobado_at,
    c.enviado_at,
    -- Timestamps:
    c.created_at,
    c.updated_at
FROM pqrs_casos c
WHERE c.tipo_caso = 'TUTELA';

COMMENT ON MATERIALIZED VIEW tutelas_view IS
    'Vista materializada polimórfica de casos TUTELA expandiendo metadata_especifica. ⚠️ RLS NO HEREDA — los consumidores deben filtrar por cliente_id explícitamente o usar un wrapper SQL con SET LOCAL app.current_tenant_id. Refresh vía REFRESH MATERIALIZED VIEW CONCURRENTLY tutelas_view (requiere índice UNIQUE creado debajo).';

-- ── Índices ───────────────────────────────────────────────────────
-- Único para REFRESH CONCURRENTLY + acceso por (tenant, id).
CREATE UNIQUE INDEX IF NOT EXISTS idx_tutelas_view_pk
    ON tutelas_view (cliente_id, id);

-- Búsqueda por expediente judicial (textual, no único — podría repetirse).
CREATE INDEX IF NOT EXISTS idx_tutelas_view_expediente
    ON tutelas_view (expediente) WHERE expediente IS NOT NULL;

-- Filtrado operativo por semáforo dentro del tenant (listas rojas/negro/etc.).
CREATE INDEX IF NOT EXISTS idx_tutelas_view_semaforo
    ON tutelas_view (cliente_id, semaforo_sla);
