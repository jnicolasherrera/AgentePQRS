# Brain Changelog

## 2026-07-02
- ops(prod) **DESPLEGADO**: upgrade full a `main@59e23a7` en ventana 18:00 ART — cierra "deuda de deploy #1". Entra a runtime: F1+F2 lectura de adjuntos (PRs de mayo), RAG cierre-de-loop, `/health` (DT-25), reclasificación PQRS↔AC (#19), fixes auditoría A1–A7, RBAC operador v2.
  - Migración 14 aplicada a prod (regimen_sla + festivos + sla_regimen_config) — el Motor SLA sectorial deja de estar dormido.
  - 2 incidentes en el corte, resueltos en ~15 min: grants faltantes de las tablas mig 14 para `aequitas_worker` (patrón DT-43) y `asunto varchar(500)` bloqueando el buzón ARC en loop (asunto real >500 chars) → `asunto`/`storage_path` a TEXT con recreate de `tutelas_view`. Versionado como **migración 20** (pendiente staging).
  - Validación E2E con casos REALES de ARC: adjuntos descargados para contexto del borrador + `rag_docs=3` en el primer ciclo post-deploy.
  - demo_worker: revivido al mediodía para demo en vivo (había sido apagado el 25/06 como zombie) — **se queda: se usa para demos comerciales**.
  - Rollback disponible: imágenes `:pre-upgrade-20260702`, tag git `pre-f1f2-prod-20260702`, dump 8.4 MB. Borrar tags en ~1 semana (disco 89%).
- bitácora completa: `Brain/sesion_20260702_deploy_f1f2_prod.md`

## 2026-06-24
- fix(rbac) **DESPLEGADO**: rol `abogado` (Arcas / tenant Abogados Recovery) operativo. Modelo "cada uno ve lo suyo" unificado en la Bandeja:
  - Fase 1 backend (hotfix en prod, commits `aecac2d`+`3343d93`): `/admin/casos` y `/stats/dashboard` aceptan `abogado`/`analista` forzando `asignado_a`=ellos; `/casos/enviados/historial` revertido (ven solo SUS envíos). Verificado e2e: abogado→256 casos (antes 403), admin→1590, enviados→29.
  - Fase 2a frontend (`5ea8c2b`, en main): nav de operador `[Dashboard, Bandeja, Enviados]` + Bandeja sin controles admin. **Deploy a prod PENDIENTE** (rebuild `frontend_v2`, esperando OK de los abogados sobre Fase 1).
  - Fase 2b (overlay) diferida — backend ya bloquea con 403.
- chequeos: Zoho healthy; Kafka/Zookeeper vestigiales (no regresión).
- chore(repo) `009afb5`: commiteadas bitácoras sprint mayo + updates CHANGELOG/DEUDAS; `.gitignore` ignora `graphify-out/`. Árbol limpio, a la par con origin/main.
- bitácora completa: `Brain/sesion_20260624_cierre_rbac_recovery_y_repo.md`

## 2026-06-01
- feat(backend): `/health` endpoint con `SELECT 1` (DT-25) — PR #18 (`87c7df7`) mergeado a main
- ops(staging): upgrade full del sprint mayo (130 commits, branch `cleanup/fase1-estructura-2026-05-21` → `main`)
  - 5 migraciones aplicadas idempotente (16, 17_ab_test_borradores, 17_borrador_feedback, 18, 19) — solo 17_ab_test_borradores faltaba realmente
  - 4 imágenes rebuild: backend_v2, frontend_v2, master_worker_v2, demo_worker_v2
  - Drift staging preservado: `pqrs_backend` role + IP staging en compose, certs reales
  - Hot-fix: `GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO aequitas_worker` (sprint FF cambió worker a `WORKER_DB_URL=aequitas_worker`)
  - DB dump pre-upgrade: `/home/ubuntu/backups/pqrs_v2_pre_upgrade_20260601.dump` (146 KB)
- deudas nuevas registradas: DT-42 (MinIO hostname `miniov2`), DT-43 (grants `aequitas_worker` lazy)
- deuda obsoletada: seed plantillas Recovery — prod ya tenía 8 plantillas desde marzo, script local con cuerpos más cortos quedó out-of-date
- pendiente: deploy DT-25 a prod siguiendo `project-agentepqrs-deploy-preflight`
- bitácora completa: `Brain/sesion_20260601_upgrade_staging_dt25.md`

## 2026-04-13
- feat(demo): auto-envío de respuesta IA en demo_worker (exclusivo tenant demo)
- docs: documentado comportamiento exclusivo en `00_DIRECTIVAS_CLAUDE_CODE.md` y nuevo `demo_worker.md`
- bug pendiente: visualización de `borrador_respuesta` en frontend pestaña Casos (ticket aparte)
