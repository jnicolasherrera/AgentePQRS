# Sesión 2026-06-01 — Upgrade staging full + DT-25 `/health` endpoint

## Resumen ejecutivo

Sesión doble que cerró dos cosas:

1. **DT-25 resuelta**: agregado endpoint `GET /health` al backend con `SELECT 1` (PR #18 → main, `87c7df7`).
2. **Upgrade staging al día con main**: 130 commits de drift cerrado en una sola pasada (sprint mayo completo: RAG, FlexFintech operativo, F1+F2 adjuntos, cierre-de-loop, rediseño dashboard).

Deploy a **prod queda pendiente** — sesión aparte siguiendo `project-agentepqrs-deploy-preflight`.

## Línea de tiempo

### 1. Triaje del backlog (Telegram)
Pedido inicial del usuario: "¿qué falta en AgentePQRS?". Mapeo completo del backlog (DT-1 a DT-41) entregado por DM. Decisión: arrancar por **DT-25** (chico, autocontenible, desbloquea healthchecks externos).

### 2. DT-25 implementación

**Verificación previa (regla brain-first):**
- `curl http://18.228.54.9:8001/health` → 404 (prod).
- `curl http://15.229.114.148:8001/health` → 404 (staging).
- `GET /` → 200 en ambos (legacy intacto).

**Edit aplicado en `backend/app/main.py`:**
```python
from app.core.db import init_db_pool, close_db_pool, get_raw_pool  # +get_raw_pool

@app.get("/health")
async def health_check():
    pool = get_raw_pool()
    if pool is None:
        return JSONResponse(503, {"status":"degraded","db":"uninitialized"})
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status":"ok","db":"up"}
    except Exception as e:
        return JSONResponse(503, {"status":"degraded","db":"down","error":str(e)})
```

**Decisiones de diseño:**
- Solo chequea DB (`SELECT 1`). Kafka/Redis/MinIO no — el backend arranca degradado sin ellos.
- 503 si DB no disponible (convención uptime probes / K8s readiness).
- Sin auth (endpoint público de monitoring).
- `GET /` intacto para compat con smoke tests existentes.

**Smoke quirúrgico en staging (pre-merge):**

Detectado drift severo de staging (commit `376a0b6`, sin `plantillas.py` que el código local ya importaba). Aplicado patch quirúrgico vía `scp` directo + edit in-place — solo `/health` + import `get_raw_pool`, sin tocar el resto. Rebuild + restart backend_v2. Smoke PASS.

**Flujo git canónico:**
- Branch `feat/dt25-health-endpoint`.
- Commit `9f372f4` (local), squash a `87c7df7` en merge.
- PR #18 → squash merge a main, branch borrada.

### 3. Upgrade staging — descubrimiento del scope real

Cuando Nico pidió "completá los 8 commits" (asumiendo el drift de staging vs main), el chequeo real mostró que NO eran 8 sino **30+ commits + 53 archivos + 8999 LOC nuevas**.

**Inventario del drift cerrado:**
- 4 migraciones DB (`16_kb_rag_pgvector`, `17_ab_test_borradores`, `17_borrador_feedback`, `18_flexfintech_operativo`, `19_historico_email_cedula_unique_lower`).
- 4 deps backend nuevas (`voyageai`, `pdfplumber`, `python-docx`, `openpyxl`).
- Imagen DB: `postgres:15-alpine` → `pgvector/pgvector:pg15` (drop-in compat con data).
- Env var `VOYAGE_API_KEY` agregada a backend + workers.
- Frontend: rediseño dashboard + tutelas + FlexFintech UI (sin cambios `package.json`).
- Master worker: +304 LOC (dispatcher AC, F1+F2 adjuntos, cierre-de-loop).

### 4. Plan de upgrade ejecutado

**Preparación (todo reversible):**
1. `git push` branch + `gh pr create` (PR #18).
2. `gh pr merge --squash --delete-branch` (Opción A elegida por Nico).
3. Backup DB staging (`pg_dump -F c`, 146 KB → `/home/ubuntu/backups/pqrs_v2_pre_upgrade_20260601.dump`).
4. Backup `docker-compose.yml` + `.env` (mismo dir).

**Deploy:**
5. `git stash` todo el drift staging (incluyendo `docker-compose.yml`, `frontend/Dockerfile`, certs).
6. `git checkout main && git pull origin main` → fast-forward 130 commits.
7. Restaurar drift staging:
   - `cp /home/ubuntu/backups/docker-compose.yml.bak-upgrade-20260601 docker-compose.yml`
   - `git checkout stash@{0} -- frontend/Dockerfile nginx/certs/`
8. Aplicar 5 migraciones en orden idempotente (todas con `IF NOT EXISTS`). Solo `17_ab_test_borradores` faltaba realmente.
9. `docker compose build` (4 imágenes en paralelo, ~52s).
10. `docker compose up -d --no-deps backend_v2 frontend_v2 master_worker_v2 demo_worker_v2`.

**Smoke + hotfix:**
- Backend `/health` 200 OK + `db:up` ✅
- Frontend 200 ✅
- ❌ **master_worker + demo_worker**: `permission denied for table clientes_tenant` (master) y `pqrs_casos` (demo).
- Root cause: el sprint FF cambió el worker a usar `WORKER_DB_URL=aequitas_worker`. Prod tenía grants completos por histórico; staging no.
- Fix: `GRANT ALL PRIVILEGES ON ALL TABLES/SEQUENCES IN SCHEMA public TO aequitas_worker;`
- Restart workers → ambos healthy.

## Drift staging preservado (no se pisa con main)

| Archivo | Hardening staging |
|---|---|
| `docker-compose.yml` línea 84 | `DATABASE_URL=postgresql://pqrs_backend:KOuxPrWMdz1Azc3Yp1brmqGTOZum94lF@...` (RLS no-bypass para backend) |
| `docker-compose.yml` línea 167 | `NEXT_PUBLIC_API_URL=https://15.229.114.148` (IP staging) |
| `frontend/Dockerfile` línea 10 | `ARG NEXT_PUBLIC_API_URL=https://15.229.114.148` |
| `nginx/certs/*.crt` | Certs reales staging (no placeholders) |

## Deudas nuevas registradas

- **DT-42**: `demo_worker` apunta a hostname `miniov2` en lugar de `minio`. DNS falla → demo_worker arranca sin storage. Pre-existente, no del upgrade.
- **DT-43**: hot-fix `GRANT ALL` para `aequitas_worker` en staging quedó como lazy. Idealmente migrar a grants granulares por tabla.

## Deuda obsoletada

- **Seed plantillas Recovery**: prod ya tenía 8 plantillas desde marzo (87 días, onboarding). El script local en `backend/scripts/seed_plantillas_recovery.py` tenía 5 plantillas con cuerpos más cortos. Correrlo hubiera sido destructivo. Detalle en `DEUDAS_PENDIENTES.md` sección "Seed plantillas Recovery en prod".

## Aviso entregado

Paola Lombana notificada por Nico de:
1. D3 housekeeping + RLS defensa profundidad en prod (sprint mayo).
2. Pregunta abierta sobre las 8 plantillas Recovery actuales — esperando confirmación.

## Pendientes derivados

1. **Deploy DT-25 a prod** (`18.228.54.9`). Sesión aparte siguiendo preflight.
2. **DT-42**: fix hostname `miniov2`.
3. **DT-43**: granular grants para `aequitas_worker`.
4. **Confirmación Paola**: respuesta sobre las 8 plantillas Recovery (incluyendo duplicado `ELIMINACION_CENTRALES_PAZ_SALVO`).
5. **Upgrade prod** al mismo nivel que staging — sesión dedicada con preflight completo + ventana mantenimiento.

## Referencias

- PR #18: https://github.com/jnicolasherrera/AgentePQRS/pull/18
- Commit DT-25 squash: `87c7df7`
- Backup DB staging: `/home/ubuntu/backups/pqrs_v2_pre_upgrade_20260601.dump` (146 KB)
- Brain/DEUDAS_PENDIENTES.md DT-25 (resuelta), DT-42, DT-43
- Brain/CHANGELOG.md entrada 2026-06-01
