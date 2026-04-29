# Sprint Fix de Fondo INC-2026-04-27 — 2026-04-29

Cierre del sprint que aborda las 4 deudas técnicas surgidas del incidente master_worker pool dead (INC-2026-04-27).

## Alcance

- **DT-32** reconnect logic asyncpg (RESUELTA).
- **DT-33** healthcheck funcional Docker (RESUELTA).
- **DT-34** alerting via email + SSM Parameter Store multi-tenant (RESUELTA, pend. verificación 7d).
- **DT-39** bridge cron `check_ingestion.sh` falsos positivos (MITIGADA + REEMPLAZADA por v2).

## Branch + PR

- Branch: `hotfix/dt-32-33-34-2026-04-28`
- PR: https://github.com/jnicolasherrera/AgentePQRS/pull/7 (mergeado a `main` 2026-04-29).
- Commit squash en `main`: `74aa53d`.
- Tags: `sprint-fix-fondo-dt32-33-34-2026-04-29`, `dia-2026-04-29`.

## Smoke staging — 2026-04-29 17:32-17:59 UTC

Stack staging recreated con `docker compose up -d --force-recreate master_worker_v2 demo_worker_v2`.

| Test | Resultado | Detalle |
|---|---|---|
| Containers recreated con healthcheck activo | ✅ | `Up 36s (healthy)` antes de start_period agotarse |
| Helper `_ensure_alive_connection` en código del container | ✅ | grep -c = 4 matches |
| `/app/healthcheck_worker.py` desplegado | ✅ | mtime fresca |
| DT-32 reconnect post `docker restart pqrs_v2_db` | ✅ | Logs: `🔄 (re)abierta` → `⚠️ DB connection lost: InterfaceError` → `🔄 (re)abierta`. Workers no marcaron unhealthy durante restart |
| DT-33 unhealthy detection vía SIGSTOP + touch -d 15min | ✅ | Marcó `(unhealthy)` a los 105s, FailingStreak=3, motivo `"UNHEALTHY: last activity 15.1min ago (max 10)"` |
| DT-33 recovery via SIGCONT | ✅ | Volvió a `(healthy)` en 10s |
| DT-34 email alerting (test prod) | ✅ | `THRESHOLD_HOURS=0` → email `[FlexPQR][ARC] WARNING ingestion delayed` recibido por Nico |

## Conflict en deploy + resolución

El pull en prod EC2 rechazó preventivamente: `docker-compose.yml` tenía drift productivo no commiteado desde abril 2026. Estrategia aplicada (Camino C — commit + merge):

1. Backup defensivo: `docker-compose.yml.backup.preMerge_20260429_192453`.
2. Branch `prod-drift-2026-04-29` con commit `2331581 ops(prod): drift productivo no-commiteado abr-2026`.
3. Pull `origin/main` en branch `main` (fast-forward limpio, drift no estaba ahí).
4. `git merge --no-ff prod-drift-2026-04-29` → conflict único en `demo_worker_v2` (env vars + healthcheck mezclados en mismas regiones).
5. Resolución: unión semántica preservando ambos lados:
   - `DEMO_RESET_MINUTES=1440` (drift, sobreescribe `=30` viejo).
   - `MINIO_ENDPOINT/ACCESS_KEY/SECRET_KEY` (drift, rescue 16-abr).
   - `ACTIVITY_FLAG=/tmp/demo_worker_last_activity` (DT-33).
   - `healthcheck:` block con test/interval/timeout/start_period/retries (DT-33).
6. Validación: `docker compose config` → YAML válido.
7. Merge commit local `e930a4f`.

Los commits `2331581` y `e930a4f` son **prod-only audit trail**, no pusheados a origin. Se cherry-pickearán al repo en sprint dedicado DT-19.

## Ver detalle del drift

`Brain/incidents/INC-2026-04-29_drift_docker_compose_prod.md`.

## Plan validación 7 días post-deploy

1. **Día 1 (2026-04-30):** revisar `/home/ubuntu/logs/check_ingestion.log` para entries WARNING/CRITICAL post-deploy. Esperado: ninguna en horario hábil.
2. **Días 2-7:** monitorear:
   - Que no aparezcan logs `connection is closed` infinitos en master_worker (señal de reconnect roto).
   - Que el flag `/tmp/master_worker_last_activity` se actualice cada ciclo del while loop.
   - Que el cron horario v2 ejecute (cat tail del log a `:00` de cada hora).
3. **Día 7 (2026-05-06):** si todo estable, eliminar v1 `/home/ubuntu/check_ingestion.sh`.

## Lecciones aprendidas

1. **Spec smoke S5 desfasado.** El spec original asumía que SIGSTOP al master_worker generaría `(unhealthy)` en 3 ciclos × 60s = 180s. Default `HC_MAX_INACTIVITY_MINUTES=10` hace que el flag tarde >10min en parecer stale al script. Para futuros tests rápidos: override `HC_MAX_INACTIVITY_MINUTES=2` con force-recreate del container ANTES del SIGSTOP, o forzar staleness manualmente con `touch -d '15 minutes ago' /tmp/master_worker_last_activity` (lo que hicimos como fix in-flight).

2. **DT-19 elevada por descubrimiento de drift crítico.** Cuatro cambios productivos legítimos del 14-16 abril 2026 estaban en filesystem prod sin commitear al repo. Si hubiéramos hecho `git stash drop` o `git checkout --` sin investigar, perdíamos hardening de seguridad de ports + funcionalidad demo. Pattern del Camino C (commit del drift en branch + merge) ahora documentado como playbook estándar para deploys con drift detectado.

3. **`docker compose restart` no aplica cambios del YAML.** Hay que usar `docker compose up -d --force-recreate <service>` para que la nueva healthcheck/env config tome efecto. El spec original decía `restart` y se tuvo que corregir in-flight.

4. **`pkill` no disponible en imagen slim del worker.** Para SIGSTOP testing, usar `docker kill --signal=STOP <container>` (al PID 1) en vez de `pkill` interno. Equivalente semántico, comando estándar.

## Issue separado detectado durante deploy

Master_worker logueando `WARNING:app.services.ai_engine:Claude API falló: ... You have reached your specified API usage limits. You will regain access on 2026-05-01 at 00:00 UTC` y usando fallback a keywords. **No es regresión del sprint** — es rate-limit Anthropic API hasta 1-mayo. Action: revisar facturación / quota Anthropic en próximos días.

## Tiempo total

Sprint planificado para 7 días, ejecutado en una sesión de ~5h+ (incluye smoke staging de 25 min, descubrimiento + resolución del drift de 30 min, deploy prod + verificación de 15 min).
