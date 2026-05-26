# SPRINT D3 — Deploy a Prod 2026-05-26 ✅

**Fecha:** 2026-05-26 (ventana al iniciar jornada AR, ARC con jornada CO cerrando)
**Tag git:** `d3-deploy-prod-2026-05-26`
**PR:** #8 — merge commit `5cd8b01` a `main`
**Rama deployada:** `cleanup/fase1-estructura-2026-05-21` @ `0f892b0`

## Qué se llevó a runtime

- **Sprint Tutelas** (pendiente en runtime desde el 11/5; estaba en filesystem) — frontend nuevo + features completas.
- **C3** — fix del bug Zoho token revocado sin crash-loop + excepciones tipadas + test de regresión (causa raíz de la caída de 13 días de ARC en mayo).
- **RLS (SEC-2026-05-21)** — 7 endpoints IDOR cerrados (`ai.py` ×2, `casos.py` ×5) con opción A: super_admin ve todo, resto scoped por tenant. **Aislamiento multi-tenant ahora real** (antes el backend con BYPASSRLS lo dejaba a merced del filtro explícito, faltante en varios endpoints).
- **DT-41** — el acuse de cortesía ya no se envía a remitentes judiciales (`@ramajudicial`, `@cendoj…`, etc.).
- **Fase 1/2** — limpieza estructural + C5/C7.

## Procedimiento (5 pasos, runbook ejecutado)

1. **Backup DB** a S3 → `s3://flexpqr-backups-prod/backup_pre_d3_20260526_150507.dump.gz` (29.6 MiB).
2. **Checkout** rama PR #8 en prod (rollback target: `d757ffa`).
3. **Rebuild + recreate** backend + master_worker + demo_worker.
4. **Frontend** (regla inmutable — bind-mount): `docker exec ... npm run build` + `restart frontend + nginx`.
5. **Validación** post-deploy: containers healthy, HTTP 200 en `/` y `/login`, ingesta procesando sin errores, marcadores `SEC-2026-05-21` confirmados en el código del container.

## Validación post-deploy

| Check | Resultado |
|---|---|
| 8/8 containers | healthy / Up |
| Frontend `/` y `/login` | HTTP 200 |
| Backend `/docs` vía nginx | 404 (esperado, Swagger cerrado en prod) |
| Ingesta ARC | siguió procesando; último caso `2026-05-26 15:16` |
| Errores worker últimos 5 min post-deploy | 0 |
| Código nuevo en runtime | `SEC-2026-05-21` presente en `casos.py` y `ai.py` |

## Rollback (no usado)

`git checkout d757ffa` + rebuild + frontend build + recreate. La DB no se tocó
(PR #8 sin migraciones); backup en S3 por las dudas.

## Pendientes post-deploy

- [ ] **Validar aislamiento RLS** con cuentas reales (user de un tenant intentando ver casos de otro → 404).
- [ ] **RLS defensa en profundidad**: cambiar el rol del backend a uno SIN BYPASSRLS (la segunda barrera real). Requiere manejo cuidadoso de super_admin.
- [ ] Avisar a Paola que está OK.
- [ ] Monitorear ingesta las próximas horas.
- [ ] Confirmar lo del client_secret de Zoho (pendiente de 5 días — ARC sigue vivo, sin urgencia).
