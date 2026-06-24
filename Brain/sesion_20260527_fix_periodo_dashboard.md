# Sesión 2026-05-27 — Fix selector de período del dashboard

**Estado:** ✅ Deployado y validado.
**PR:** #12 (squash a main, commit `4620500`).
**Tag prod:** `deploy-periodo-fix-110943` (HEAD prod `1d07795`).

## Bug original
El selector Hoy/7d/30d del Dashboard **solo afectaba el gráfico de tendencia**.
Todo el resto (Activos, Vencidos, Total, Ingresos del correo, Distribución
por tipo, Últimos casos) era hardcoded a 7 días o all-time → user percibía
que el filtro "no hacía nada".

## Causa raíz
`backend/app/api/routes/stats.py:60-63` tenía:
```sql
COUNT(*) FILTER (... AND fecha_recibido >= CURRENT_DATE - INTERVAL '7 days')
```
hardcoded en `ingresos_pqr_semana` y `ingresos_tutela_semana`. El resto eran
counts all-time.

## Fix (4 archivos, ~64 LOC)
- **Backend** `/stats/dashboard`: acepta `?periodo=dia|semana|mes` (mismo
  contrato que `/rendimiento/tendencia`). Inyecta
  `fecha_recibido >= CURRENT_DATE - INTERVAL '{dias} days'` al `WHERE` base
  → TODOS los counts quedan scopeados al período.
- Response gana campos `periodo` y `dias`. `ingresos_semana` queda como
  alias deprecado de `ingresos_periodo` para retrocompat.
- `por_vencer` sigue prospectivo (≤48h) pero solo cuenta casos del período.
- **Frontend** `useDashboardStats(selectedClienteId, periodo)` refetcha al
  cambiar período. Título "Lo que entró al correo · últimos 7 días" pasa a
  dinámico según período seleccionado.

## Decisión de UX (importante)
El user eligió **opción 2**: el período aplica a TODO (no solo "lo que entró
al correo"). Esto cambia semántica:
- "Activos" antes = activos all-time. Ahora = creados en período Y activos.
- "Vencidos" antes = vencidos all-time. Ahora = creados en período Y vencidos.
- "% Resueltos" antes = cerrados/total all-time. Ahora = del período.

Es lo que el user pidió explícitamente. Si en algún momento queremos volver
a separar "snapshot ahora" vs "del período", habría que partir el `WHERE` y
hacer counts duales.

## Drift descubierto (importante)
Al deployar, el server NO estaba en `68a23d1` (PR #9) como creímos: estaba
en `189fdb1` que incluye **PR #10 RAG Fase 1** mergeado. Alguien hizo un
pull/reset entre el deploy de PR #9 y este sin documentar.

**Verificación post-deploy:** PR #10 NO rompió nada porque:
- Solo agrega services internos (`rag_engine`, `embedding_engine`, `ab_test_engine`).
- Scripts (`kb_backfill`, `ab_test_evaluate`) + tests.
- **NO toca `routes/`** → cero endpoints nuevos expuestos.
- pgvector 0.8.2 ya instalado + tabla `respuestas_kb` con embedding ya existía.
- Backend arrancó OK, solo Kafka boot retries normales.

→ PR #10 ya está silente en runtime de prod desde el cherry-pick (el
backend rebuild también trajo su código). No hay endpoints user-facing
todavía; lo que active RAG será un cambio futuro (probablemente desde el
worker).

## Cherry-pick a prod
- Aplicamos regla nueva: `git diff package.json` vacío → sin rebuild full
  de imagen. Usamos `docker exec npm run build` + restart frontend.
- Backend rebuild + restart (`docker compose up -d --build backend_v2`).
- Tiempo total: ~2 min, sin 502.

## Estado post
- **HEAD main**: `4620500` (squash merge PR #12)
- **HEAD prod**: `1d07795` (cherry-pick directo, mismo contenido que `4620500`)
- **Tag pre**: `pre-periodo-fix-110943`
- **Tag post**: `deploy-periodo-fix-110943`
- **Tu rama FF intacta**: `feat/flexfintech-operativo-2026-05-27` (6 commits,
  ~2900 LOC, bloques 3–6 del FF 2 universos listos para próxima épica).

## Próximos pendientes
- [ ] Avisar a Paola que el filtro Hoy/7d/30d ahora afecta TODO.
- [ ] Validar duración del endpoint `/stats/dashboard` con `?periodo=mes` y
  datos reales (debería seguir siendo 1 RTT, igual de barato).
- [ ] Planificar deploy FF 2 universos (épica grande con frontend nuevo de
  dos vistas, no es trivial).

## Referencias
- [[sesion_20260526_deploy_pr9_prod]]
- [[RUNBOOK_PROD_DEPLOY_PR9_REDISENO]]
- PR #12: https://github.com/jnicolasherrera/AgentePQRS/pull/12
