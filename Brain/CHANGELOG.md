# Brain Changelog

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
