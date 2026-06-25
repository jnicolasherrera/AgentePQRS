-- Migración: Gestión Multicliente y Super Usuarios
-- Fecha: 25 Febrero 2026

-- 1. Tabla de Configuración de Buzones por Cliente
-- Permite que el sistema sea dinámico: agregas una fila y el worker empieza a leer ese Outlook.
CREATE TABLE IF NOT EXISTS config_buzones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cliente_id UUID NOT NULL REFERENCES clientes_tenant(id) ON DELETE CASCADE,
    email_buzon VARCHAR(255) NOT NULL,
    azure_folder_id VARCHAR(500) NOT NULL,
    azure_client_id VARCHAR(255), -- Si el cliente usa su propia App Registration
    azure_client_secret VARCHAR(255),
    azure_tenant_id VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    last_sync TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Habilitar RLS en config_buzones
-- Nota: Solo los admins del cliente o el SuperUser pueden ver esto.
ALTER TABLE config_buzones ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_config_policy ON config_buzones AS PERMISSIVE FOR ALL TO public
USING (
    cliente_id = current_setting('app.current_tenant_id', true)::UUID 
    OR current_setting('app.is_superuser', true) = 'true'
);

-- 3. Actualizar Políticas de RLS existentes para permitir BYPASS a Super Usuarios
-- Vamos a recrearlas con la condición de 'app.is_superuser'

DROP POLICY IF EXISTS tenant_isolation_usuarios_policy ON usuarios;
CREATE POLICY tenant_isolation_usuarios_policy ON usuarios AS PERMISSIVE FOR ALL TO public
USING (
    cliente_id = current_setting('app.current_tenant_id', true)::UUID 
    OR current_setting('app.is_superuser', true) = 'true'
);

DROP POLICY IF EXISTS tenant_isolation_pqrs_policy ON pqrs_casos;
CREATE POLICY tenant_isolation_pqrs_policy ON pqrs_casos AS PERMISSIVE FOR ALL TO public
USING (
    cliente_id = current_setting('app.current_tenant_id', true)::UUID 
    OR current_setting('app.is_superuser', true) = 'true'
);

DROP POLICY IF EXISTS tenant_isolation_adjuntos_policy ON pqrs_adjuntos;
CREATE POLICY tenant_isolation_adjuntos_policy ON pqrs_adjuntos AS PERMISSIVE FOR ALL TO public
USING (
    cliente_id = current_setting('app.current_tenant_id', true)::UUID 
    OR current_setting('app.is_superuser', true) = 'true'
);

DROP POLICY IF EXISTS tenant_isolation_comentarios_policy ON pqrs_comentarios;
CREATE POLICY tenant_isolation_comentarios_policy ON pqrs_comentarios AS PERMISSIVE FOR ALL TO public
USING (
    cliente_id = current_setting('app.current_tenant_id', true)::UUID 
    OR current_setting('app.is_superuser', true) = 'true'
);

-- 4. Insertar la configuración inicial para Flexfintech (Migrar lo que estaba hardcoded)
-- ID Flexfintech: a1b2c3d4-e5f6-7890-1234-56789abcdef0
INSERT INTO config_buzones (cliente_id, email_buzon, azure_folder_id)
VALUES (
    'a1b2c3d4-e5f6-7890-1234-56789abcdef0', 
    'clientes@flexfintech.com', 
    'AAMkADUxOGI3MjNmLTRmYjYtNDRlMC04ZjdkLTI5NWI5NTVlMTYwYQAuAAAAAAAfifyJAfEXQb8nwih5Ou3GAQA_6g6Es0c0QJlfW-ufh7p9AADpbc9rAAA='
) ON CONFLICT DO NOTHING;

-- 5. Insertar configuración para Cliente 2
-- ID Cliente 2: d1cf5e93-4121-4124-abf7-0f8dc1b070a9
INSERT INTO config_buzones (cliente_id, email_buzon, azure_folder_id)
VALUES (
    'd1cf5e93-4121-4124-abf7-0f8dc1b070a9', 
    'clientes@cliente2.com', 
    'AAMkADUxOGI3MjNmLTRmYjYtNDRlMC04ZjdkLTI5NWI5NTVlMTYwYQAuAAAAAAAfifyJAfEXQb8nwih5Ou3GAQA_6g6Es0c0QJlfW-ufh7p9AADpbc9rAAA=' -- Mock ID
) ON CONFLICT DO NOTHING;
