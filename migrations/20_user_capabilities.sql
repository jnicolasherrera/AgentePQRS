-- ═══════════════════════════════════════════════════════════════
-- Migración 20: Tabla user_capabilities + RLS + grants default ARC
-- ═══════════════════════════════════════════════════════════════
-- Modelo:
-- * Capabilities granulares por usuario, con scope (p.ej. tipo de caso).
-- * RLS aislado por tenant usando current_setting('app.current_tenant_id').
-- * Grants default para el sprint Tutelas:
--     CAN_SIGN_DOCUMENT scope TUTELA  → abogados + analistas ARC
--     CAN_APPROVE_RESPONSE scope TUTELA → abogados + analistas ARC
--
-- Para matchear "ARC" en cualquier ambiente se usan los dos UUIDs
-- conocidos: el productivo (effca814-...) y el staging fake
-- (00000000-0001-0001-0001-000000000001). En prod el staging UUID
-- matcheará 0 filas, en staging el productivo también 0. Solo el
-- ARC real del ambiente recibe grants.
-- ═══════════════════════════════════════════════════════════════

-- ── 1. Tabla user_capabilities ────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_capabilities (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id   UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    cliente_id   UUID NOT NULL REFERENCES clientes_tenant(id) ON DELETE CASCADE,
    capability   VARCHAR(64) NOT NULL,
    scope        VARCHAR(64),
    granted_by   UUID REFERENCES usuarios(id),
    granted_at   TIMESTAMPTZ DEFAULT NOW(),
    revoked_at   TIMESTAMPTZ,
    UNIQUE (usuario_id, capability, scope)
);

COMMENT ON TABLE user_capabilities IS
    'Capabilities granulares por usuario con scope opcional (típicamente tipo_caso). Scope NULL = capability global. Revocación por revoked_at, no por DELETE, para auditoría.';
COMMENT ON COLUMN user_capabilities.capability IS
    'Nombre de la capability. Ej: CAN_SIGN_DOCUMENT, CAN_APPROVE_RESPONSE, CAN_IMPERSONATE_TENANT.';
COMMENT ON COLUMN user_capabilities.scope IS
    'Scope opcional de la capability. Ej: TUTELA, PETICION, *. NULL = todos los tipos.';

-- ── 2. Índices ────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_user_caps_usuario
    ON user_capabilities (usuario_id) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_user_caps_capability_scope
    ON user_capabilities (capability, scope) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_user_caps_cliente
    ON user_capabilities (cliente_id);

-- ── 3. RLS ────────────────────────────────────────────────────────
ALTER TABLE user_capabilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_capabilities FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_user_caps_policy ON user_capabilities;
CREATE POLICY tenant_isolation_user_caps_policy ON user_capabilities
    AS PERMISSIVE FOR ALL TO public
    USING (
        cliente_id = current_setting('app.current_tenant_id', true)::UUID
        OR current_setting('app.is_superuser', true) = 'true'
    )
    WITH CHECK (
        cliente_id = current_setting('app.current_tenant_id', true)::UUID
        OR current_setting('app.is_superuser', true) = 'true'
    );

-- ── 4. Grants default ARC — CAN_SIGN_DOCUMENT scope TUTELA ────────
INSERT INTO user_capabilities (usuario_id, cliente_id, capability, scope)
SELECT u.id, u.cliente_id, 'CAN_SIGN_DOCUMENT', 'TUTELA'
FROM usuarios u
WHERE u.cliente_id IN (
        'effca814-b0b5-4329-96be-186c0333ad4b'::uuid,  -- ARC prod
        '00000000-0001-0001-0001-000000000001'::uuid    -- ARC staging fake
      )
  AND u.rol IN ('abogado', 'analista')
  AND u.is_active = true
ON CONFLICT (usuario_id, capability, scope) DO NOTHING;

-- ── 5. Grants default ARC — CAN_APPROVE_RESPONSE scope TUTELA ─────
INSERT INTO user_capabilities (usuario_id, cliente_id, capability, scope)
SELECT u.id, u.cliente_id, 'CAN_APPROVE_RESPONSE', 'TUTELA'
FROM usuarios u
WHERE u.cliente_id IN (
        'effca814-b0b5-4329-96be-186c0333ad4b'::uuid,
        '00000000-0001-0001-0001-000000000001'::uuid
      )
  AND u.rol IN ('abogado', 'analista')
  AND u.is_active = true
ON CONFLICT (usuario_id, capability, scope) DO NOTHING;

-- ── 6. Reporte de grants aplicados ────────────────────────────────
DO $$
DECLARE
    v_grants INT;
BEGIN
    SELECT COUNT(*) INTO v_grants
    FROM user_capabilities
    WHERE capability IN ('CAN_SIGN_DOCUMENT', 'CAN_APPROVE_RESPONSE')
      AND scope = 'TUTELA'
      AND revoked_at IS NULL;
    RAISE NOTICE 'Migración 20: % grants default TUTELA aplicados a abogados/analistas ARC.', v_grants;
END $$;
