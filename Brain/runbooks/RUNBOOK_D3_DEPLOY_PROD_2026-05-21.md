# RUNBOOK — D3 Deploy a Producción (2026-05-21, ventana nocturna)

**Qué se deploya:** rama `cleanup/fase1-estructura-2026-05-21` (PR #8) =
sprint Tutelas (ya en filesystem, falta runtime) + C3 (fix Zoho) + RLS (SEC-2026-05-21)
+ DT-41 + Fase1/2. **Validado en staging 2026-05-21** (suite 88 verde).
**Prod:** `ubuntu@18.228.54.9`, `/home/ubuntu/PQRS_V2`. Backend/workers SIN bind-mount
(rebuild); frontend CON bind-mount (build-in-container + restart).
**Sin migraciones nuevas** (PR #8 es solo código) → rollback = solo código.

## PRE (antes de la ventana)
- [ ] Avisar a Paola Lombana (ARC): "corte breve de ingesta ~5-15 min".
- [ ] Confirmar baja actividad (noche CO).

## DEPLOY (en la ventana, supervisado)

### 1. Backup DB a S3
```bash
ssh ubuntu@18.228.54.9 'docker exec pqrs_v2_db pg_dump -U pqrs_admin pqrs_v2 \
  | gzip > /tmp/backup_pre_d3_$(date +%Y%m%d_%H%M%S).dump.gz && \
  aws s3 cp /tmp/backup_pre_d3_*.dump.gz s3://<bucket-backups>/ '
```
(usar el bucket/perfil que usó el backup del 11/5; verificar tamaño > 0)

### 2. Checkout de la rama en prod
```bash
ssh ubuntu@18.228.54.9 'cd /home/ubuntu/PQRS_V2 && \
  git fetch origin cleanup/fase1-estructura-2026-05-21 && \
  git checkout cleanup/fase1-estructura-2026-05-21 && \
  git log -1 --format="%h %s" && [ -f .env ] && echo ".env OK"'
```
Guardar el commit ANTERIOR para rollback: `release/tutelas-2026-05-07` (37ab9c0).

### 3. Rebuild backend + workers + recreate
```bash
ssh ubuntu@18.228.54.9 'cd /home/ubuntu/PQRS_V2 && \
  docker compose build backend_v2 master_worker_v2 demo_worker_v2 && \
  docker compose up -d backend_v2 master_worker_v2 demo_worker_v2'
```

### 4. Frontend (bind-mount → build-in-container, NUNCA --build)
```bash
ssh ubuntu@18.228.54.9 "docker exec pqrs_v2_frontend sh -c 'cd /app && npm run build' && \
  cd /home/ubuntu/PQRS_V2 && docker compose restart frontend_v2 nginx_ssl"
```

## VALIDACIÓN POST-DEPLOY
- [ ] `docker compose ps` → todos healthy
- [ ] Ingesta ARC sigue: `MAX(fecha_recibido)` reciente, sin errores en logs del worker
- [ ] Frontend Tutelas visible: https://18.228.54.9 (login, vista tutelas)
- [ ] **Aislamiento RLS**: usuario no-super de un tenant NO ve casos de otro (probar con un caso real de cada uno, con cuidado)
- [ ] DT-41: un caso entrante de dominio judicial no genera acuse
- [ ] Backend `/docs` responde

## ROLLBACK (si algo falla)
Sin migraciones nuevas → rollback es solo código:
```bash
ssh ubuntu@18.228.54.9 'cd /home/ubuntu/PQRS_V2 && \
  git checkout release/tutelas-2026-05-07 && \
  docker compose build backend_v2 master_worker_v2 demo_worker_v2 && \
  docker compose up -d backend_v2 master_worker_v2 demo_worker_v2 && \
  docker exec pqrs_v2_frontend sh -c "cd /app && npm run build" && \
  docker compose restart frontend_v2 nginx_ssl'
```
(La DB no se tocó; el backup de S3 es por las dudas.)

## ✅ EJECUTADO 2026-05-26 — OK

Backup: `s3://flexpqr-backups-prod/backup_pre_d3_20260526_150507.dump.gz`.
Tag: `d3-deploy-prod-2026-05-26`. PR #8 mergeado a main (`5cd8b01`).
Sin rollback necesario. Ver [[SPRINT_D3_DEPLOY_2026-05-26]].

## POST (después de validar OK)
- [ ] Mergear PR #8 a main (sincronizar la verdad).
- [ ] Avisar a Paola que quedó OK.
- [ ] Actualizar este runbook con el resultado + tag git.
