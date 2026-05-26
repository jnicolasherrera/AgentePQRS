-- ============================================================
-- backfill_tutelas_escaladas.sql
--
-- Para cada TUTELA existente, busca PQRs previos del mismo demandante
-- (mismo cliente_id + mismo email_origen) recibidos en los 90 días
-- ANTES de la tutela, y los registra en pqr_origenes.
--
-- Solo aplica estrategia A (match por email). El detector del worker
-- (master_worker_outlook.py) también aplica B (radicado citado en cuerpo);
-- esa parte requiere parseo Python y solo se ejecuta para tutelas NUEVAS.
--
-- Idempotente: el UPDATE sobrescribe pqr_origenes con el resultado actual
-- (si ya estaba populado, queda igual o se actualiza).
--
-- Aplicar con role pqrs_admin (BYPASSRLS) para evitar problemas de policies:
--   docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 < backfill_tutelas_escaladas.sql
-- ============================================================

BEGIN;

WITH origenes AS (
  SELECT
    t.id AS tutela_id,
    COALESCE(ARRAY_AGG(p.id) FILTER (WHERE p.id IS NOT NULL), '{}'::uuid[]) AS ids
  FROM pqrs_casos t
  LEFT JOIN pqrs_casos p
    ON p.cliente_id        = t.cliente_id
   AND LOWER(p.email_origen) = LOWER(t.email_origen)
   AND p.tipo_caso         != 'TUTELA'
   AND p.id                != t.id
   AND p.fecha_recibido    <  t.fecha_recibido
   AND p.fecha_recibido    >= t.fecha_recibido - INTERVAL '90 days'
  WHERE t.tipo_caso = 'TUTELA'
  GROUP BY t.id
)
UPDATE pqrs_casos t
SET pqr_origenes = o.ids
FROM origenes o
WHERE t.id = o.tutela_id
  AND t.pqr_origenes IS DISTINCT FROM o.ids;

-- Métricas post-backfill
SELECT
  COUNT(*) AS tutelas_total,
  COUNT(*) FILTER (WHERE COALESCE(array_length(pqr_origenes,1),0) > 0) AS tutelas_con_origenes,
  ROUND(
    COUNT(*) FILTER (WHERE COALESCE(array_length(pqr_origenes,1),0) > 0)::numeric
    / NULLIF(COUNT(*), 0) * 100, 1
  ) AS tasa_escalamiento_pct
FROM pqrs_casos
WHERE tipo_caso = 'TUTELA';

COMMIT;
