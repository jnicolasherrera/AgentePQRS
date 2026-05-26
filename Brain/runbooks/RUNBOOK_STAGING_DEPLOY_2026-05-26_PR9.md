# RUNBOOK — Deploy PR #9 a Staging (15.229.114.148)

**Fecha:** 2026-05-26
**PR:** [#9](https://github.com/jnicolasherrera/AgentePQRS/pull/9) — `cleanup/fase1-estructura-2026-05-21`
**Cambios:** rediseño Dashboard v2 + Liquid Glass + consolidación admin + stats consolidado backend.
**Objetivo:** validar end-to-end frontend nuevo + backend con KPIs nuevos (`por_vencer`, `activos`, `tutelas/día`).
**Tiempo estimado:** 8-12 min (build frontend pesado por Tailwind v4 + recharts).

## Pre-requisitos

- SSH al server staging (`ubuntu@15.229.114.148`).
- Repo clonado en el server (asumo `/home/ubuntu/PQRS_V2` por paridad con prod, verificar).
- Estado actual: `git status` limpio antes de empezar.

## Pasos

### 1. SSH al server

```bash
ssh ubuntu@15.229.114.148
cd /home/ubuntu/PQRS_V2   # ajustar si el path difiere
```

### 2. Pull del branch

```bash
git fetch origin
git checkout cleanup/fase1-estructura-2026-05-21
git pull origin cleanup/fase1-estructura-2026-05-21
git log --oneline -7
```

### 3. ⚠️ FIX — apuntar el frontend al backend_staging

`docker-compose.staging.yml` hoy bakea `NEXT_PUBLIC_API_URL=http://18.228.54.9:8002` (la IP de PROD). Para validar los KPIs nuevos del backend de staging, hay que cambiarla a la URL accesible desde el browser:

```bash
# Backup del compose por las dudas
cp docker-compose.staging.yml docker-compose.staging.yml.bak

# Reemplazo (la IP del server staging accesible desde el browser del tester)
sed -i 's|NEXT_PUBLIC_API_URL: http://18.228.54.9:8002|NEXT_PUBLIC_API_URL: http://15.229.114.148:8002|g' docker-compose.staging.yml
sed -i 's|NEXT_PUBLIC_API_URL=http://18.228.54.9:8002|NEXT_PUBLIC_API_URL=http://15.229.114.148:8002|g' docker-compose.staging.yml

# Verificar
grep -nE "NEXT_PUBLIC_API_URL" docker-compose.staging.yml
```

> Este fix es **temporal y NO se commitea** (la deuda real es reorganizar los compose, anotada en `Brain/ARQUITECTURA_DE_CAMBIOS_2026-05-21.md`).

### 4. Rebuild + recreate backend_staging + frontend_staging

```bash
docker compose -f docker-compose.staging.yml up -d --build backend_staging frontend_staging
```

(El backend es el más rápido. El frontend tarda 5-8 min por `next build` con Tailwind v4 + recharts.)

### 5. Validar contenedores y CORS

```bash
docker compose -f docker-compose.staging.yml ps backend_staging frontend_staging
# ambos deben estar Up + healthy

# Backend responde?
curl -s -o /dev/null -w "backend_staging /docs: %{http_code}\n" http://localhost:8002/docs
curl -s -X POST http://localhost:8002/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@flexpqr.local","password":"<seed_password>"}' | head -c 200

# Frontend responde?
curl -s -o /dev/null -w "frontend_staging /: %{http_code}\n" http://localhost:3003/
```

### 6. Verificar campos nuevos del backend

```bash
TOKEN=$(curl -s -X POST -H "Content-Type: application/json" \
  -d '{"email":"<admin>","password":"<pw>"}' \
  http://localhost:8002/api/v2/auth/login | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8002/api/v2/stats/dashboard | python3 -c "
import sys,json
d=json.load(sys.stdin)
k=d['kpis']
assert 'por_vencer' in k, 'falta por_vencer'
assert 'activos' in k, 'falta activos'
print('✓ campos nuevos OK:', 'activos=', k['activos'], 'por_vencer=', k['por_vencer'])
"

curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8002/api/v2/stats/rendimiento/tendencia?periodo=semana" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert d and 'tutelas' in d[0], 'falta tutelas en tendencia'
print('✓ tendencia con tutelas OK, primer punto:', d[0])
"
```

### 7. Validación visual

Abrir en navegador local:
```
http://15.229.114.148:3003
```

Login con un user de los tenants fake de staging (ARC / Demo). Validar checklist:

- [ ] Login (navy on-brand) responde.
- [ ] Dashboard: sidebar Liquid Glass + fondo metalizado visibles.
- [ ] KPIs en "Operación actual" muestran activos · vencidos · por vencer (números reales del seed).
- [ ] "Histórico acumulado" muestra total + % resueltos.
- [ ] Gráfico de tendencia (área + líneas) renderiza con datos.
- [ ] "Composición por tipo" muestra TUTELA destacada con su %.
- [ ] Trazabilidad funnel renderiza.
- [ ] Tabla "Casos recientes" + botón "Ver todos" → navega a Bandeja.
- [ ] Pestañas admin: Dashboard · **Bandeja** · Enviados · Rendimiento · Configuración (sin "Casos").
- [ ] Bandeja: tabla con cards en glass, filtros funcionan, clic en fila abre detalle.
- [ ] Detalle de caso (overlay): light theme, draft + IA + Enviar funcionan.
- [ ] Settings: sub-nav sticky, formulario perfil funcional.
- [ ] Console del browser: 0 errores rojos.

### 8. Si algo falla → Rollback

```bash
# Volver al commit previo (el de RLS docs en main):
git checkout 9896e3d  # o el head anterior conocido bueno
docker compose -f docker-compose.staging.yml up -d --build backend_staging frontend_staging
# Restaurar el compose original
mv docker-compose.staging.yml.bak docker-compose.staging.yml
```

### 9. Post-validación OK

- [ ] Logs del backend sin errores los últimos 10 min:
  ```bash
  docker compose -f docker-compose.staging.yml logs --tail=200 backend_staging | grep -iE "error|exception|traceback" | head
  ```
- [ ] Avisar al equipo que staging tiene el rediseño.
- [ ] Si todo OK por 24h en staging → mergear PR #9 a `main`.
- [ ] Crear runbook de deploy a PROD (similar al SPRINT_D3 de 2026-05-26).

## ✅ EJECUTADO 2026-05-26 — OK (con 2 hallazgos)

Ejecutado por Claude vía SSH. Tag rollback: `pre-pr9-deploy-20260526_171042`.

**Hallazgo 1 — Realidad del server:** Este server (15.229.114.148) **NO corre el stack `pqrs_staging_*` del `docker-compose.staging.yml`**. Corre el stack normal con prefijo `pqrs_v2_*` (igual que prod local). Es decir, el "staging" en la práctica es este server con `docker-compose.yml` regular, y el `docker-compose.staging.yml` del repo es una idea no implementada. **No se aplicó el fix de NEXT_PUBLIC_API_URL del paso 3** — el frontend bakea con `https://app.flexpqr.com` (env del compose normal). Consecuencia: el rediseño visual se valida OK, pero los campos backend nuevos (`por_vencer`, `activos`, `tutelas/día`) NO llegan al frontend de este server porque apunta a prod (que aún no los tiene). El backend de este server SÍ tiene los campos nuevos en runtime (verificado con grep dentro del container).

**Hallazgo 2 — Build prod TypeScript:** El primer `docker compose up -d --build frontend_v2` falló porque `next build` con strict TS no acepta el cast `stats.kpis as Record<string, number>`. Fix puntual via `as unknown as Record<string, number>` (commit `bbd0f74`, pusheado). Segundo build OK.

**Hallazgo 3 — Cert/key mismatch preexistente:** Al restart de nginx tras el deploy, nginx entró en restart-loop por `SSL_CTX_use_PrivateKey ... key values mismatch`. Causa raíz: los 3 pares cert/key en `nginx/certs/` (`server`, `flexpqr`, `app.flexpqr`) tenían mismatch preexistente (solo `server.*` matcheaba; los otros `.key` son symlinks a `server.key` pero los `.crt` venían de otra key). Nginx llevaba 6 semanas Up con los certs cacheados en RAM → el restart le forzó releer del disco. **Mi pull NO causó esto** (git log de `nginx/certs/` entre HEAD viejo y nuevo no muestra commits). **Fix aplicado**: regeneré los 3 .crt firmados con `server.key` existente (self-signed, CN apropiado, 365 días). Backups en `nginx/certs/*.bak-1712/1713`.

**Validación post-deploy (sin auth real, faltan credenciales):**
- Containers: 8/8 Up + healthy.
- HTTPS local: `/` y `/login` → 200.
- HTTP directo: `localhost:3002/` y `:3002/login` → 200.
- Backend `/docs` → 200, `/api/v2/stats/dashboard` sin auth → 401 (esperado).
- Código nuevo en backend container: `por_vencer`, `activos`, `tut TUTELA` presentes en `/app/app/api/routes/stats.py`.
- Logs backend: `Application startup complete`, sin errores.

**Pendiente (manual por el usuario):**
- Validación visual con login real en staging (no tengo credenciales).
- Si se quiere end-to-end frontend↔backend de este server: rebuild frontend con
  `--build-arg NEXT_PUBLIC_API_URL=http://15.229.114.148:8001` (deuda compose).
- Considerar commitear los certs regenerados al repo o documentar el regen como
  paso de runbook.

## Pendiente arquitectónico (no bloqueante)

La deuda del compose staging apuntando a IPs de prod está documentada en
`Brain/ARQUITECTURA_DE_CAMBIOS_2026-05-21.md:82`. Sería buena la próxima
oportunidad: reorganizar a `docker-compose.base.yml` + overrides `.dev.yml`
/ `.staging.yml` / `.prod.yml` con env vars de URL bien tipadas.
