# Sesión 2026-05-27 — Sprint FF frontend (2 universos) deployado

**Estado:** ✅ Deployado a prod. PR #13 squash-mergeado, runtime estable.
**Tag prod:** `deploy-ffsprint-135133` (HEAD `60cd772`).

## Qué se llevó a prod

PR #13 "feat(flexfintech): sprint frontend 2 universos — bandeja + caso + dashboard + endpoints" — 15 archivos · +1448/-164 LOC · 6 commits squasheados.

### Backend (Fase 0)
- `GET /api/v2/auth/me` — devuelve user + tenant + `workflows_disponibles` (DISTINCT `tipo_workflow` de `config_buzones` is_active=TRUE).
- `GET /api/v2/plantillas?workflow=` — lista plantillas activas del tenant.
- `POST /api/v2/casos/{id}/aplicar-plantilla` — render placeholders + escribe `borrador_respuesta` + audit `PLANTILLA_APLICADA`.
- `GET /api/v2/casos/{id}` extendido: `tipo_workflow`, `email_respuesta_override`, `email_destinatario_efectivo`, `documento_peticionante`, `sp_archivo`, `metadata_especifica`, `destinatario_override_audit`.
- `?workflow=` agregado a: `/admin/casos`, `/casos/borrador/pendientes`, `/casos/enviados/historial`, `/stats/dashboard`, `/stats/rendimiento/tendencia`.
- `/stats/dashboard` gana `workflow_breakdown` (pqrs_count, ac_count, plantillas_top5, pct_match_exacto) cuando el tenant tiene AC.

### Frontend (Fase 1-4)
- **Tipos + lib + hooks**: `WorkflowType`, `Plantilla`, `WorkflowBreakdown`, `WORKFLOWS`, `getProblematicaMeta` (8 categorías visuales), `useTenantWorkflows` (cachea /auth/me), `usePlantillas` (cachea por workflow).
- **Bandeja**: pill `[PQRS] [Atención] [Ambos]` solo si tieneAC. Default PQRS. Modos:
  - PQRS: idéntico al actual.
  - AC: oculta Tipo/No PQRS/Vencimiento, reemplaza Tipo por Problemática (badge color).
  - Ambos: agrega columna Workflow con chip ⚖️/💬.
- **Caso detail**:
  - Editor destinatario (admin) con popover + regex + audit badge.
  - Badge SharePoint verde/ámbar (solo PQRS).
  - Tag problemática prominente (solo AC).
  - Sección plantillas collapsible agrupada por categoría → 1-click aplicar.
- **Dashboard**: sección "Atención al Cliente" al final (solo tieneAC + breakdown):
  - Donut PQRS vs AC + KPI "% match plantilla exacta".
  - Top 5 plantillas usadas (bar horizontal).

## Detalles de deploy

### Lo que NO rompió
- Migración 18 YA estaba aplicada en prod (descubierto durante Fase 0, eliminó un riesgo del plan).
- Sin cambios en `package.json` ni `requirements.txt` → reuse de ambas imágenes (frontend solo `npm run build` interno).
- `docker exec npm run build` salió OK al primer intento (lección de PR #9 aplicada: la imagen vieja tenía deps suficientes porque no agregamos nada nuevo).
- Cero downtime visible (frontend restart ~8s con `docker restart`).

### Friction encontrado y resuelto
- **Conflict de cherry-pick duplicado**: la rama `feat/flexfintech` tenía `a47e2b7` (cherry-pick del fix período) que también estaba en main como squash PR #12. GitHub no logró auto-merge. **Fix**: `git rebase origin/main` local (git detectó el duplicado, lo skipeó automáticamente) + `git push --force-with-lease` + retry squash → OK.

### Drift main vs prod (continuación)
- Prod estaba en `1d07795` (cherry-pick del fix período de la sesión anterior).
- Main avanzó con PR #11 (merged backend FF), PR #12 (fix período squash), PR #13 (sprint FF frontend squash).
- Post-deploy: prod=main=`60cd772`. Drift cerrado.

## Smoke validado
- HTTPS 200 `/login`.
- `/api/v2/auth/me` → 401 sin auth (UP).
- `/api/v2/plantillas?workflow=ATENCION_CLIENTE` → 401 sin auth (UP).
- `/api/v2/casos/{id}/aplicar-plantilla` POST → 401 sin auth (UP).
- `/api/v2/stats/dashboard?workflow=ATENCION_CLIENTE` → 401 sin auth (UP).
- 10 containers UP (backend + workers healthy + db + redis + nginx + kafka + minio + zookeeper).

## Pendientes
- [ ] Validar end-to-end con login real **FF** (admin Mica o Paula) para ver pill + sección AC + aplicar plantilla → ver borrador rellenado.
- [ ] Validar end-to-end con login Recovery/Demo para confirmar **cero cambio visible** (zero ruido).
- [ ] Si FF aún no tiene buzones con `tipo_workflow='ATENCION_CLIENTE'` configurado, marcar uno y ver que el worker dispatcher arranque a clasificar mails como AC.
- [ ] Setear `procesar_desde` cutoff en `config_buzones` de FF antes de activar workers AC nuevos (evita reprocesar histórico unread).
- [ ] Correr seeds (cuando haya tiempo):
  - `backend/scripts/seed_plantillas_flexfintech.py` — necesita Excel "Rtas+RTA DC".
  - `backend/scripts/seed_email_cedula_flexfintech.py` — 3010 pares.
- [ ] Mostrar a Paola lo nuevo (PR #11 backend + #13 frontend).

## Referencias
- PR #13: https://github.com/jnicolasherrera/AgentePQRS/pull/13
- PR #11 (backend FF previo): https://github.com/jnicolasherrera/AgentePQRS/pull/11
- [[sesion_20260527_fix_periodo_dashboard]] (la sesión justo anterior)
- [[sesion_20260526_deploy_pr9_prod]] (PR #9 rediseño, base sobre la que se construyó esto)
- [[project-agentepqrs-deploy-preflight]] (regla del package.json — confirmada útil)
