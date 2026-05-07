# Runbook — Operación de tutelas

**Audiencia:** ops, abogados ARC, Nico.
**Última revisión:** 2026-04-27 (post sprint Tutelas S1+S2+S3).

Documento operativo. Cómo consultar, debuggear, refrescar y reparar tutelas en runtime.

Para arquitectura del pipeline, ver [[SPRINT_TUTELAS_S123]].

## 1. Consultar estado de una tutela específica

### Por UUID

```bash
ssh -f -N -L 5434:localhost:5434 flexpqr-staging   # o flexpqr-prod (read-only)
```

```sql
SELECT id, asunto, tipo_caso, estado,
       fecha_recibido, fecha_vencimiento, semaforo_sla,
       asignado_a, alerta_2h_enviada,
       borrador_estado, aprobado_at, enviado_at,
       metadata_especifica
FROM pqrs_casos
WHERE id = '<uuid>';
```

### Por número de expediente judicial

```sql
SELECT id, asunto, fecha_vencimiento, semaforo_sla
FROM pqrs_casos
WHERE tipo_caso = 'TUTELA'
  AND metadata_especifica->>'numero_expediente' = '11001-3103-001-2026-00123-00';
```

### Vista materializada `tutelas_view` (campos expandidos)

```sql
SELECT id, expediente, juzgado, accionante, accionado,
       plazo_informe_horas, plazo_tipo,
       semaforo_sla, fecha_vencimiento,
       tutela_informe_rendido_at, tutela_fallo_sentido,
       tutela_riesgo_desacato
FROM tutelas_view
WHERE cliente_id = '<uuid_tenant>'
ORDER BY fecha_vencimiento ASC;
```

⚠️ **`tutelas_view` NO hereda RLS.** Filtrar por `cliente_id` siempre. Ver el `COMMENT ON MATERIALIZED VIEW tutelas_view` en [[SPRINT_TUTELAS_S123]].

## 2. Forzar re-extracción si Claude falló

Cuando un caso tiene `metadata_especifica->>'_extraction_failed' = 'true'` (Claude cayó al fallback defensivo), se puede re-procesar manualmente:

```python
# scripts ad-hoc en Python (con tunnel a staging)
import asyncio, asyncpg, json
from app.services.enrichers.tutela_extractor import enrich_tutela
from app.services.sla_engine import calcular_vencimiento_tutela

async def reextraer(caso_id: str):
    conn = await asyncpg.connect(STAGING_DB_URL)
    row = await conn.fetchrow(
        "SELECT id, cliente_id, fecha_recibido, asunto, cuerpo, email_origen "
        "FROM pqrs_casos WHERE id = $1", caso_id,
    )
    event = {
        "tenant_id": str(row["cliente_id"]),
        "subject": row["asunto"], "body": row["cuerpo"],
        "sender": row["email_origen"],
    }
    metadata = await enrich_tutela(event, clasificacion=None)
    if metadata.get("_extraction_failed"):
        print("Falló otra vez:", metadata.get("_error"))
        return
    fecha_venc = await calcular_vencimiento_tutela(
        row["fecha_recibido"], metadata, row["cliente_id"], conn,
    )
    await conn.execute(
        "UPDATE pqrs_casos SET metadata_especifica = $1::jsonb, "
        "fecha_vencimiento = $2 WHERE id = $3",
        json.dumps(metadata), fecha_venc, caso_id,
    )
    print(f"Re-extraído: plazo={metadata.get('plazo_informe_horas')}h, vence={fecha_venc}")
    await conn.close()

asyncio.run(reextraer("<uuid>"))
```

⚠️ **Costo:** 1 call real a Claude Sonnet por re-extracción. Coordinar antes de ejecutar en lote.

## 3. Refrescar `tutelas_view`

Tras INSERTs/UPDATEs masivos, la materialized view queda obsoleta. Refresh sin downtime:

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY tutelas_view;
```

`CONCURRENTLY` requiere el índice UNIQUE (`idx_tutelas_view_pk`) que la migración 21 creó. Tiempo: <1s para <10k filas.

**Cuándo refrescar:**
- Tras `UPDATE` masivo de `metadata_especifica` (re-extracción en lote).
- Tras alterar `tutela_informe_rendido_at` / `tutela_fallo_sentido` / `tutela_riesgo_desacato`.
- Programar cron cada 5 min en horas de operación si el frontend consume directo de `tutelas_view`.

## 4. Debuggear caso con `_requiere_revision_humana = true`

Casos donde Claude reportó `_confidence.plazo_informe_horas < 0.85`. La UI debería mostrarlos en un buzón dedicado.

```sql
SELECT id, asunto, fecha_recibido,
       metadata_especifica->>'plazo_informe_horas' AS plazo_h,
       metadata_especifica->>'plazo_tipo'           AS plazo_tipo,
       metadata_especifica->'_confidence'->>'plazo_informe_horas' AS confidence_plazo,
       metadata_especifica->>'_error'               AS error_extraccion
FROM pqrs_casos
WHERE tipo_caso = 'TUTELA'
  AND (metadata_especifica->>'_requiere_revision_humana')::boolean = true
ORDER BY fecha_recibido DESC;
```

Acción operativa:
1. Abogado revisa el oficio original.
2. Determina plazo correcto manualmente.
3. UPDATE `metadata_especifica` con plazo corregido + `_requiere_revision_humana=false` + actor.
4. Recalcular `fecha_vencimiento` (manual con `sla_engine` o re-extracción).
5. `REFRESH MATERIALIZED VIEW CONCURRENTLY tutelas_view`.

## 5. Marcar vinculación manual

Si la vinculación automática (`vincular_con_pqrs_previo`) no encontró match pero el abogado conoce uno:

```sql
UPDATE pqrs_casos
SET metadata_especifica = COALESCE(metadata_especifica, '{}'::jsonb)
    || jsonb_build_object(
        'vinculacion',
        jsonb_build_object(
          'motivo', 'MANUAL_OPERATOR',
          'matches_ids', jsonb_build_array('<uuid_pqrs_previo>'),
          'encontrado_at', now()::text,
          'operator_id', '<uuid_usuario>'
        )
    )
WHERE id = '<uuid_caso_tutela>';
```

## 6. Listar tutelas próximas a vencer (alertas)

```sql
SELECT id, asunto, fecha_vencimiento,
       (fecha_vencimiento - now()) AS tiempo_restante,
       semaforo_sla, asignado_a
FROM pqrs_casos
WHERE tipo_caso = 'TUTELA'
  AND estado != 'CERRADO'
  AND fecha_vencimiento BETWEEN now() AND now() + INTERVAL '6 hours'
ORDER BY fecha_vencimiento ASC;
```

## 7. Caso smoke retenido — `0f83ce56-7f9c-4209-ba3d-2a5be8ef33ae`

Caso de referencia generado por el smoke E2E del Agente 3 (sprint Tutelas). **Marker `SYNTHETIC_FIXTURE_V1` explícito en metadata.**

```
asunto              = [SMOKE_TEST_AGENTE3] Tutela sintética Agente 3 471586e1-...
tipo_caso           = TUTELA
fecha_recibido      = 2026-04-27 15:00:53+00
fecha_vencimiento   = 2026-04-29 15:01:00+00 (sla_engine: lun 15:00 + 16h hábiles)
metadata.tipo_actuacion = AUTO_ADMISORIO
metadata.plazo_informe_horas = 16, plazo_tipo = HABILES
metadata.numero_expediente = 11001-9999-888-2026-00999-00
metadata._synthetic_fixture = SYNTHETIC_FIXTURE_V1
```

⚠️ **NO ELIMINAR sin verificar que no rompe `test_arc_smoke_case_persiste`** en `backend/tests/integration/test_arc_regression.py`. Es opt-in con `RUN_STAGING_REGRESSION=1`.

## 8. Capabilities — quién firma / aprueba tutelas

```sql
SELECT u.email, u.rol,
       array_agg(uc.capability || ':' || COALESCE(uc.scope, '*')
                 ORDER BY uc.capability) AS caps
FROM usuarios u
JOIN user_capabilities uc ON uc.usuario_id = u.id AND uc.revoked_at IS NULL
WHERE u.cliente_id = '<uuid_tenant>'
GROUP BY u.email, u.rol
ORDER BY u.rol, u.email;
```

Para otorgar capability ad-hoc:

```python
from app.services.capabilities import grant_capability
await grant_capability(
    user_id=uuid.UUID("..."),
    capability="CAN_SIGN_DOCUMENT",
    tipo_caso_scope="TUTELA",
    granted_by=uuid.UUID("..."),
    conn=conn,
)
```

## 9. Alertas CloudWatch (post Agente 6)

| Alerta | Significado | Acción |
|---|---|---|
| `tutela_extraction_failed_rate > 5%` (5min) | El extractor está cayendo al fallback frecuentemente. Posibles causas: API key revocada, rate limit, oficios mal scannedos. | Revisar `_error` en metadata, validar `ANTHROPIC_API_KEY`. |
| `tutela_vencidas_sin_responder` (cada hora) | Casos con `semaforo_sla = NEGRO` sin `enviado_at`. | Escalar a representante legal ARC. |
| `tutelas_view_stale_minutes > 30` | La materialized view no se ha refrescado en 30+ min. | Manual `REFRESH MATERIALIZED VIEW CONCURRENTLY tutelas_view` o revisar cron. |
| `vinculacion_match_rate < 10%` (24h) | Demasiados casos sin doc_hash o sin PQRS previos. Síntoma posible: documento no se está extrayendo. | Validar `_confidence` del extractor. |

(Las definiciones exactas de alarmas las pone el Agente 6.)

## 10. Cuándo abrir un sprint dedicado

- **DT-30 reconciliación ORM ↔ DB.** Cualquier feature futura que use SQLAlchemy ORM va a tropezar con las 13 columnas no declaradas.
- **DT-26 Kafka en staging.** Mientras no esté, el `worker_ai_consumer` no se puede probar E2E (solo unitario con mocks).
- **DT-18 fixtures reales de Paola.** Validar precisión de Claude Sonnet en producción.
