-- ============================================================
-- 15_tutelas_escaladas.sql — Tracking de tutelas escaladas de PQR previo
--
-- Feature: detectar si una TUTELA entrante es consecuencia de un PQR previo
-- no resuelto del mismo demandante (señal de mala atención del servicio).
--
-- Estrategia (poblado por master_worker_outlook.py al ingestar):
--   A. Match por email_origen (mismo demandante) en últimos 90 días.
--   B. Parseo de radicados citados en el cuerpo de la tutela.
--   D. Vinculación/desvinculación manual desde el detalle del caso (UI — follow-up).
--
-- Idempotente: IF NOT EXISTS en column + index.
-- ============================================================

ALTER TABLE pqrs_casos
  ADD COLUMN IF NOT EXISTS pqr_origenes UUID[] DEFAULT '{}';

COMMENT ON COLUMN pqrs_casos.pqr_origenes IS
  'Solo poblado para tipo_caso=TUTELA. Array de IDs de PQRs previos del mismo '
  'email_origen en últimos 90 días (auto-match en ingestión) o vinculados '
  'manualmente desde la UI. array_length>0 ⇒ tutela escalada de PQR previo.';

-- GIN index para queries del tipo "tutelas con pqr_origenes no vacío"
-- y para futuras búsquedas inversas (qué tutelas vinieron de este PQR).
CREATE INDEX IF NOT EXISTS idx_pqrs_casos_pqr_origenes
  ON pqrs_casos USING GIN (pqr_origenes);
