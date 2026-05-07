-- ═══════════════════════════════════════════════════════════════
-- Migración 14: Régimen Sectorial por Tenant
-- Normativa: SFC Circular Básica Jurídica — QUEJA/RECLAMO = 8 días
-- ═══════════════════════════════════════════════════════════════
-- DIVERGENCIA vs aequitas_infrastructure/database/14_regimen_sectorial.sql:
-- Esta versión REMUEVE la línea `NEW.semaforo_sla := 'VERDE';` del
-- trigger `fn_set_fecha_vencimiento`. Razón: `semaforo_sla` no existe
-- ni en el schema de prod ni en ninguna migración del repo (ver
-- Brain/sprints/SPRINT_TUTELAS_S123_BLOQUEANTE_DRIFT_REPO.md §Bloqueante 2).
-- La versión original tendría un bug latente: al primer INSERT en
-- pqrs_casos, el trigger explotaría con "column semaforo_sla does
-- not exist". Al deployar la 14 a prod (sprint separado), usar
-- esta versión de migrations/, no la de aequitas_infrastructure/.
-- La original queda como deuda a purgar cuando se deploye.
-- ═══════════════════════════════════════════════════════════════

-- 0. Tabla festivos_colombia (necesaria para calcular_fecha_vencimiento)
CREATE TABLE IF NOT EXISTS festivos_colombia (
  fecha DATE PRIMARY KEY,
  nombre VARCHAR(100) NOT NULL
);

INSERT INTO festivos_colombia (fecha, nombre) VALUES
  ('2026-01-01', 'Año Nuevo'),
  ('2026-01-12', 'Día de los Reyes Magos'),
  ('2026-03-23', 'Día de San José'),
  ('2026-03-29', 'Domingo de Ramos'),
  ('2026-03-30', 'Lunes Santo'),
  ('2026-03-31', 'Martes Santo'),
  ('2026-04-01', 'Miércoles Santo'),
  ('2026-04-02', 'Jueves Santo'),
  ('2026-04-03', 'Viernes Santo'),
  ('2026-05-01', 'Día del Trabajo'),
  ('2026-05-18', 'Día de la Ascensión'),
  ('2026-06-08', 'Corpus Christi'),
  ('2026-06-15', 'Sagrado Corazón'),
  ('2026-06-29', 'San Pedro y San Pablo'),
  ('2026-07-20', 'Día de la Independencia'),
  ('2026-08-07', 'Batalla de Boyacá'),
  ('2026-08-17', 'La Asunción de la Virgen'),
  ('2026-10-12', 'Día de la Raza'),
  ('2026-11-02', 'Todos los Santos'),
  ('2026-11-16', 'Independencia de Cartagena'),
  ('2026-12-08', 'Día de la Inmaculada Concepción'),
  ('2026-12-25', 'Día de Navidad')
ON CONFLICT (fecha) DO NOTHING;

-- 1. Columna regimen_sla en clientes_tenant
ALTER TABLE clientes_tenant
  ADD COLUMN IF NOT EXISTS regimen_sla VARCHAR(50)
    NOT NULL DEFAULT 'GENERAL'
    CHECK (regimen_sla IN (
      'GENERAL', 'FINANCIERO', 'SALUD', 'SERVICIOS_PUBLICOS', 'TELECOMUNICACIONES'
    ));

COMMENT ON COLUMN clientes_tenant.regimen_sla IS
  'Régimen regulatorio del tenant. FINANCIERO: SFC CBJ — QUEJA/RECLAMO = 8 días hábiles.';

-- 2. Tabla maestra de plazos por régimen y tipo de caso
CREATE TABLE IF NOT EXISTS sla_regimen_config (
  id           SERIAL PRIMARY KEY,
  regimen      VARCHAR(50) NOT NULL,
  tipo_caso    VARCHAR(50) NOT NULL,
  dias_habiles INTEGER NOT NULL,
  norma        VARCHAR(200) NOT NULL,
  descripcion  TEXT,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(regimen, tipo_caso)
);

COMMENT ON TABLE sla_regimen_config IS
  'Tabla maestra de plazos SLA por régimen sectorial y tipo de caso.';

-- 3. Plazos GENERAL (Ley 1755/2015)
INSERT INTO sla_regimen_config (regimen, tipo_caso, dias_habiles, norma, descripcion) VALUES
  ('GENERAL', 'TUTELA',       2,  'Decreto 2591/1991 Art. 16',    '48 horas hábiles'),
  ('GENERAL', 'PETICION',     15, 'Ley 1755/2015 Art. 14',        'Derecho de petición general'),
  ('GENERAL', 'QUEJA',        15, 'Ley 1755/2015 Art. 14',        'Queja general'),
  ('GENERAL', 'RECLAMO',      15, 'Ley 1755/2015 Art. 14',        'Reclamo general'),
  ('GENERAL', 'SOLICITUD',    10, 'Ley 1755/2015 Art. 14',        'Solicitud de información'),
  ('GENERAL', 'CONSULTA',     30, 'Ley 1755/2015 Art. 14',        'Consulta a autoridades'),
  ('GENERAL', 'FELICITACION', 5,  'Buena práctica administrativa', 'Felicitación'),
  ('GENERAL', 'SUGERENCIA',   15, 'Ley 1755/2015 Art. 14',        'Sugerencia')
ON CONFLICT (regimen, tipo_caso) DO NOTHING;

-- 4. Plazos FINANCIERO (SFC Circular Básica Jurídica)
INSERT INTO sla_regimen_config (regimen, tipo_caso, dias_habiles, norma, descripcion) VALUES
  ('FINANCIERO', 'TUTELA',       2,  'Decreto 2591/1991 Art. 16',           'Igual en todos los sectores'),
  ('FINANCIERO', 'PETICION',     15, 'Ley 1755/2015 Art. 14',               'Derecho de petición general'),
  ('FINANCIERO', 'QUEJA',        8,  'SFC Circular Básica Jurídica Cap. II', 'Régimen especial consumidor financiero'),
  ('FINANCIERO', 'RECLAMO',      8,  'SFC Circular Básica Jurídica Cap. II', 'Régimen especial consumidor financiero'),
  ('FINANCIERO', 'SOLICITUD',    10, 'Ley 1755/2015 Art. 14',               'Solicitud de información'),
  ('FINANCIERO', 'CONSULTA',     30, 'Ley 1755/2015 Art. 14',               'Consulta'),
  ('FINANCIERO', 'FELICITACION', 5,  'Buena práctica',                       'Felicitación'),
  ('FINANCIERO', 'SUGERENCIA',   15, 'Ley 1755/2015 Art. 14',               'Sugerencia')
ON CONFLICT (regimen, tipo_caso) DO NOTHING;

-- 5. Plazos SALUD (Ley 1438/2011)
INSERT INTO sla_regimen_config (regimen, tipo_caso, dias_habiles, norma, descripcion) VALUES
  ('SALUD', 'TUTELA',       2,  'Decreto 2591/1991',  'Urgencia constitucional'),
  ('SALUD', 'PETICION',     15, 'Ley 1755/2015',      'Petición general'),
  ('SALUD', 'QUEJA',        15, 'Ley 1438/2011',      'Queja en salud'),
  ('SALUD', 'RECLAMO',      15, 'Ley 1438/2011',      'Reclamo en salud'),
  ('SALUD', 'SOLICITUD',    10, 'Ley 1755/2015',      'Solicitud información'),
  ('SALUD', 'CONSULTA',     30, 'Ley 1755/2015',      'Consulta'),
  ('SALUD', 'FELICITACION', 5,  'Buena práctica',     'Felicitación'),
  ('SALUD', 'SUGERENCIA',   15, 'Ley 1755/2015',      'Sugerencia')
ON CONFLICT (regimen, tipo_caso) DO NOTHING;

-- 6. Función calcular_fecha_vencimiento (lee régimen del tenant)
CREATE OR REPLACE FUNCTION calcular_fecha_vencimiento(
  fecha_inicio TIMESTAMPTZ,
  tenant_id    UUID,
  p_tipo_caso  VARCHAR
) RETURNS TIMESTAMPTZ AS $$
DECLARE
  v_dias_habiles  INTEGER;
  v_regimen       VARCHAR(50);
  v_fecha         DATE;
  v_contador      INTEGER := 0;
BEGIN
  SELECT COALESCE(regimen_sla, 'GENERAL')
    INTO v_regimen
    FROM clientes_tenant WHERE id = tenant_id;
  IF NOT FOUND THEN v_regimen := 'GENERAL'; END IF;

  SELECT dias_habiles INTO v_dias_habiles
    FROM sla_regimen_config
   WHERE regimen = v_regimen AND tipo_caso = UPPER(p_tipo_caso);

  IF NOT FOUND THEN
    SELECT dias_habiles INTO v_dias_habiles
      FROM sla_regimen_config
     WHERE regimen = 'GENERAL' AND tipo_caso = UPPER(p_tipo_caso);
  END IF;

  IF NOT FOUND THEN v_dias_habiles := 15; END IF;

  v_fecha := fecha_inicio::DATE;
  WHILE v_contador < v_dias_habiles LOOP
    v_fecha := v_fecha + INTERVAL '1 day';
    IF EXTRACT(DOW FROM v_fecha) NOT IN (0, 6)
       AND NOT EXISTS (
         SELECT 1 FROM festivos_colombia WHERE fecha = v_fecha
       )
    THEN
      v_contador := v_contador + 1;
    END IF;
  END LOOP;

  RETURN (v_fecha + TIME '23:59:59')::TIMESTAMPTZ;
END;
$$ LANGUAGE plpgsql STABLE;

-- 7. Trigger para calcular fecha_vencimiento al INSERTar
-- DIVERGENCIA vs original: removida la asignación `NEW.semaforo_sla := 'VERDE'`
-- porque esa columna no existe en pqrs_casos (ni en prod ni en este baseline).
CREATE OR REPLACE FUNCTION fn_set_fecha_vencimiento()
RETURNS TRIGGER AS $$
BEGIN
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

DROP TRIGGER IF EXISTS tg_set_fecha_vencimiento ON pqrs_casos;
CREATE TRIGGER tg_set_fecha_vencimiento
  BEFORE INSERT ON pqrs_casos
  FOR EACH ROW EXECUTE FUNCTION fn_set_fecha_vencimiento();

-- 8. RLS en sla_regimen_config
ALTER TABLE sla_regimen_config ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sla_config_select ON sla_regimen_config;
CREATE POLICY sla_config_select ON sla_regimen_config
  FOR SELECT USING (true);
