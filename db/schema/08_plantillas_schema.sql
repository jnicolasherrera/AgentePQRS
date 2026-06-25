-- Tabla de plantillas de respuesta (multi-tenant)
CREATE TABLE IF NOT EXISTS plantillas_respuesta (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id    UUID REFERENCES clientes_tenant(id) ON DELETE CASCADE,
    problematica  VARCHAR(100) NOT NULL,
    contexto      TEXT,
    cuerpo        TEXT NOT NULL,
    keywords      TEXT[],
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_plantillas_tenant ON plantillas_respuesta(cliente_id, problematica);

-- Columnas nuevas en pqrs_casos para flujo de borradores
ALTER TABLE pqrs_casos
    ADD COLUMN IF NOT EXISTS borrador_respuesta     TEXT,
    ADD COLUMN IF NOT EXISTS borrador_estado        VARCHAR(20) DEFAULT 'SIN_PLANTILLA',
    ADD COLUMN IF NOT EXISTS problematica_detectada VARCHAR(100),
    ADD COLUMN IF NOT EXISTS plantilla_id           UUID REFERENCES plantillas_respuesta(id),
    ADD COLUMN IF NOT EXISTS aprobado_por           UUID REFERENCES usuarios(id),
    ADD COLUMN IF NOT EXISTS aprobado_at            TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS enviado_at             TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_pqrs_borrador_estado ON pqrs_casos(cliente_id, borrador_estado)
    WHERE borrador_estado = 'PENDIENTE';

-- Audit log inmutable de respuestas enviadas
CREATE TABLE IF NOT EXISTS audit_log_respuestas (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    caso_id     UUID REFERENCES pqrs_casos(id),
    usuario_id  UUID REFERENCES usuarios(id),
    accion      VARCHAR(30) NOT NULL,  -- BORRADOR_GENERADO | BORRADOR_EDITADO | ENVIADO_LOTE | RECHAZADO
    lote_id     UUID,
    ip_origen   INET,
    metadata    JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_caso    ON audit_log_respuestas(caso_id);
CREATE INDEX IF NOT EXISTS idx_audit_lote    ON audit_log_respuestas(lote_id);
CREATE INDEX IF NOT EXISTS idx_audit_usuario ON audit_log_respuestas(usuario_id, created_at DESC);
