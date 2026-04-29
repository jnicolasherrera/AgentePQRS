# INC-2026-04-29 — Drift productivo en docker-compose.yml descubierto durante deploy

## Resumen

Durante el deploy del Sprint Fix de Fondo (PR #7) en prod EC2, `git pull origin main` rechazó preventivamente porque `docker-compose.yml` en prod tenía cambios locales no commiteados que se sobrescribirían con el merge.

**Detección:** 2026-04-29 ~17:30 UTC (intento de pull post-merge del PR #7).

**Severidad de la deuda:** ALTA. Eleva DT-19 (drift detection) de Media a Alta.

**Severidad del incidente:** BAJA — el git pull rechazó automáticamente, no se perdió nada. La presencia del drift se transformó en oportunidad para commitearlo formalmente.

## Cambios drift productivos descubiertos

Los 4 cambios eran legítimos, aplicados manualmente en prod entre 14-16 abril 2026, nunca commiteados al repo:

| # | Cambio | Categoría | Origen probable |
|---|---|---|---|
| 1 | Ports binding `127.0.0.1:` (postgres 5434, redis 6381, backend 8001, frontend 3002) | Hardening seguridad | Post-CloudTrail/GuardDuty setup, evitar exposición pública |
| 2 | `DEMO_RESET_MINUTES=30 → 1440` en demo_worker | Runtime config | Cambio de demo (24h en vez de 30 min) |
| 3 | `MINIO_ENDPOINT/ACCESS_KEY/SECRET_KEY` en demo_worker | Funcional | Rescue 16-abr (commit `d660af1` necesitaba estas env vars en runtime) |
| 4 | `DEMO_GMAIL_USER/PASSWORD` en backend | Funcional | Soporte para flow de demo en backend |

Backups previos del compose en disco prod:
- `docker-compose.yml.backup.20260414_1511`
- `docker-compose.yml.backup.20260414_175705`
- `docker-compose.yml.bak.20260416_152744`
- `docker-compose.yml.backup.preMerge_20260429_192453` (creado durante este incidente)

Los 3 backups previos al de hoy confirman que Nico fue iterando sobre el compose con backups defensivos manuales — practica válida pero no se complementó con commits al repo.

## Resolución aplicada

**Camino C** (commit del drift + merge sobre HEAD main):

1. Backup defensivo: `cp docker-compose.yml docker-compose.yml.backup.preMerge_20260429_192453`.
2. `git checkout -b prod-drift-2026-04-29` (branch local prod, no pusheada).
3. `git add docker-compose.yml && git commit -m 'ops(prod): drift productivo no-commiteado abr-2026'` → commit `2331581`.
4. `git checkout main && git pull origin main` → fast-forward limpio (drift no existía en main, solo cambios DT-32/33/34 del PR #7).
5. `git merge --no-ff prod-drift-2026-04-29` → conflict único en `docker-compose.yml::demo_worker_v2` (las regiones de env vars + healthcheck pegaban en el mismo bloque YAML).
6. Resolución manual via Edit tool en local + scp al server: unión semántica preservando ambos lados (drift + DT-33 ACTIVITY_FLAG/healthcheck block).
7. Validación: `docker compose config` → YAML válido.
8. Commit del merge → `e930a4f merge(prod): integra fix de fondo DT-32/33/34 con drift productivo abr-2026`.

Estado final prod EC2 main local:
```
e930a4f merge(prod): integra fix de fondo...                ← merge resolution
2331581 ops(prod): drift productivo no-commiteado abr-2026  ← drift audit trail
74aa53d Merge pull request #7 from .../dt-32-33-34          ← origin/main HEAD
...
```

**Los commits `2331581` y `e930a4f` no se pushean a origin.** Son audit trail local en prod EC2 únicamente.

## Por qué no se commiteó el drift en su momento

Hipótesis (no verificada con Nico):

- Cambios urgentes durante incidentes (rescue 16-abr, hardening post-CloudTrail) priorizaron "aplicar a prod ya" sobre "commitear formalmente".
- Falta de checklist post-cambio que incluya commit + push al repo.
- Backups manuales del compose suplían parcialmente la pérdida de history pero perdían el contexto del *por qué* del cambio.

## Plan de cierre

1. **Sprint dedicado DT-19** (próximos 14 días):
   - Cherry-pick del commit `2331581` (drift productivo) a una rama nueva en repo (ej. `chore/prod-drift-recovery-2026-04`).
   - PR formal con explicación detallada de cada cambio (igual a lo de este doc).
   - Merge a `main` después de revisión.
   - Después del merge, en prod EC2: pull para que el HEAD remoto y local coincidan; los commits locales `2331581` y `e930a4f` quedan como ancestros del nuevo main.

2. **Hook automatizado** para evitar próximas instancias:
   - Cron diario en prod EC2 que ejecute `cd ~/PQRS_V2 && git status --porcelain` y reporte (vía DT-34 alerting) si hay archivos modificados o untracked críticos. Path mínimo: docker-compose.yml, nginx/nginx.conf, scripts/.
   - Drift detection automatizado cumple parcialmente DT-19.

3. **Playbook documentado** (este mismo archivo + sección en `Brain/00_maestro/`):
   - Patrón "git checkout -b prod-drift-YYYY-MM-DD + commit + merge" como standard para deploys con drift detectado.
   - Backup defensivo del file conflictivo antes de tocar git.
   - Validación con `docker compose config` (o equivalente) antes de commitear el merge.
   - Camino C es el camino canónico cuando hay drift legítimo. Camino A (manual edit sin git ayudando) y Camino B (stash pop) son fallback solo si el drift es trivial.

## Lo que se hizo bien

- Pull rechazó preventivamente. Git protegió el drift.
- El agente NO improvisó `git stash` ni `git checkout --` ni `git reset --hard`. Pausó, diagnosticó, y dejó decidir al humano.
- Backup defensivo antes del commit del drift.
- Validación YAML antes del commit del merge.

## Lo que mejoramos en próxima iteración

- Drift detection debería ser automatizado, no descubierto en deploy.
- Audit trail local en prod debería tener un proceso de "promote to repo" claro.
- Cuando se aplique cambio a prod manualmente, el procedimiento debería incluir paso explícito "commit + push antes de salir del SSH session".
