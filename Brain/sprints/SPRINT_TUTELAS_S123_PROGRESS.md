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

## Sesión 2 — Agentes 2 + 3 (pendiente de green-light)

- [ ] Agente 2: Backend (`sla_engine.py`, `capabilities.py`, `scoring_engine` extendido, `pipeline.py`, `db_inserter.py` extendido, tests ≥80%, mypy clean)
- [ ] Agente 3: AI/Worker (`enrichers/`, `tutela_extractor.py` con Claude Sonnet, `vinculacion.py`, fixtures sintéticos con marker DT-18, integración 3 workers al pipeline, smoke E2E staging)
- [ ] Cierre Sesión 2: reporte + PAUSA

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
