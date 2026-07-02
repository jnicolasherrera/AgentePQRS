-- ═══════════════════════════════════════════════════════════════
-- Migración 20: asunto/storage_path a TEXT + grants worker post-mig 14
-- Origen: deploy F1/F2 a prod 2026-07-02. Ya APLICADA A PROD a mano
-- esa noche (incidente: buzón ARC bloqueado en loop por un derecho de
-- petición con asunto >500 chars y adjunto de nombre largo).
-- Idempotente: re-ejecutable sin efecto si ya está aplicada.
-- ═══════════════════════════════════════════════════════════════

-- 1. Grants a las tablas creadas por la migración 14. El GRANT ALL
--    histórico sobre ALL TABLES es one-shot: no cubre tablas futuras.
--    Sin esto, el trigger de fecha_vencimiento (SECURITY INVOKER) revienta
--    con "permission denied" cuando el worker inserta casos. (Ver DT-43.)
GRANT SELECT ON sla_regimen_config, festivos_colombia TO aequitas_worker;

-- 2. storage_path sin límite: con F1 los adjuntos se guardan con su nombre
--    real (casos/{uuid}/{uuid}_{filename}) y hay filenames judiciales largos.
ALTER TABLE pqrs_adjuntos ALTER COLUMN storage_path TYPE TEXT;

-- 3. asunto sin límite. tutelas_view (materialized) depende de la columna:
--    hay que dropearla, alterar y recrearla idéntica (con sus 3 índices).
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'pqrs_casos' AND column_name = 'asunto'
      AND data_type = 'character varying'
  ) THEN
    EXECUTE 'DROP MATERIALIZED VIEW IF EXISTS tutelas_view';
    EXECUTE 'ALTER TABLE pqrs_casos ALTER COLUMN asunto TYPE TEXT';
    EXECUTE $v$
      CREATE MATERIALIZED VIEW tutelas_view AS
       SELECT c.id,
          c.cliente_id,
          c.numero_radicado,
          c.email_origen,
          c.asunto,
          c.estado,
          c.nivel_prioridad,
          c.fecha_recibido,
          c.fecha_vencimiento,
          c.semaforo_sla,
          c.tipo_caso,
          c.asignado_a,
          c.fecha_asignacion,
          c.alerta_2h_enviada,
          c.numero_radicado AS radicado_interno,
          (c.metadata_especifica ->> 'expediente'::text) AS expediente,
          (c.metadata_especifica ->> 'juzgado'::text) AS juzgado,
          (c.metadata_especifica ->> 'accionante'::text) AS accionante,
          (c.metadata_especifica ->> 'accionado'::text) AS accionado,
          ((c.metadata_especifica ->> 'plazo_informe_horas'::text))::integer AS plazo_informe_horas,
          (c.metadata_especifica ->> 'plazo_tipo'::text) AS plazo_tipo,
          (c.metadata_especifica ->> 'derechos_invocados'::text) AS derechos_invocados,
          c.tutela_informe_rendido_at,
          c.tutela_fallo_sentido,
          c.tutela_riesgo_desacato,
          c.documento_peticionante_hash,
          c.borrador_estado,
          c.aprobado_por,
          c.aprobado_at,
          c.enviado_at,
          c.created_at,
          c.updated_at
         FROM pqrs_casos c
        WHERE ((c.tipo_caso)::text = 'TUTELA'::text)
      WITH DATA
    $v$;
    EXECUTE 'CREATE UNIQUE INDEX idx_tutelas_view_pk ON public.tutelas_view USING btree (cliente_id, id)';
    EXECUTE 'CREATE INDEX idx_tutelas_view_expediente ON public.tutelas_view USING btree (expediente) WHERE (expediente IS NOT NULL)';
    EXECUTE 'CREATE INDEX idx_tutelas_view_semaforo ON public.tutelas_view USING btree (cliente_id, semaforo_sla)';
  END IF;
END $$;
