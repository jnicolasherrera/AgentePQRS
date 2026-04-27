# Runbook — CloudWatch metrics para tutelas

**Audiencia:** ops, oncall.
**Última revisión:** 2026-04-27 (Agente 6 sprint Tutelas).

Este runbook define las métricas custom y alarmas que el sprint Tutelas requiere para observabilidad. Las métricas se publican desde el backend Python al namespace `Aequitas/Tutelas` vía AWS SDK (boto3).

⚠️ **Las métricas y alarmas NO se crean automáticamente por el sprint.** Requieren configuración manual en AWS Console o IaC (terraform/CloudFormation) por Nico tras el deploy.

## Métricas custom propuestas

### `tutela_extraction_failed_rate`

Porcentaje de tutelas con `metadata_especifica.'_extraction_failed' = true` sobre el total de tutelas procesadas en una ventana de 5 minutos.

**Publicación:** worker o backend cron incrementa contador cada vez que `enrich_tutela` retorna fallback. Cada 5 min publica el ratio.

**Query SQL para validar:**
```sql
SELECT
  count(*) FILTER (WHERE (metadata_especifica->>'_extraction_failed')::boolean) AS failed,
  count(*) AS total
FROM pqrs_casos
WHERE tipo_caso = 'TUTELA'
  AND created_at > now() - interval '5 minutes';
```

**Alarma:**
- Threshold: `> 5%` durante 2 períodos consecutivos de 5 min.
- Acción: notificación SNS a oncall.
- Significado: el extractor está fallando frecuentemente. Causas comunes:
  - `ANTHROPIC_API_KEY` revocada / expirada.
  - Rate limit de Anthropic activo.
  - Oficios mal scaneados (PDF basura).

### `tutelas_vencidas_sin_responder`

Casos con `tipo_caso = 'TUTELA' AND fecha_vencimiento < now() AND enviado_at IS NULL`.

**Publicación:** cron cada 15 min hace COUNT y publica el valor absoluto.

**Query:**
```sql
SELECT count(*)
FROM pqrs_casos
WHERE tipo_caso = 'TUTELA'
  AND fecha_vencimiento < now()
  AND enviado_at IS NULL;
```

**Alarma:**
- Threshold: `>= 1` (cualquier tutela vencida es crítica).
- Acción: notificación SNS + email a representante legal del tenant.
- Severidad: crítica. Tutela vencida = riesgo de desacato.

### `tutelas_view_stale_minutes`

Minutos transcurridos desde el último `REFRESH MATERIALIZED VIEW`.

**Publicación:** la vista materializada PostgreSQL no expone su última hora de refresh por default. Habilitar:

```sql
-- Una opción: tabla auxiliar que actualiza el cron de refresh.
CREATE TABLE IF NOT EXISTS aequitas_view_refresh (
  view_name TEXT PRIMARY KEY,
  last_refresh TIMESTAMPTZ DEFAULT now()
);

-- Modificar el cron de refresh:
DO $$ BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY tutelas_view;
  INSERT INTO aequitas_view_refresh (view_name, last_refresh)
  VALUES ('tutelas_view', now())
  ON CONFLICT (view_name) DO UPDATE SET last_refresh = EXCLUDED.last_refresh;
END $$;

-- Y publicar:
SELECT EXTRACT(EPOCH FROM (now() - last_refresh)) / 60 AS stale_min
FROM aequitas_view_refresh
WHERE view_name = 'tutelas_view';
```

**Alarma:**
- Threshold: `> 30 minutos`.
- Acción: refrescar manualmente o revisar el cron.

### `vinculacion_match_rate`

Porcentaje de tutelas nuevas con `metadata_especifica.'vinculacion'.'motivo' != null` sobre total de tutelas en ventana 24h.

**Query:**
```sql
SELECT
  count(*) FILTER (WHERE metadata_especifica->'vinculacion'->>'motivo' IS NOT NULL) AS con_match,
  count(*) AS total
FROM pqrs_casos
WHERE tipo_caso = 'TUTELA'
  AND created_at > now() - interval '24 hours';
```

**Alarma:**
- Threshold: `< 10%` durante 24h.
- Acción: investigar.
- Significado: posibles causas:
  - El extractor no extrae documento (revisar `_confidence`).
  - El salt del tenant cambió (DT-30).
  - Cambió la convención del documento (ej. dejó de incluir cédulas).
  - Realmente las tutelas vienen de accionantes nuevos sin PQRS previo (caso normal en tenants nuevos).

### `claude_api_latency_p99` (opcional)

Latencia P99 de las calls a Claude Sonnet desde `enrich_tutela`.

**Publicación:** wrappear `client.messages.create` con métricas de tiempo y publicar a CloudWatch.

**Alarma:**
- Threshold: `> 30s P99` durante 10 min.
- Significado: Anthropic está degradado o nuestra red al endpoint está lenta.

## Dashboard recomendado

Panel CloudWatch con:
1. Línea: `tutela_extraction_failed_rate` últimas 24h.
2. Single value: `tutelas_vencidas_sin_responder` actual.
3. Línea: `tutelas_view_stale_minutes`.
4. Línea: `vinculacion_match_rate` últimas 24h.
5. Logs aggregator: errores `aiokafka` o `RuntimeError` en backend container.

## Implementación en código

⚠️ **No implementado en este sprint.** Requiere:

1. Wrapper `cloudwatch_metrics.py` en `backend/app/services/`.
2. Llamadas desde `tutela_extractor.py` (en cada call exitosa o fallback).
3. Cron job (diariamente o cada N min) que ejecuta las queries SQL y publica los valores.

Sprint candidato: post-tutelas housekeeping del Agente 6 / Infra.

## Mientras no estén las alarmas

Workaround manual: las queries SQL de cada métrica se pueden ejecutar ad-hoc desde tunnel SSH para verificar el estado puntual.

```bash
ssh -f -N -L 5434:localhost:5434 flexpqr-staging
psql "postgresql://pqrs_admin:pg_password@localhost:5434/pqrs_v2"
# Pegar las queries de cada sección.
```

## Referencias

- [[RUNBOOK_TUTELAS]] sección "Alertas CloudWatch".
- [[SPRINT_TUTELAS_S123]] decisiones B2/W3 que justifican estas métricas.
