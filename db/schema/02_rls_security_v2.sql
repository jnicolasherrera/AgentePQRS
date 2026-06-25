-- Configuración de Seguridad de Filas (Row-Level Security - RLS)
-- Fecha: 21 Febrero 2026
-- Objetivo: Aislamiento estricto de Tenants (Multitenancy)

-- 1. Habilitamos el Motor de Seguridad RLS en las tablas críticas
ALTER TABLE usuarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE pqrs_casos ENABLE ROW LEVEL SECURITY;

-- 2. POLÍTICA DE SEGURIDAD PARA `usuarios`
-- Un usuario SOLO puede ver y modificar los usuarios que pertenezcan a su propio `cliente_id` (Tenant).
-- Excepción: Un "Superadmin del sistema" (nuestro equipo) que no usa RLS.
CREATE POLICY tenant_isolation_usuarios_policy
    ON usuarios
    AS PERMISSIVE
    FOR ALL
    TO public
    USING (cliente_id = current_setting('app.current_tenant_id', true)::UUID)
    WITH CHECK (cliente_id = current_setting('app.current_tenant_id', true)::UUID);

-- 3. POLÍTICA DE SEGURIDAD PARA `pqrs_casos`
-- Un caso PQRS SOLO puede ser visto o editado por el Tenant al que pertenece.
-- Esto asegura que Abogados Recovery jamás cruce un correo con el Gobierno u otro cliente.
CREATE POLICY tenant_isolation_pqrs_policy
    ON pqrs_casos
    AS PERMISSIVE
    FOR ALL
    TO public
    USING (cliente_id = current_setting('app.current_tenant_id', true)::UUID)
    WITH CHECK (cliente_id = current_setting('app.current_tenant_id', true)::UUID);

-- 4. Opcional pero recomendado: Forzamos el RLS incluso para los dueños de las tablas
ALTER TABLE usuarios FORCE ROW LEVEL SECURITY;
ALTER TABLE pqrs_casos FORCE ROW LEVEL SECURITY;
