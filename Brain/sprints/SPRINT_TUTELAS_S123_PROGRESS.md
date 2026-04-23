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
- [ ] Ejecutar queries read-only contra staging (festivos_colombia, sla_regimen_config, regimen_sla, ARC)
- [ ] Clasificar escenario: **A** (aplicada) | **B** (no aplicada) | **C** (parcial — STOP)
- [ ] Documentar resultado en esta sección

**Resultado:** _pendiente_

### Gate 0.5 Sub-B: `migrations/` + `scripts/migrate.sh` + bootstrap
- [ ] Crear directorio `migrations/`
- [ ] `git mv` de 01, 02, 03, 04, 05, 08 de raíz + 14 de `aequitas_infrastructure/database/`
- [ ] Commit `chore(migrations): consolidar SQLs historicos en directorio migrations`
- [ ] Escribir `scripts/migrate.sh` con advisory lock + tabla `aequitas_migrations` + flags
- [ ] Commit `feat(scripts): migrate.sh runner idempotente con advisory lock`
- [ ] Dry-run staging verificado
- [ ] Bootstrap según escenario D3
- [ ] Commit `chore(db): bootstrap registro aequitas_migrations en staging`
- [ ] Verificación final (dry-run muestra todas aplicadas)

### Agente 1 — DB migraciones 18–21
- [ ] Diagnóstico obligatorio (columnas, policies, trigger def, doc_hash, config_hash_salt existencia)
- [ ] Migración 18: CHECK semáforo extendido (NARANJA, NEGRO)
- [ ] Migración 19: metadata_especifica + columnas tutela + trigger respeta fecha_vencimiento
- [ ] Migración 20: user_capabilities + RLS + grants default ARC
- [ ] Migración 21: tutelas_view materializada
- [ ] Aplicar vía `migrate.sh` (dry-run + real + idempotencia)
- [ ] Validación post-ejecución (constraint, policies, ARC intacto, grants)
- [ ] Test crítico del trigger en BEGIN/ROLLBACK
- [ ] Verificar que ARC sigue operando (count casos, smoke SSE/curl)
- [ ] Commits atómicos por migración
- [ ] Push a origin/develop

### Cierre Sesión 1
- [ ] PROGRESS.md actualizado con timestamps
- [ ] Reporte checkpoint a Nico (escenario D3, migraciones, tests trigger, anomalías)
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

_Ninguno registrado._

---

## Timestamps

- Inicio Sesión 1: _pendiente_
- Cierre Sesión 1: _pendiente_
