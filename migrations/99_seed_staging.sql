-- ═══════════════════════════════════════════════════════════════
-- Migración 99: Seed sintético — EXCLUSIVO PARA STAGING
-- ═══════════════════════════════════════════════════════════════
-- GUARD RUNTIME: migrate.sh aborta si intenta correr un archivo
-- con prefijo 99_ cuando --env != staging.
--
-- PROPÓSITO: dejar staging con datos fake suficientes para que el
-- sprint Tutelas pueda correr pipelines y tests E2E.
--
-- REGLAS:
-- - UUIDs de tenants y usuarios están hardcoded con patrón
--   00000000-000X-... para ser inequívocamente NO productivos.
--   Los UUIDs reales de prod usan UUIDv4 generados.
-- - Ningún dato deriva de prod. Todo generado por generate_series,
--   md5, funciones determinísticas.
-- - Todos los casos TUTELA incluyen el marker "SYNTHETIC_FIXTURE_V1"
--   en el cuerpo para que los tests del sprint puedan filtrarlos.
-- - Password hash es bcrypt fake constante (no es el hash de una
--   password real; no crackeable).
-- ═══════════════════════════════════════════════════════════════

-- Desactivar RLS para el seed (lo haremos con app.is_superuser)
SET app.is_superuser = 'true';

-- ───────────────────────────────────────────────────────────────
-- 1. Tenants sintéticos (2)
-- ───────────────────────────────────────────────────────────────
INSERT INTO clientes_tenant (id, nombre, dominio, regimen_sla, is_active) VALUES
  ('00000000-0001-0001-0001-000000000001', 'ARC Staging (fake)', 'arc-staging.invalid', 'FINANCIERO', true),
  ('00000000-0002-0002-0002-000000000002', 'Demo Staging (fake)', 'demo-staging.invalid', 'GENERAL', true)
ON CONFLICT (id) DO NOTHING;

-- ───────────────────────────────────────────────────────────────
-- 2. Usuarios sintéticos (8 total, distribuidos entre ambos tenants)
-- ───────────────────────────────────────────────────────────────
-- Password hash fake: bcrypt-like format pero inválido para autenticar.
-- Nunca usarlo con código de login real; solo para satisfacer NOT NULL.
INSERT INTO usuarios (id, cliente_id, email, password_hash, nombre, rol, is_active) VALUES
  -- ARC Staging: 1 admin, 2 abogados, 2 analistas
  ('00000000-0001-1001-0001-000000000001', '00000000-0001-0001-0001-000000000001', 'admin@arc-staging.invalid',     '$2b$12$SYNTHETIC_HASH_DO_NOT_USE_FAKE_1', 'Admin Uno Staging',     'admin',    true),
  ('00000000-0001-2001-0001-000000000001', '00000000-0001-0001-0001-000000000001', 'abogado1@arc-staging.invalid',  '$2b$12$SYNTHETIC_HASH_DO_NOT_USE_FAKE_2', 'Abogado Uno Staging',   'abogado',  true),
  ('00000000-0001-2002-0001-000000000001', '00000000-0001-0001-0001-000000000001', 'abogado2@arc-staging.invalid',  '$2b$12$SYNTHETIC_HASH_DO_NOT_USE_FAKE_3', 'Abogado Dos Staging',   'abogado',  true),
  ('00000000-0001-3001-0001-000000000001', '00000000-0001-0001-0001-000000000001', 'analista1@arc-staging.invalid', '$2b$12$SYNTHETIC_HASH_DO_NOT_USE_FAKE_4', 'Analista Uno Staging',  'analista', true),
  ('00000000-0001-3002-0001-000000000001', '00000000-0001-0001-0001-000000000001', 'analista2@arc-staging.invalid', '$2b$12$SYNTHETIC_HASH_DO_NOT_USE_FAKE_5', 'Analista Dos Staging',  'analista', true),
  -- Demo Staging: 1 admin, 1 abogado, 1 analista
  ('00000000-0002-1001-0002-000000000002', '00000000-0002-0002-0002-000000000002', 'admin@demo-staging.invalid',    '$2b$12$SYNTHETIC_HASH_DO_NOT_USE_FAKE_6', 'Admin Demo Staging',    'admin',    true),
  ('00000000-0002-2001-0002-000000000002', '00000000-0002-0002-0002-000000000002', 'abogado@demo-staging.invalid',  '$2b$12$SYNTHETIC_HASH_DO_NOT_USE_FAKE_7', 'Abogado Demo Staging',  'abogado',  true),
  ('00000000-0002-3001-0002-000000000002', '00000000-0002-0002-0002-000000000002', 'analista@demo-staging.invalid', '$2b$12$SYNTHETIC_HASH_DO_NOT_USE_FAKE_8', 'Analista Demo Staging', 'analista', true)
ON CONFLICT (id) DO NOTHING;

-- ───────────────────────────────────────────────────────────────
-- 3. PQRS sintéticos — 20 casos variados en ARC Staging
-- (5 PETICION, 5 QUEJA, 5 RECLAMO, 5 SUGERENCIA)
-- ───────────────────────────────────────────────────────────────
INSERT INTO pqrs_casos (
  cliente_id, email_origen, asunto, cuerpo, tipo_caso, fecha_recibido, estado, external_msg_id
)
SELECT
  '00000000-0001-0001-0001-000000000001'::uuid,
  'peticionario' || i || '@fixture.invalid',
  'Asunto sintético ' || tipo || ' #' || i,
  'Este es un cuerpo generado sintéticamente para staging. Hash: ' || md5('fixture-' || tipo || '-' || i::text) ||
  '. No contiene datos reales de peticionarios.',
  tipo,
  NOW() - (i || ' hours')::interval,
  'ABIERTO',
  'FIXTURE_V1_' || tipo || '_' || i
FROM generate_series(1, 5) i
CROSS JOIN (VALUES ('PETICION'), ('QUEJA'), ('RECLAMO'), ('SUGERENCIA')) AS t(tipo);

-- ───────────────────────────────────────────────────────────────
-- 4. TUTELAS sintéticas — 5 casos con marker SYNTHETIC_FIXTURE_V1
-- (con textos que simulan escenarios DT-18 del sprint Tutelas)
-- ───────────────────────────────────────────────────────────────
INSERT INTO pqrs_casos (
  cliente_id, email_origen, asunto, cuerpo, tipo_caso, fecha_recibido, estado, external_msg_id, nivel_prioridad
)
VALUES
  ('00000000-0001-0001-0001-000000000001', 'juzgado01@fixture.invalid',
   'Notificación tutela - Expediente 11001-22-33-000-2026-00001',
   'SYNTHETIC_FIXTURE_V1 - Juzgado 1 Civil Municipal notifica acción de tutela radicada por peticionario ficticio. Accionante solicita protección al derecho de petición. Término de contestación: 2 días hábiles. (Caso 100% sintético, md5=' || md5('tutela-fixture-1') || ')',
   'TUTELA', NOW() - INTERVAL '30 minutes', 'ABIERTO', 'FIXTURE_V1_TUTELA_1', 'ALTA'),

  ('00000000-0001-0001-0001-000000000001', 'juzgado02@fixture.invalid',
   'Admisión de tutela - Radicado 2026-00002',
   'SYNTHETIC_FIXTURE_V1 - Juzgado 2 admite acción de tutela. Ordena notificar a entidad accionada. Hechos: presunta vulneración al derecho a la seguridad social. (Caso 100% sintético, md5=' || md5('tutela-fixture-2') || ')',
   'TUTELA', NOW() - INTERVAL '1 hour', 'ABIERTO', 'FIXTURE_V1_TUTELA_2', 'ALTA'),

  ('00000000-0001-0001-0001-000000000001', 'juzgado03@fixture.invalid',
   'Tutela - Derecho a la salud 2026-00003',
   'SYNTHETIC_FIXTURE_V1 - Acción de tutela por presunta negación de servicios de salud. Accionante solicita medida provisional. (Caso 100% sintético, md5=' || md5('tutela-fixture-3') || ')',
   'TUTELA', NOW() - INTERVAL '2 hours', 'ABIERTO', 'FIXTURE_V1_TUTELA_3', 'ALTA'),

  ('00000000-0001-0001-0001-000000000001', 'juzgado04@fixture.invalid',
   'Fallo de tutela - 2026-00004',
   'SYNTHETIC_FIXTURE_V1 - El juez de tutela tutela el derecho invocado y ordena cumplimiento en 48 horas. (Caso 100% sintético, md5=' || md5('tutela-fixture-4') || ')',
   'TUTELA', NOW() - INTERVAL '3 hours', 'ABIERTO', 'FIXTURE_V1_TUTELA_4', 'ALTA'),

  ('00000000-0001-0001-0001-000000000001', 'juzgado05@fixture.invalid',
   'Impugnación de tutela 2026-00005',
   'SYNTHETIC_FIXTURE_V1 - Impugnación a fallo de tutela. Remitido a juzgado de segunda instancia. (Caso 100% sintético, md5=' || md5('tutela-fixture-5') || ')',
   'TUTELA', NOW() - INTERVAL '4 hours', 'ABIERTO', 'FIXTURE_V1_TUTELA_5', 'ALTA');

-- ───────────────────────────────────────────────────────────────
-- 5. Verificaciones post-seed (no fallan, solo reportan)
-- ───────────────────────────────────────────────────────────────
DO $$
DECLARE
  v_tenants INT;
  v_users INT;
  v_casos INT;
  v_tutelas INT;
BEGIN
  SELECT COUNT(*) INTO v_tenants FROM clientes_tenant WHERE dominio LIKE '%.invalid';
  SELECT COUNT(*) INTO v_users FROM usuarios WHERE email LIKE '%@%.invalid';
  SELECT COUNT(*) INTO v_casos FROM pqrs_casos WHERE external_msg_id LIKE 'FIXTURE_V1_%';
  SELECT COUNT(*) INTO v_tutelas FROM pqrs_casos WHERE external_msg_id LIKE 'FIXTURE_V1_TUTELA_%';
  RAISE NOTICE 'Seed staging aplicado: % tenants fake, % usuarios fake, % casos sintéticos (% tutelas).',
    v_tenants, v_users, v_casos, v_tutelas;
END $$;
