-- Migración Inicial PQRS V2 (SQL Puro)
-- Fecha: 21 Febrero 2026

-- 1. Habilitar extensión UUID (si no existe)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Tabla de Clientes (Tenant)
CREATE TABLE IF NOT EXISTS clientes_tenant (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre VARCHAR(255) NOT NULL,
    dominio VARCHAR(255) UNIQUE NOT NULL, -- ej. abogadosrecovery.com
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tabla de Usuarios (Ligada obligatoriamente a un Tenant)
CREATE TABLE IF NOT EXISTS usuarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cliente_id UUID NOT NULL REFERENCES clientes_tenant(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nombre VARCHAR(255) NOT NULL,
    rol VARCHAR(50) DEFAULT 'abogado', -- roles: admin, abogado, bot
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Tabla de PQRS (Nuestros Casos / Transaccional Puro)
CREATE TABLE IF NOT EXISTS pqrs_casos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cliente_id UUID NOT NULL REFERENCES clientes_tenant(id) ON DELETE CASCADE,
    email_origen VARCHAR(255) NOT NULL,
    asunto VARCHAR(500) NOT NULL,
    cuerpo TEXT,
    estado VARCHAR(50) DEFAULT 'ABIERTO', -- ABIERTO, EN_PROGRESO, CERRADO
    nivel_prioridad VARCHAR(50) DEFAULT 'NORMAL',
    fecha_recibido TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índices para escalabilidad
CREATE INDEX IF NOT EXISTS idx_usuarios_cliente_id ON usuarios(cliente_id);
CREATE INDEX IF NOT EXISTS idx_pqrs_cliente_id ON pqrs_casos(cliente_id);
CREATE INDEX IF NOT EXISTS idx_pqrs_estado ON pqrs_casos(estado);
