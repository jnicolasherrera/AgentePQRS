# Progress — Sprint Tutelas S1+S2+S3

**Versión prompt canónica:** `Brain/sprints/SPRINT_TUTELAS_PIPELINE_PROMPT.md` (v3).
**Archivo v2 archivado:** `Brain/sprints/archive/SPRINT_TUTELAS_PIPELINE_PROMPT_v2.md`.
**Branch:** `develop`.
**Responsable humano:** Nico (jnicolasherrera).

---

## Sesión 1 — Gate 0.5 + Agente 1

### Setup
- [x] Archivar v2 → `Brain/sprints/archive/SPRINT_TUTELAS_PIPELINE_PROMPT_v2.md`
- [x] Escribir v3 canónico → `Brain/sprints/SPRINT_TUTELAS_PIPELINE_PROMPT.md`
- [x] Crear PROGRESS.md (este archivo)
- [ ] Commit setup + push

### Gate 0.5 Sub-A: Diagnóstico D3
- [x] Ejecutar queries read-only contra staging
- [x] Clasificar escenario
- [x] Documentar resultado

**Resultado:** 🚨 **ANOMALÍA BLOQUEANTE — pausa escalada a Nico.**

**14 sectorial en staging:** aplicada (escenario A nominal).
- `festivos_colombia`: existe, 22 filas ✓
- `sla_regimen_config`: existe, 24 filas ✓
- `clientes_tenant.regimen_sla`: existe, default `'GENERAL'`, NOT NULL ✓
- SP `calcular_fecha_vencimiento(timestamptz, uuid, varchar)`: existe ✓

**Pero staging NO refleja producción:**
- Solo 5 tablas en total: `clientes_tenant`, `festivos_colombia`, `pqrs_casos`, `sla_regimen_config`, `usuarios`.
- `pqrs_casos` es esqueleto mínimo: SIN `tipo_caso`, `fecha_vencimiento`, `fecha_creacion`, `semaforo_sla`, `numero_radicado`, `fecha_respuesta`.
- Trigger `tg_set_fecha_vencimiento` apunta a función que referencia columnas inexistentes (estaría roto en INSERT real).
- 1 solo tenant: "Organizacion Default V2" (`a1b2c3d4-...`). **NO existe ARC** (`effca814-...`).
- 1 solo usuario, rol `admin`. **0 abogados, 0 analistas**.
- Tabla `pqrs_casos` con 0 filas (no pude contar por error; tabla inexistente con esa columna).

**Implicación:** el sprint tal como está diseñado (v3) asume que staging es clon de prod. NO lo es. Todas las migraciones 18-21 fallarían porque agregan columnas sobre una tabla sin las columnas base que esperan. Los grants default de migración 20 matchearían 0 filas. Los tests del trigger apuntan a un UUID inexistente.

**Decisión pendiente de Nico:** ruta de reconciliación staging vs prod antes de continuar.

### Gate 0.5 Sub-B: `migrations/` + `scripts/migrate.sh` + bootstrap — RE-ALCANZADO CON RUTA 1b (pg_dump schema-only)
- [x] Crear directorio `migrations/` + `migrations/baseline/`
- [x] Baseline `migrations/baseline/prod_schema_20260423_1600.sql` (pg_dump schema-only autorizado)
- [x] `migrations/00_baseline_schema.sql` limpiado (subsume legacy 01-05, 08; ver DT-27 para mover legacy)
- [x] `migrations/14_regimen_sectorial.sql` versión corregida (sin `semaforo_sla` en trigger)
- [x] `migrations/99_seed_staging.sql` con fixture sintético (2 tenants fake, 8 usuarios, 25 casos)
- [x] `scripts/migrate.sh` runner idempotente con advisory-lock-por-tabla + guard `99_seed_*` abortando si env≠staging
- [x] Staging reseteado (`DROP SCHEMA public CASCADE`) + migraciones 00/14/99 aplicadas (id 1-3 en `aequitas_migrations`)
- [x] Verificación idempotencia — re-run skippea todas

> La "ruta SQLs 01-05+08" original de Sub-B fue reemplazada por baseline pg_dump tras detectarse drift repo↔prod (ver `SPRINT_TUTELAS_S123_BLOQUEANTE_DRIFT_REPO.md`). Las SQLs legacy quedan intactas en raíz; mover a `migrations/legacy/` es DT-27 (housekeeping no bloqueante).

### Agente 1 — DB migraciones 18–21 — ✅ COMPLETADO 2026-04-23
- [x] Diagnóstico obligatorio: `SPRINT_TUTELAS_S123_AG1_DIAGNOSTICO.md`. Gaps detectados (semaforo_sla ausente, fecha_creacion inexistente) y resueltos con Nico.
- [x] Migración 18: CHECK semáforo extendido + ADD COLUMN semaforo_sla DEFAULT 'VERDE' (commit `4b142c1`).
- [x] Migración 19: metadata_especifica JSONB + columnas tutela + doc_hash + config_hash_salt + índices GIN + trigger híbrido respetando `fecha_vencimiento` entrante, con capa CALENDARIO y fallback SP usando `NEW.fecha_recibido` (commit `de30d0d`).
- [x] Migración 20: `user_capabilities` con RLS + grants default ARC (`CAN_SIGN_DOCUMENT` y `CAN_APPROVE_RESPONSE` scope TUTELA). 8 grants aplicados en staging (commit `47f5684`).
- [x] Migración 21: MATERIALIZED VIEW `tutelas_view` polimórfica + 3 índices + COMMENT de advertencia RLS (commit `9f2a73e`).
- [x] Aplicación vía `migrate.sh`: dry-run → real → idempotencia (re-run 0 aplicadas/7 skipped).
- [x] Validación estructural P7: 6 columnas nuevas, CHECK 5 valores, salt 64 hex en 2 tenants, 10 índices, RLS activo user_capabilities, grants 8, ARC 25 casos, tutelas_view 5 filas, trigger usando `fecha_recibido`.
- [x] Test crítico del trigger P8 con 4 tests A/B/C/D en BEGIN/ROLLBACK, todos ✓ (matriz en `SPRINT_TUTELAS_S123_AG1_APLICACION.md`).
- [x] Verificar ARC operando P9 (25 casos intactos, capabilities 4/4, vista 5, HTTP 200 en `/`).
- [x] Commits atómicos: 4b142c1, de30d0d, 47f5684, 9f2a73e.
- [x] Push a origin/develop confirmado.

### Cierre Sesión 1
- [x] PROGRESS.md actualizado con timestamps
- [ ] Reporte checkpoint a Nico
- [ ] PAUSA — esperar green-light Sesión 2

---

## Sesión 2 — Agentes 2 + 3

### Agente 2 — Backend — ✅ COMPLETADO 2026-04-24
- [x] Diagnóstico paso 1: `Brain/sprints/SPRINT_TUTELAS_S123_AG2_DIAGNOSTICO.md`.
- [x] `sla_engine.py` con `sumar_horas_habiles` (8h/día hábil, salta almuerzo, fds, festivos), `calcular_vencimiento_tutela`, `calcular_vencimiento_medida_provisional` — commit `2105773`.
- [x] `capabilities.py` con `user_has_capability` (scope NULL cubre), `grant_capability` idempotente, `list_user_capabilities` NULLS FIRST — commit `57530fa`.
- [x] `scoring_engine.py` extendido con `SEMAFORO_CONFIG` (TypedDict) + `calcular_semaforo` polimórfico — commits `443f915` + fix mypy `2244221`.
- [x] `pipeline.py` unificador `process_classified_event` con imports diferidos de enrichers/vinculacion — commit `6b3bf9f`.
- [x] `db_inserter.py` extendido con kwargs `metadata_especifica`/`fecha_vencimiento` + fix `_parse_fecha` (fromisoformat first) — commit `f6a9ca8`.
- [x] 42 tests pasan (`python3 -m pytest backend/tests/services/`). Commit `9970a26`.
- [x] mypy clean en los 3 módulos nuevos (`sla_engine`, `capabilities`, `pipeline`); 3 errores preexistentes en `ai_engine.py` documentados.
- [x] Cobertura: estimada ≥80% por módulo a partir de los casos testeados. Medición formal con `coverage.py` bloqueada localmente por performance; deferida a Agente 4 QA (Sesión 3).
- [x] Brain doc de aplicación: `SPRINT_TUTELAS_S123_AG2_APLICACION.md` — commit `3a9e564`.
- [x] Bug encontrado y arreglado durante tests: `sumar_horas_habiles` no respetaba el almuerzo (fixed antes del commit). Bug encontrado en `_parse_fecha` (dependencia dura de pandas, fixed).
- [x] DT-28 registrado: staging al 100% de disco (bloquea `docker exec` nuevos, no runtime).

### Agente 3 — AI/Worker — ✅ COMPLETADO 2026-04-24
- [x] Diagnóstico de workers + `insert_pqrs_caso` actual (`SPRINT_TUTELAS_S123_AG3_DIAGNOSTICO.md`).
- [x] `enrichers/__init__.py` dispatcher polimórfico + auto-registro — commit `0a6f59c`.
- [x] `enrichers/tutela_extractor.py` con Claude Sonnet + tool_use + TUTELA_SCHEMA + hash documento + fallback — commit `be47e66`.
- [x] 3 fixtures sintéticos `SYNTHETIC_FIXTURE_V1` (HABILES estándar, ambiguo+medida provisional, FALLO_PRIMERA) — commit `557e6a7`.
- [x] `vinculacion.py` best-effort con 4 motivos y query cross-tenant-safe — commit `f866dd1`.
- [x] 3 workers al pipeline (worker_ai_consumer, master_worker_outlook con pool+adapter, demo_worker con pool+adapter) — commit `bba7f67`.
- [x] Tests unitarios extractor (10) + vinculacion (6) con mocks 100% — commit `dcedec2`.
- [x] Smoke E2E staging escrito (`test_tutela_pipeline_staging.py`, opt-in RUN_STAGING_SMOKE=1) — mismo commit.
- [x] Brain: AG3_DIAGNOSTICO + AG3_APLICACION.
- [x] DT-29 propuesto: refactor `storage_engine` para import lazy (conftest global cuelga en env local sin MinIO).

### Cierre Sesión 2
- [x] Agente 2 ✅ (9 commits) + Agente 3 ✅ (7 commits) pusheados a origin/develop.
- [ ] Reporte checkpoint a Nico (smoke real de staging queda opt-in; 42+16 tests verdes en env local con `--noconftest`).
- [ ] PAUSA — esperar green-light Sesión 3.

## Sesión 3 — Agentes 4 + 5 + 6 (pendiente de green-light)

- [ ] Agente 4: QA (tests E2E, multi-tenant, carga, regression ARC)
- [ ] Agente 5: Docs (Brain sprint, runbooks, DEUDAS, arquitectura, CHANGELOG)
- [ ] Agente 6: Infra (bind mounts staging, deploy, healthcheck, CloudWatch, rollback doc)
- [ ] Cierre final: reporte + PAUSA

---

## Anomalías / hallazgos no previstos

### A1 — Staging no es clon de producción (BLOQUEANTE)
**Fecha detección:** 2026-04-23
**Dónde:** `15.229.114.148` (staging oficial según SSH config y Brain).
**Evidencia:**
- Solo 5 tablas.
- `pqrs_casos` sin columnas centrales del sistema.
- 1 tenant dummy, 1 usuario admin.
**Impacto:** bloquea Sub-B y Agente 1. El sprint v3 asume staging con schema prod.
**Opciones a validar con Nico:** (1) seguir en staging mínimo con fixture sintético al inicio del sprint; (2) clonar prod→staging con `pg_dump`; (3) recrear staging desde cero aplicando 01-14 canonical + seed mínimo; (4) cambiar "staging" a otra instancia si existiera.

---

## Timestamps

- Inicio Sesión 1: 2026-04-23 (diagnóstico D3 + reconstrucción staging + Agente 1)
- Cierre Sesión 1: 2026-04-23 19:07 UTC (tras aplicar 18-21 y validar los 4 tests trigger)

## Anomalías / hallazgos de Sesión 1 (resumen)

| Código | Descripción | Resolución |
|---|---|---|
| A1 | Staging esqueleto no reflejaba prod | Reconstruido con baseline pg_dump schema-only (Opción 1b, ruta Y) |
| Drift repo↔prod | 14 cols de pqrs_casos no venían de SQLs del repo | Baseline 00_baseline_schema.sql subsume las legacy |
| 14 con `semaforo_sla` fantasma | Trigger referenciaba columna ausente | Fix en `migrations/14_regimen_sectorial.sql` (removida la asignación) + columna creada por la 18 |
| Trigger con `fecha_creacion` | Columna inexistente | Reemplazado por `fecha_recibido` (consistente con trigger vigente) |
| UUIDs productivos en 04/05 legacy | Credenciales Zoho en git | DT-20 (rotación, deadline 2026-04-30) + DT-21 (purga git history) |
| `/health` ausente | Backend expone `/`, no `/health` | DT-25 (agregar endpoint formal) |
| Kafka sin container en staging | Backend arranca sin producer | DT-26 (decidir mock vs contenedor) |
| SQLs legacy en raíz | Confusión con baseline | DT-27 (mover a `migrations/legacy/`) |
