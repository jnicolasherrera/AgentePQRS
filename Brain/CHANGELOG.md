# Brain Changelog

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
