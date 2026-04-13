# Brain Changelog

## 2026-04-13 (deploy nocturno — hotfix aislado)
- hotfix(round-robin): incluir rol `'abogado'` en asignación automática Recovery (`master_worker_outlook.py` +1/−1)
- Branch: `hotfix/round-robin-abogado`, basado en `97f239e` (runtime actual de containers prod)
- Cherry-pick de `453e5ae` para evitar arrastrar el motor SLA sectorial dormido en main
- Merge PR #4 → commit `1106f45` en main. Semánticamente inerte en disco (el fix ya estaba en `c0dab9d` desde el pull del demo_worker previo), pero el hotfix dejó la historia auditablemente aislada
- Solo `master_worker_v2` rebuildeado. Backend, frontend, demo_worker, DB intactos (uptime original preservado)
- Validación previa: `zoho_engine.py` (+67/−13, refactor rate-limit aditivo) y `config.py` (JWT TTL 120→480) verificados como seguros para master_worker — APIs compatibles, sin impacto funcional
- Smoke test DB: 6 usuarios con rol `abogado` activos en Abogados Recovery, 0 con rol `analista` → el fix resuelve un problema real (casos Recovery no se asignaban automáticamente antes)
- Backup DB pre-deploy: `~/backups/backup_pre_sync_20260413_1927.dump` (11 MB)
- DEUDA REGISTRADA: motor SLA sectorial (commits `c26bcee`, `0713f74`) sigue dormido en main sin migración 14 aplicada. Ver `Brain/DEUDAS_PENDIENTES.md`

## 2026-04-13
- feat(demo): auto-envío de respuesta IA en demo_worker (exclusivo tenant demo)
- docs: documentado comportamiento exclusivo en `00_DIRECTIVAS_CLAUDE_CODE.md` y nuevo `demo_worker.md`
- bug pendiente: visualización de `borrador_respuesta` en frontend pestaña Casos (ticket aparte)
