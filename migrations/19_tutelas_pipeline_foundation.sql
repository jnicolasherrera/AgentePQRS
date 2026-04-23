-- ═══════════════════════════════════════════════════════════════
-- Migración 19: Fundación del pipeline de tutelas
-- ═══════════════════════════════════════════════════════════════
-- Agrega:
-- * metadata_especifica JSONB en pqrs_casos (polimórfico por tipo)
-- * columnas tutela_* para seguimiento post-respuesta
-- * documento_peticionante_hash para dedup cross-tenant con salt
-- * config_hash_salt en clientes_tenant (por-tenant, random 32 bytes)
-- * 3 índices: GIN metadata, plazo tutela, doc hash
-- * trigger fn_set_fecha_vencimiento en versión híbrida:
--     (1) respeta fecha_vencimiento si ya viene seteado (pipeline Python)
--     (2) TUTELA con metadata CALENDARIO calcula en el trigger
--     (3) fallback al SP calcular_fecha_vencimiento con default sectorial
-- ═══════════════════════════════════════════════════════════════

-- ── 1. metadata_especifica: JSONB polimórfico por tipo de caso ────
ALTER TABLE pqrs_casos
    ADD COLUMN IF NOT EXISTS metadata_especifica JSONB DEFAULT '{}'::jsonb;

COMMENT ON COLUMN pqrs_casos.metadata_especifica IS
    'Metadata específica del tipo_caso en JSONB. Ej. TUTELA: {expediente, juzgado, accionante, plazo_informe_horas, plazo_tipo}. PETICION: {asunto_categoria, entidad_destino}. Poblado por worker Python post-extracción.';

-- ── 2. Columnas tutela para post-respuesta ────────────────────────
ALTER TABLE pqrs_casos
    ADD COLUMN IF NOT EXISTS tutela_informe_rendido_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS tutela_fallo_sentido VARCHAR(20),
    ADD COLUMN IF NOT EXISTS tutela_riesgo_desacato VARCHAR(10) DEFAULT 'BAJO';

COMMENT ON COLUMN pqrs_casos.tutela_informe_rendido_at IS
    'Timestamp de cuando el abogado rindió el informe de tutela al juzgado. NULL hasta que se firma y envía.';
COMMENT ON COLUMN pqrs_casos.tutela_fallo_sentido IS
    'Sentido del fallo del juez: FAVORABLE, DESFAVORABLE, PARCIAL, IMPUGNADO. NULL mientras no hay fallo.';
COMMENT ON COLUMN pqrs_casos.tutela_riesgo_desacato IS
    'Riesgo de desacato calculado por el sistema: BAJO, MEDIO, ALTO. Default BAJO.';

-- ── 3. Hash del documento del peticionante (dedup cross-tenant) ──
ALTER TABLE pqrs_casos
    ADD COLUMN IF NOT EXISTS documento_peticionante_hash VARCHAR(64);

COMMENT ON COLUMN pqrs_casos.documento_peticionante_hash IS
    'SHA-256 hex del documento del peticionante (cédula/NIT), salteado con config_hash_salt del tenant. Permite detectar multi-radicación sin exponer el documento en claro.';

-- ── 4. Salt por tenant ────────────────────────────────────────────
ALTER TABLE clientes_tenant
    ADD COLUMN IF NOT EXISTS config_hash_salt VARCHAR(64);

UPDATE clientes_tenant
SET config_hash_salt = encode(gen_random_bytes(32), 'hex')
WHERE config_hash_salt IS NULL;

COMMENT ON COLUMN clientes_tenant.config_hash_salt IS
    'Salt criptográfico por tenant (32 bytes hex) para documento_peticionante_hash. Generado una sola vez al crear el tenant. Rotarlo invalida todos los hashes del tenant — hacerlo solo en migración controlada.';

-- ── 5. Índices ────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_casos_metadata_gin
    ON pqrs_casos USING GIN (metadata_especifica);

CREATE INDEX IF NOT EXISTS idx_casos_tutela_vencimiento
    ON pqrs_casos ((metadata_especifica->>'plazo_informe_horas'))
    WHERE tipo_caso = 'TUTELA';

CREATE INDEX IF NOT EXISTS idx_casos_doc_hash
    ON pqrs_casos (cliente_id, documento_peticionante_hash)
    WHERE documento_peticionante_hash IS NOT NULL;

-- ── 6. Trigger híbrido fn_set_fecha_vencimiento ──────────────────
-- Reemplaza la versión de la 14 (que ya respetaba tipo_caso/fecha_recibido)
-- por la versión híbrida decidida en sprint Tutelas S1:
--   (1) si el pipeline Python ya pobló NEW.fecha_vencimiento → RETURN NEW (respeta).
--   (2) TUTELA con metadata_especifica.plazo_tipo = 'CALENDARIO' → calcula aquí
--       como fecha_recibido + plazo_informe_horas * INTERVAL '1 hour' (horas reloj).
--   (3) fallback al SP calcular_fecha_vencimiento con el default sectorial
--       (HABILES según régimen del tenant). TUTELA cae aquí y toma 2 días hábiles.
--
-- Nota diseño: el plazo HABILES no se resuelve en el trigger (la aritmética
-- de horas hábiles es compleja y vive en Python/sla_engine). Si el pipeline
-- Python no llegó a calcularlo y el caso es HABILES, se degrada al SP — es
-- degradación controlada documentada en TEST B del Agente 1.
--
-- Usa NEW.fecha_recibido como anchor del SLA (coherente con el trigger
-- vigente de la 14 y con el SP). fecha_creacion NO existe como columna.

CREATE OR REPLACE FUNCTION fn_set_fecha_vencimiento() RETURNS TRIGGER AS $$
DECLARE
    v_plazo_horas INTEGER;
    v_plazo_tipo  VARCHAR;
BEGIN
    -- (1) Respeta el valor que vino del pipeline Python.
    IF NEW.fecha_vencimiento IS NOT NULL THEN
        RETURN NEW;
    END IF;

    -- (2) Defense in depth: TUTELA con metadata CALENDARIO calcula aquí mismo.
    IF NEW.tipo_caso = 'TUTELA'
       AND NEW.metadata_especifica IS NOT NULL
       AND NEW.metadata_especifica != '{}'::jsonb
    THEN
        v_plazo_horas := (NEW.metadata_especifica->>'plazo_informe_horas')::INTEGER;
        v_plazo_tipo  := NEW.metadata_especifica->>'plazo_tipo';

        IF v_plazo_horas IS NOT NULL AND v_plazo_tipo = 'CALENDARIO' THEN
            NEW.fecha_vencimiento := NEW.fecha_recibido
                + (v_plazo_horas || ' hours')::INTERVAL;
            RETURN NEW;
        END IF;
        -- plazo_tipo = HABILES sin pipeline Python → cae al SP.
    END IF;

    -- (3) Fallback: SP calcula según régimen del tenant + tipo_caso.
    IF NEW.tipo_caso IS NOT NULL AND NEW.fecha_recibido IS NOT NULL THEN
        NEW.fecha_vencimiento := calcular_fecha_vencimiento(
            NEW.fecha_recibido,
            NEW.cliente_id,
            NEW.tipo_caso
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- El trigger tg_set_fecha_vencimiento ya está creado por la 14.
-- CREATE OR REPLACE FUNCTION reemplaza la función en su lugar sin re-crear trigger.
