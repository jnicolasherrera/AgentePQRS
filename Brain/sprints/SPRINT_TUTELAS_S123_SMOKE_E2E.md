# Smoke E2E del Sprint Tutelas — bitácora completa

**Fecha:** 2026-04-24 → 2026-04-27.
**Branch:** `develop`.
**Pre-requisito:** Agente 2 ✅ + Agente 3 ✅.
**Objetivo:** ejercitar el pipeline completo (`enrich_tutela` Claude Sonnet → `sla_engine` → `db_inserter` → `vinculacion`) contra DB real de staging, con 1 call real al API de Claude.

## Resumen

| Iteración | Resultado | Causa |
|---|---|---|
| Smoke #1 | ❌ FAIL | `column "correlation_id" does not exist` (Bug latente histórico DRIFT-B). |
| Smoke #2 | ❌ FAIL | `external_msg_id` no se propagaba al INSERT (DRIFT-D activado por integración). |
| Smoke #3 | (en ejecución / ✅ pendiente) | Espera resultado del re-test post-fix. |

## Smoke #1 — primer FAIL

### Comando

```bash
ssh -f -N -L 5434:localhost:5434 flexpqr-staging
cd backend && RUN_STAGING_SMOKE=1 \
  STAGING_DB_URL=".../localhost:5434/pqrs_v2" \
  ANTHROPIC_API_KEY="<staging .env>" \
  MINIO_ENDPOINT="127.0.0.1:1" \
  python3 -m pytest tests/test_tutela_pipeline_staging.py --noconftest -v -s
```

### Stack trace

```
asyncpg.exceptions.UndefinedColumnError:
    column "correlation_id" of relation "pqrs_casos" does not exist
```

Traza: `pipeline.py:84 → db_inserter.py:70 → conn.fetchval(...)`.

### Análisis

- `db_inserter.insert_pqrs_caso` (preexistente) incluía la columna `correlation_id`.
- `models.py:PqrsCaso` la declara, pero el ORM es "reflejo, no fuente de verdad".
- En prod la columna **no existe**: query read-only `SELECT ... WHERE table_name='pqrs_casos' AND column_name='correlation_id'` devolvió 0 rows.
- Bug latente histórico (no nuevo del sprint): hasta ahora `master_worker` y `demo_worker` hacían INSERTs manuales sin `correlation_id`, así que el bug nunca se ejercitaba. La integración del sprint puso a los 3 workers a usar `db_inserter`, activando el bug.

### Fix aplicado: migración 22

`migrations/22_add_correlation_id.sql`:

```sql
ALTER TABLE pqrs_casos
    ADD COLUMN IF NOT EXISTS correlation_id UUID NOT NULL DEFAULT gen_random_uuid();
CREATE INDEX IF NOT EXISTS idx_pqrs_correlation ON pqrs_casos(correlation_id);
```

Aplicada en staging vía `migrate.sh`. Verificada con `\d pqrs_casos` y query información_schema. Commit `2b394a4`.

## Auditoría sistemática drift ORM ↔ DB ↔ INSERT

Comparación de las 37 columnas de `pqrs_casos` en staging contra `models.py:PqrsCaso` y el INSERT de `db_inserter`. Resumen:

| Categoría | Cantidad | Notas |
|---|---|---|
| `match` | 15 | Las 3 fuentes coinciden. |
| `DRIFT-A` intencional | 9 | ORM✓ DB✓ INSERT✗. Se llenan post-INSERT por flujos específicos (`numero_radicado`, `aprobado_*`, `enviado_at`, `acuse_enviado`, `alerta_2h_enviada`, `problematica_detectada`, `plantilla_id`, `semaforo_sla` con default DB). No es bug. |
| `DRIFT-D` auto | 5 | DB✓ con DEFAULT que cubre, ORM no declara (`updated_at`, `es_pqrs`, `reply_adjunto_ids`, `edit_ratio`, `tutela_riesgo_desacato`). No es bug. |
| `DRIFT-D` post-INSERT | 3 | DB✓ ORM✗ INSERT✗, se llenan en flujos específicos (`tutela_informe_rendido_at`, `tutela_fallo_sentido`, `texto_respuesta_final`, `borrador_ia_original`). |
| `DRIFT-D` con bug | **2** | DB✓ ORM✗ INSERT✗ pero el código asume que se llenan: `external_msg_id` (dedup roto) y `documento_peticionante_hash` (vinculación rota). |
| `DRIFT-D` info | 1 | `metadata_especifica` — el INSERT lo escribe pero ORM no lo declara. |
| ORM stale CHECK | 1 | `semaforo_sla` ORM declara CHECK con 3 valores; DB tiene 5 (post mig 18). |

**Bugs identificados para fix en el sprint:**

1. `external_msg_id` no se propaga al INSERT.
2. `documento_peticionante_hash` no se llena (la vinculación tutela→PQRS-previo nunca matchearía en runtime).

**Deudas para DT-30 (post-sprint):**

- 9 columnas declaradas en DB no aparecen en `models.py:PqrsCaso`.
- 6 columnas del ORM se llenan post-INSERT por workflows específicos (no es bug, es diseño que merece documentación).
- `semaforo_sla` CHECK del ORM desactualizado.

## Smoke #2 — segundo FAIL

Tras aplicar la migración 22, el smoke avanzó pero falló con un assert distinto:

```
AssertionError: assert None == 'SMOKE_AGENTE3_882170c8-e0ba-4035-8f1e-718ab3884a1c'
tests/test_tutela_pipeline_staging.py:109
```

Causa: `db_inserter` no propagaba `event["external_msg_id"]` al INSERT. La columna existe en DB pero quedaba NULL.

### Verificación SQL del caso #2

| Campo | Valor |
|---|---|
| `id` | `b4a620bb-f352-4034-b80f-dd6f24bb4690` |
| `tipo_caso` | `TUTELA` |
| `asunto` | `[SMOKE_TEST_AGENTE3] Tutela sintética Agente 3 882170c8-...` |
| `fecha_recibido` | `2026-04-24 17:04:26+00` |
| `fecha_vencimiento` | `2026-04-28 17:00:00+00` (calculado por `sla_engine`) |
| `semaforo_sla` | `VERDE` (default mig 18) |
| `correlation_id` | `882170c8-...` (propagado del event ✓ tras mig 22) |
| `external_msg_id` | **`None` ❌** |
| `metadata_especifica.tipo_actuacion` | `REQUERIMIENTO` |
| `metadata_especifica.plazo_informe_horas` | `16` (Claude calculó "2 días hábiles × 8h") |
| `metadata_especifica.plazo_tipo` | `HABILES` |
| `metadata_especifica._confidence.plazo_informe_horas` | `0.95` |
| `metadata_especifica._synthetic_fixture` | `SYNTHETIC_FIXTURE_V1` (marker detectado) |
| `metadata_especifica.numero_expediente` | `11001-9999-888-2026-00999-00` |
| `metadata_especifica.accionante` | `{documento_hash, tipo_documento}` (raw borrado ✓) |

**Lo que funcionó:**
- Pipeline orquestó enrich → SLA → INSERT → vinculación correctamente.
- Claude Sonnet real extrajo metadata estructurado vía tool_use.
- `enrich_tutela` hasheó documento + borró raw.
- `sla_engine.calcular_vencimiento_tutela` con plazo HABILES → `sumar_horas_habiles(16h)` → desde jue 24-abr 17:04 UTC, ajustó a vie 25 08:00 → +16h hábiles = **lun 28-abr 17:00**. Match perfecto.
- `semaforo_sla='VERDE'` default de la migración 18.
- `correlation_id` propagado tras la migración 22.

**Lo que rompió:**
- `external_msg_id` quedó NULL → assert falló.
- (Bug 2 silente, no detectado por el smoke pero sí por la auditoría:) `documento_peticionante_hash` nunca se llenaba en columna física, rompiendo la query indexada de `vinculacion`.

### Fix aplicado al `db_inserter`

Commit `e28e355` (`fix(db_inserter): propagar external_msg_id y documento_peticionante_hash al INSERT`):

- `external_msg_id`: lee del event con fallback `external_msg_id → message_id → id`. Strip blanks → None.
- `documento_peticionante_hash`: extrae de `metadata_especifica["accionante"]["documento_hash"]` con guards `isinstance(accionante, dict)`. None si no existe.
- INSERT extendido a 15 parámetros ($14 = external_msg_id, $15 = documento_peticionante_hash).
- 9 tests unitarios en `test_db_inserter.py` validan la propagación con mocks (commit `97c5aa6`).
- Smoke con asserts ampliados (commit `bdb9cb3`).

## Smoke #3 — re-ejecución — ✅ PASSED

```
tests/test_tutela_pipeline_staging.py::test_smoke_pipeline_tutela_staging
[SMOKE OK] caso_id=0f83ce56-7f9c-4209-ba3d-2a5be8ef33ae
PASSED
1 passed in 30.10s
```

### Verificación SQL del caso #3

| Campo | Valor |
|---|---|
| `id` | `0f83ce56-7f9c-4209-ba3d-2a5be8ef33ae` |
| `tipo_caso` | `TUTELA` |
| `fecha_recibido` | `2026-04-27 15:00:53+00` |
| `fecha_vencimiento` | `2026-04-29 15:01:00+00` (calculado por `sla_engine`: lun 15:00 + 16h hábiles = mié 15:00) |
| `semaforo_sla` | `VERDE` ✓ |
| `correlation_id` | `471586e1-2bce-4c2f-86ca-72d75f877318` ✓ (propagado del event) |
| `external_msg_id` | `SMOKE_AGENTE3_471586e1-2bce-4c2f-86ca-72d75f877318` ✓ **(fix 1 OK)** |
| `documento_peticionante_hash` | `3c4302b3169a4247471a91afe869571bf37aad606298196bbe12eadf304fadd9` ✓ **(fix 2 OK)** |
| `metadata.tipo_actuacion` | `AUTO_ADMISORIO` |
| `metadata.plazo_informe_horas` | `16` (Claude calculó "2 días hábiles × 8h") |
| `metadata.plazo_tipo` | `HABILES` |
| `metadata._confidence.plazo_informe_horas` | `0.98` (alto, sin flag revisión humana) |
| `metadata.numero_expediente` | `11001-9999-888-2026-00999-00` |
| `metadata.accionante.documento_hash` | match exacto con la columna física ✓ |
| `metadata._synthetic_fixture` | `SYNTHETIC_FIXTURE_V1` (marker detectado) |

**Verificaciones críticas — todas ✓:**
- `correlation_id != None` (post mig 22).
- `external_msg_id != None` (post fix Bug 1).
- `documento_peticionante_hash != None` (post fix Bug 2).
- `metadata.accionante.documento_hash == columna física` ← **el sistema preserva el contrato cross-tenant: hash en metadata JSONB es el mismo que en la columna indexada**, lo que habilita `vinculacion.vincular_con_pqrs_previo` a hacer joins por `idx_casos_doc_hash`.

## DT-30 reclasificada

Ver `Brain/DEUDAS_PENDIENTES.md#DT-30`.

## Cuestiones de seguridad cruzadas

- API key de staging (`.env` server) → 401 invalid. Rotación pendiente, parte de DT-20.
- Key ad-hoc usada para smoke #2 y #3 → válida, debe revocarse según indicación de Nico tras el cierre.
