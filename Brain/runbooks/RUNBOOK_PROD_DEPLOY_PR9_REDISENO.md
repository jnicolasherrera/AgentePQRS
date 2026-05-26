# RUNBOOK — Deploy PR #9 a PROD (18.228.54.9)

**Fecha planeada:** TBD (ventana operativa baja — AR madrugada o sábado AM).
**Tag fuente:** `main @ 68a23d1` (merge commit de PR #9).
**Cambios:** rediseño dashboard completo, KPIs tutelas, eficiencia por abogado, vinculación manual PQR↔Tutela, refactor shared modules.
**Tiempo estimado:** 12-18 min (backend 2 min + workers 1 min + frontend 6-8 min build + nginx restart + validación).
**Riesgo:** medio. Cambios en backend (stats consolidado, 2 endpoints nuevos, 1 modificado para hidratar pqr_origenes, fix auth RLS), 2 migraciones SQL nuevas (idempotentes), rewrite completo del dashboard, refactor de imports en 5+ componentes.

## Pre-requisitos

- [ ] PR #9 mergeada a `main` (confirmado: commit `68a23d1`).
- [ ] Acceso SSH `ubuntu@18.228.54.9` confirmado.
- [ ] Backup DB pre-deploy disponible (a S3 como SPRINT_D3).
- [ ] Ventana operativa coordinada con ARC (cliente piloto).

## Procedimiento

### 1. Backup DB

```bash
ssh ubuntu@18.228.54.9 'cd /home/ubuntu/PQRS_V2 && \
  docker exec pqrs_v2_db pg_dump -U pqrs_admin -Fc pqrs_v2 | gzip > /tmp/backup_pre_pr9_$(date +%Y%m%d_%H%M%S).dump.gz && \
  aws s3 cp /tmp/backup_pre_pr9_*.dump.gz s3://flexpqr-backups-prod/'
```

### 2. Tag de rollback

```bash
ssh ubuntu@18.228.54.9 'cd /home/ubuntu/PQRS_V2 && \
  git tag -f pre-pr9-prod-$(date +%Y%m%d_%H%M%S) HEAD && \
  echo "ROLLBACK target: $(git log -1 --format=%h)"'
```

### 3. Pull main + migraciones SQL

```bash
ssh ubuntu@18.228.54.9 'cd /home/ubuntu/PQRS_V2 && \
  # Stash cualquier drift local (ej. cert keys, docker-compose.override.yml)
  git stash push -m "prod-drift-pre-pr9" 2>&1 | tail -1 && \
  git fetch origin && git checkout main && git pull --ff-only origin main && \
  git stash pop 2>&1 | tail -1 || true && \
  git log --oneline -3'

# Aplicar 2 migraciones nuevas (idempotentes):
ssh ubuntu@18.228.54.9 'cd /home/ubuntu/PQRS_V2 && \
  for f in aequitas_infrastructure/database/15_tutelas_escaladas.sql \
           aequitas_infrastructure/database/17_borrador_feedback.sql; do
    echo "--- aplicando $f ---"; \
    cat "$f" | docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 2>&1 | tail -3; \
  done && \
  echo "=== verificación ===" && \
  docker exec pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 -tAc \
    "SELECT '\''pqr_origenes col'\'', count(*) FROM information_schema.columns WHERE table_name='\''pqrs_casos'\'' AND column_name='\''pqr_origenes'\''
     UNION ALL SELECT '\''borrador_feedback tbl'\'', count(*) FROM information_schema.tables WHERE table_name='\''borrador_feedback'\''"'
```

### 4. (Opcional) Backfill `pqr_origenes` en tutelas históricas

Detecta retroactivamente tutelas escaladas de PQR previo (match por email_origen).
Si lo aplicás, el KPI "Tutelas escaladas de PQR previo" empezará con datos
históricos en lugar de 0%.

```bash
ssh ubuntu@18.228.54.9 'cd /home/ubuntu/PQRS_V2 && \
  cat scripts/backfill_tutelas_escaladas.sql | docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 2>&1 | tail -8'
```

### 5. Rebuild backend + workers

```bash
ssh ubuntu@18.228.54.9 'cd /home/ubuntu/PQRS_V2 && \
  docker compose up -d --build backend_v2 master_worker_v2 demo_worker_v2 2>&1 | tail -6'
```

(Los 3 servicios comparten el mismo Dockerfile del `backend/`; el bake se hace
una vez. Recreate fuerza levantar nueva imagen.)

### 6. Validación backend

```bash
ssh ubuntu@18.228.54.9 'for i in 1 2 3 4 5 6 7 8 9 10; do \
  sleep 5; c=$(curl -sk -o /dev/null -w "%{http_code}" https://app.flexpqr.com/api/v2/docs); \
  echo "try $i: $c"; [ "$c" = "200" ] && break; done && \
  echo "=== logs sin errores recientes ===" && \
  docker logs pqrs_v2_backend --since 2m 2>&1 | grep -iE "error|exception|traceback" | grep -ivE "Kafka no listo" | head -5 || echo "✓ sin errores"'
```

### 7. Rebuild frontend (regla inmutable — bind-mount + `npm run build`)

```bash
ssh ubuntu@18.228.54.9 'cd /home/ubuntu/PQRS_V2 && \
  docker exec pqrs_v2_frontend npm run build 2>&1 | tail -10 && \
  docker compose restart frontend_v2 nginx_ssl 2>&1 | tail -3'
```

> **No** hacer `docker compose build frontend_v2` en prod — el patrón allá es
> `bind-mount + npm run build` en el container (a diferencia del staging local
> donde uso `--build-arg`). Verificar `docker-compose.yml` de prod para confirmar.

### 8. Validación end-to-end

```bash
ssh ubuntu@18.228.54.9 'for ep in / /login; do \
  curl -sk -o /dev/null -w "$ep: %{http_code}\n" https://app.flexpqr.com$ep; done && \
  echo "=== bundle JS apunta correctamente ===" && \
  curl -sk https://app.flexpqr.com/_next/static/chunks/*.js 2>/dev/null | grep -hoE "https?://app.flexpqr.com/api/v2" | head -1 && \
  echo "=== campos nuevos en endpoint ===" && \
  TOKEN=$(curl -sk -X POST https://app.flexpqr.com/api/v2/auth/login -H "Content-Type: application/json" -d '{"email":"<admin_prod>","password":"<pw>"}' | python3 -c "import sys,json;print(json.load(sys.stdin).get(\"access_token\",\"\"))") && \
  curl -sk -H "Authorization: Bearer $TOKEN" https://app.flexpqr.com/api/v2/stats/dashboard | python3 -c "
import sys,json; d=json.load(sys.stdin)
print(\"kpis keys:\", list(d[\"kpis\"].keys()))
print(\"ingresos_semana:\", d.get(\"ingresos_semana\"))
print(\"tutelas:\", d.get(\"tutelas\"))
"'
```

Checklist visual (en browser, con cuenta admin):
- [ ] Login OK.
- [ ] Dashboard: header "Buenas tardes/...", sidebar Liquid Glass navy + metallic.
- [ ] "Lo que entró al correo" (PQR vs Tutela) visible.
- [ ] "Pulso de Tutelas" con KPI "Escaladas de PQR previo".
- [ ] Bandeja sin pestaña "Casos" duplicada.
- [ ] Click en una TUTELA → overlay con sección "PQRs PREVIOS VINCULADOS" + buscador.
- [ ] Rendimiento: bloque "Eficiencia del equipo" con 4 KPIs.
- [ ] Console del browser sin errores rojos.

### 9. Rollback (si algo crítico falla)

```bash
ssh ubuntu@18.228.54.9 'cd /home/ubuntu/PQRS_V2 && \
  git checkout pre-pr9-prod-<TIMESTAMP> && \
  docker compose up -d --build backend_v2 master_worker_v2 demo_worker_v2 && \
  docker exec pqrs_v2_frontend npm run build && \
  docker compose restart frontend_v2 nginx_ssl'
```

Las 2 migraciones SQL nuevas son **aditivas** (solo ADD COLUMN + CREATE TABLE
+ CREATE INDEX), no destructivas → no requieren rollback de schema.

## Riesgos específicos a vigilar

1. **CORS**: el cambio `localhost:3010` agregado al CORS es solo dev y no
   afecta prod, pero verificar que `https://app.flexpqr.com` sigue en la lista.
2. **RLS login**: el fix `SET LOCAL app.is_superuser='true' + app.current_tenant_id`
   ahora setea AMBOS GUCs. Validar que el login funciona en prod (en staging falló
   inicialmente porque solo setteaba uno).
3. **Performance**: el endpoint `/rendimiento` ahora tiene 7 subqueries
   correlacionadas por abogado. Con muchos abogados (10+) puede tardar más.
   Mitigación: monitorear logs de duración primera hora.
4. **Worker tutela escalada**: el helper `detectar_pqr_origenes` se ejecuta
   en CADA tutela nueva ingestada. Es un SELECT extra (~10ms). Bajo impacto.

## POST deploy

- [ ] Mergear este runbook completado a Brain como evidencia.
- [ ] Avisar a Paola (cliente ARC) que está deployado.
- [ ] Monitorear ingesta + logs 2h después.
- [ ] Confirmar con métricas reales (no seed) que los KPIs se llenan.
