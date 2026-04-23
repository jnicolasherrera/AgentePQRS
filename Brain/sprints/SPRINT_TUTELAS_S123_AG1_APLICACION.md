# Agente 1 — Aplicación de migraciones 18-21 + validaciones + tests

**Fecha:** 2026-04-23
**Ambiente:** staging (15.229.114.148), container `pqrs_v2_db`, DB `pqrs_v2`.
**Gaps resueltos con Nico previo a escribir las migraciones:** ver `SPRINT_TUTELAS_S123_AG1_DIAGNOSTICO.md`.

## Migraciones aplicadas

Pipeline `./scripts/migrate.sh --env=staging` aplicó 4 migraciones nuevas en orden, con registro completo en `aequitas_migrations`.

| id | filename | sha256 | applied_at |
|---|---|---|---|
| 4 | `18_check_semaforo_extendido.sql` | `3ac098622f26...` | 2026-04-23 19:07:19 |
| 5 | `19_tutelas_pipeline_foundation.sql` | `cf31c9c9fbbc...` | 2026-04-23 19:07:22 |
| 6 | `20_user_capabilities.sql` | `69cc415de9bd...` | 2026-04-23 19:07:25 |
| 7 | `21_tutelas_view.sql` | `9f344e1f52f6...` | 2026-04-23 19:07:28 |

Idempotencia verificada: re-run del runner salteó las 7 (0 aplicadas, 7 skipped).

## Validaciones P7

- **pqrs_casos** ahora tiene 6 columnas nuevas (`semaforo_sla`, `metadata_especifica`, `tutela_informe_rendido_at`, `tutela_fallo_sentido`, `tutela_riesgo_desacato`, `documento_peticionante_hash`) con defaults correctos.
- **CHECK constraint** `pqrs_casos_semaforo_sla_check` presente con los 5 valores: VERDE, AMARILLO, NARANJA, ROJO, NEGRO.
- **`clientes_tenant.config_hash_salt`** presente, poblado en los 2 tenants del seed (salt de 64 hex chars cada uno).
- **10 índices nuevos** creados: `idx_casos_doc_hash`, `idx_casos_metadata_gin`, `idx_casos_tutela_vencimiento`, `idx_pqrs_tutela_alerta` (del baseline), `idx_tutelas_view_expediente`, `idx_tutelas_view_pk`, `idx_tutelas_view_semaforo`, `idx_user_caps_capability_scope`, `idx_user_caps_cliente`, `idx_user_caps_usuario`.
- **RLS en `user_capabilities`** activo (relrowsecurity=t, relforcerowsecurity=t) con policy `tenant_isolation_user_caps_policy`.
- **Grants default TUTELA aplicados:** 8 filas (`CAN_SIGN_DOCUMENT` + `CAN_APPROVE_RESPONSE` × 4 usuarios abogados/analistas del ARC Staging).
- **ARC Staging intacto:** 25 casos, misma cantidad post-migraciones.
- **tutelas_view populada:** 5 filas (los 5 casos TUTELA del seed).
- **Trigger `fn_set_fecha_vencimiento`** reescrito a versión híbrida con 3 capas y usando `NEW.fecha_recibido`.

## P8 — 4 tests BEGIN/ROLLBACK del trigger

`fecha_recibido` constante = `2026-04-23 10:00:00+00` (jueves) en los 4 tests.

### Matriz de resultados

| Test | Tenant | Tipo | Metadata | fecha_vencimiento entrante | fecha_vencimiento resultado | Expected | ✓/✗ |
|---|---|---|---|---|---|---|---|
| **A** | Demo GENERAL | QUEJA | `{}` | NULL | 2026-05-15 23:59:59+00 | 15 hábiles GENERAL saltando fest. 1-may | ✓ |
| **B** | ARC FINANCIERO | TUTELA | `{"plazo_informe_horas":48, "plazo_tipo":"HABILES"}` | NULL | 2026-04-27 23:59:59+00 | Fallback SP (2 hábiles TUTELA) | ✓ |
| **C** | ARC FINANCIERO | TUTELA | `{"plazo_informe_horas":24, "plazo_tipo":"CALENDARIO"}` | NULL | 2026-04-24 10:00:00+00 | fecha_recibido + 24h reloj | ✓ |
| **D** | ARC FINANCIERO | TUTELA | ruidosa (999h CALENDARIO) | 2026-05-01 10:00:00+00 | 2026-05-01 10:00:00+00 | Respetado literal | ✓ |

### Semántica validada

- **Capa (1) del trigger**: `fecha_vencimiento` explícita → respetada sin tocar. Comprobado por TEST D.
- **Capa (2) del trigger**: TUTELA con metadata `CALENDARIO` → calcula `fecha_recibido + N hours`. Comprobado por TEST C.
- **Capa (3) del trigger**: `HABILES` sin pipeline Python o no-TUTELA → fallback al SP sectorial. Comprobado por TEST A (PQRS QUEJA cae al SP GENERAL 15 hábiles) y TEST B (TUTELA HABILES cae al SP 2 hábiles).

ROLLBACK verificado: post-rollback `COUNT(*) FROM pqrs_casos WHERE email_origen LIKE 'test-%' = 0`.

## P9 — ARC operando

- 25 casos en ARC Staging (igual que pre-migraciones).
- Query equivalente al SSE LiveFeed devuelve los últimos 10 casos correctamente con `fecha_vencimiento` calculada (2026-04-27 para tutelas, 2026-05-06 para QUEJA/RECLAMO FINANCIERO 8 hábiles, 2026-05-15 para PETICION/SUGERENCIA 15 hábiles — todos coherentes con el régimen FINANCIERO de ARC + los festivos 2026).
- 4 abogados/analistas ARC con los 2 capabilities cada uno.
- `tutelas_view` filtra correctamente: 5 tutelas ARC, cada una con fecha_vencimiento 2026-04-27.
- Backend HTTP: `/` → 200, `/docs` → 200 (observación DT-25: `/health` sigue 404, pendiente).

## P10 — Commits atómicos (pusheados a origin/develop)

| Commit | Mensaje |
|---|---|
| `4b142c1` | feat(db): extender CHECK semaforo_sla con NARANJA y NEGRO (mig 18) |
| `de30d0d` | feat(db): fundacion pipeline tutelas + trigger hibrido fn_set_fecha_vencimiento (mig 19) |
| `47f5684` | feat(db): tabla user_capabilities con RLS y grants default ARC (mig 20) |
| `9f2a73e` | feat(db): vista materializada tutelas_view con advertencia RLS (mig 21) |
| _este doc_ | docs(brain): aplicacion migraciones 18-21 + validaciones + 4 tests trigger |

> **Nota vs prompt v3**: el prompt pedía 6 commits separando la 19 en "columnas" + "trigger". Consolidé en 1 commit por archivo físico para mantener coherencia con la atomicidad del runner (cada `.sql` aplica como transacción implícita del `psql -f`). El mensaje del commit de la 19 cubre ambos aspectos.

## Gate de salida Agente 1

| Criterio | Estado |
|---|---|
| Diagnóstico ejecutado y gaps resueltos con Nico | ✓ (`SPRINT_TUTELAS_S123_AG1_DIAGNOSTICO.md`) |
| Migraciones 18-21 escritas según specs ajustadas | ✓ |
| Aplicadas en staging vía `migrate.sh` sin errores | ✓ (`aequitas_migrations` id 4-7) |
| Idempotentes (re-run skippea todas) | ✓ |
| Validación estructural (columnas, CHECK, índices, RLS, grants) | ✓ |
| 4 tests A/B/C/D verdes en BEGIN/ROLLBACK | ✓ (matriz arriba) |
| ARC staging operando post-migraciones (25 casos intactos) | ✓ |
| Commits atómicos pusheados a origin/develop | ✓ |
| Brain doc con diagnóstico + aplicación + tests | ✓ (este doc + el de diagnóstico) |

Agente 1 cerrado. Checkpoint Sesión 1 listo para reporte a Nico.
