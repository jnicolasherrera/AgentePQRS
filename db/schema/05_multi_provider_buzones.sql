-- Migración: Soporte Multi-Proveedor (Outlook + Zoho)
-- Fecha: 25 Febrero 2026

-- 1. Agregar columna de proveedor
ALTER TABLE config_buzones ADD COLUMN IF NOT EXISTS proveedor VARCHAR(50) DEFAULT 'OUTLOOK';

-- 2. Agregar campos específicos para Zoho
ALTER TABLE config_buzones ADD COLUMN IF NOT EXISTS zoho_refresh_token TEXT;
ALTER TABLE config_buzones ADD COLUMN IF NOT EXISTS zoho_account_id VARCHAR(255);

-- 3. Limpiar y re-insertar Abogados Recovery con Zoho
DELETE FROM config_buzones WHERE email_buzon = 'pqrs@arcsas.com.co';

-- ID de Abogados Recovery ya creado: effca814-b0b5-4329-96be-186c0333ad4b
INSERT INTO config_buzones (
    cliente_id, 
    email_buzon, 
    proveedor,
    azure_folder_id, -- No se usa en Zoho pero la tabla lo pide NOT NULL
    azure_client_id, 
    azure_client_secret, 
    zoho_refresh_token, 
    zoho_account_id
) VALUES (
    'effca814-b0b5-4329-96be-186c0333ad4b', 
    'pqrs@arcsas.com.co', 
    'ZOHO',
    'ZOHO_INBOX',
    '1000.TKA5AEC621AB1NISPL1YEN08VKRHAC',
    '568f75dac62845e5d8e4caff0deef488c2896803cd',
    '1000.1b69662a184a373bc3171bb906733499.1c2be417d333b565605751d1e126fc5c',
    '2429327000000008002'
);
