-- Migración: Características Avanzadas (Adjuntos y Comentarios)
-- Fecha: 25 Febrero 2026

-- 1. Tabla de Adjuntos (Archivos en MinIO/S3)
CREATE TABLE IF NOT EXISTS pqrs_adjuntos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    caso_id UUID NOT NULL REFERENCES pqrs_casos(id) ON DELETE CASCADE,
    nombre_archivo VARCHAR(255) NOT NULL,
    storage_path VARCHAR(500) NOT NULL, -- Ruta en el Bucket MinIO
    content_type VARCHAR(100),
    tamano_bytes BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabla de Comentarios / Auditoría (Audit Log)
CREATE TABLE IF NOT EXISTS pqrs_comentarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    caso_id UUID NOT NULL REFERENCES pqrs_casos(id) ON DELETE CASCADE,
    usuario_id UUID REFERENCES usuarios(id), -- Quien hizo el comentario
    comentario TEXT NOT NULL,
    tipo_evento VARCHAR(50) DEFAULT 'COMENTARIO', -- COMENTARIO, CAMBIO_ESTADO, IA_DRAFT
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Habilitar RLS en nuevas tablas (Heredado del Tenant del Caso)
-- Nota: Para simplificar la política, podríamos agregar cliente_id a estas tablas 
-- o hacer un JOIN en la política. Agregaremos cliente_id para máxima velocidad en RLS.

ALTER TABLE pqrs_adjuntos ADD COLUMN IF NOT EXISTS cliente_id UUID NOT NULL REFERENCES clientes_tenant(id) ON DELETE CASCADE;
ALTER TABLE pqrs_comentarios ADD COLUMN IF NOT EXISTS cliente_id UUID NOT NULL REFERENCES clientes_tenant(id) ON DELETE CASCADE;

ALTER TABLE pqrs_adjuntos ENABLE ROW LEVEL SECURITY;
ALTER TABLE pqrs_comentarios ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_adjuntos_policy ON pqrs_adjuntos AS PERMISSIVE FOR ALL TO public
USING (cliente_id = current_setting('app.current_tenant_id', true)::UUID)
WITH CHECK (cliente_id = current_setting('app.current_tenant_id', true)::UUID);

CREATE POLICY tenant_isolation_comentarios_policy ON pqrs_comentarios AS PERMISSIVE FOR ALL TO public
USING (cliente_id = current_setting('app.current_tenant_id', true)::UUID)
WITH CHECK (cliente_id = current_setting('app.current_tenant_id', true)::UUID);

-- Índices
CREATE INDEX IF NOT EXISTS idx_adjuntos_caso_id ON pqrs_adjuntos(caso_id);
CREATE INDEX IF NOT EXISTS idx_comentarios_caso_id ON pqrs_comentarios(caso_id);
