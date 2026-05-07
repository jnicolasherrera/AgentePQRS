# Staging reconstruido — FASE C' completada

**Fecha:** 2026-04-23
**Host:** `flexpqr-staging` → 15.229.114.148, container `pqrs_v2_db`, DB `pqrs_v2`.
**Referencia previa:** `SPRINT_TUTELAS_S123_BASELINE_PROD_SCHEMA.md` (baseline aplicado), `SPRINT_TUTELAS_S123_BLOQUEANTE_DRIFT_REPO.md` (por qué fue necesario).

## Qué se hizo

1. **C'.1 Backup:** `pg_dump pqrs_v2` del staging antes del reset → `/tmp/staging_pre_rebuild_20260423_1607.sql` en staging (461 líneas, 14.9 KB — consistente con estado esqueleto previo).
2. **C'.2 Reset:** `DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ...`. Post-drop: 0 tablas.
3. **C'.3 Aplicación:** `./scripts/migrate.sh --env=staging` aplicó las 3 migraciones en orden. Nada failed.

### Registro en `aequitas_migrations`

| Orden | Archivo | Applied at |
|---|---|---|
| 1 | `00_baseline_schema.sql` | 2026-04-23 16:08:30 |
| 2 | `14_regimen_sectorial.sql` | 2026-04-23 16:09:27 |
| 3 | `99_seed_staging.sql` | 2026-04-23 16:09:30 |

### Estado post-rebuild

13 tablas: 9 del baseline de prod + 2 del régimen sectorial (`festivos_colombia`, `sla_regimen_config`) + 2 de control (`aequitas_migrations`, `aequitas_migrations_lock`).

### Datos sintéticos del seed 99

- 2 tenants fake: `ARC Staging (fake)` FINANCIERO (UUID `00000000-0001-...`), `Demo Staging (fake)` GENERAL (UUID `00000000-0002-...`). Dominios `*.invalid`.
- 8 usuarios fake (password hash placeholder, nunca válido para login).
- 25 casos sintéticos para ARC: 5 PETICION + 5 QUEJA + 5 RECLAMO + 5 SUGERENCIA + 5 TUTELA (todas con marker `SYNTHETIC_FIXTURE_V1`).
- 22 festivos Colombia 2026 + 24 filas `sla_regimen_config` (8 tipos × 3 regímenes).

## C'.4 Smoke tests

### Test 1 — Trigger `fn_set_fecha_vencimiento` (con fix)

Verifica que el trigger calcula `fecha_vencimiento` sin explotar por `semaforo_sla` (fix aplicado en `migrations/14_regimen_sectorial.sql`).

| Caso | Régimen tenant | fecha_recibido | fecha_vencimiento calculada | Delta | ¿Correcto? |
|---|---|---|---|---|---|
| QUEJA | FINANCIERO (ARC) | 2026-04-20 10:00 | 2026-04-30 23:59 | 10 días calendario / 8 hábiles | ✓ SFC CBJ = 8 días hábiles |
| TUTELA | FINANCIERO (ARC) | 2026-04-20 10:00 | 2026-04-22 23:59 | 2 días | ✓ Decreto 2591/1991 |

Ambos tests corrieron en `BEGIN ... ROLLBACK`, no dejaron datos.

### Test 2 — RLS `tenant_isolation_pqrs_policy`

| Verificación | Estado |
|---|---|
| `relrowsecurity` | **t** en `pqrs_casos, config_buzones, pqrs_adjuntos, pqrs_comentarios, usuarios` |
| `relforcerowsecurity` | **t** en `pqrs_casos, usuarios` (las 2 críticas) |
| Policy `tenant_isolation_pqrs_policy` | presente, `polcmd='*'`, permissive |

**No se pudo probar empíricamente** con SELECTs porque los dos únicos roles disponibles (`pqrs_admin` superuser, `aequitas_worker` con `rolbypassrls=t`) bypassean RLS por diseño. Esto es consistente con prod: el sistema usa `current_setting('app.current_tenant_id')` como variable de sesión que la app auto-impone en sus queries; no como enforcement a nivel de rol DB. RLS queda como defensa en profundidad.

**Observación (no bloqueante):** si se quisiera enforcement real a nivel DB, habría que crear un rol `pqrs_app` sin `rolbypassrls` y hacer que la app se conecte con él. No es parte del sprint Tutelas — lo anoto como posible deuda futura.

### Test 3 — Backend `/health`

- `GET http://staging:8001/health` → 404 (esta versión del backend no expone `/health`).
- `GET http://staging:8001/` → 200 `{"status":"ok","message":"FlexPQR API está VIVO."}`.
- `GET http://staging:8001/docs` → 200 (Swagger cargando).

**Observación:** el backend de staging tiene connection pool abierto desde hace 2 semanas contra la DB vieja. Como recién recreamos el schema, las conexiones stale pueden fallar en el primer query contra las nuevas tablas. Si se va a usar el backend en staging, reiniciar con `docker compose restart pqrs_v2_backend`. No es bloqueante del sprint Tutelas.

## Comportamiento del runner `scripts/migrate.sh`

Probado:
- **Dry-run:** lista 3 archivos en orden, no aplica nada.
- **Run real:** aplica en orden, registra sha256 en `aequitas_migrations`, toma lock por tabla.
- **Idempotencia:** un segundo run saltea las 3 (mensaje "✓ ya aplicada").
- **Bug encontrado y fixeado:** `((SKIPPED++))` aborta con `set -e` cuando la variable está en 0 (post-increment retorna 0 = "failure"). Fixed a `SKIPPED=$((SKIPPED + 1))`.

Pendiente de probar en condiciones reales:
- Guard de staging-only contra `--env=prod` (no se va a tocar prod en este sprint, así que el test queda teórico hasta el sprint de deploy real).

## Diferencia vs prod

Staging reconstruido es un superset de prod (agrega `festivos_colombia`, `sla_regimen_config`, `regimen_sla`, SP + trigger de la 14) + las 2 tablas de control de migraciones. Cuando la 14 se deploye a prod en sprint separado, las dos estructuras coincidirán.

## Qué NO quedó hecho en esta fase

- Rotación de credenciales ARC en `05_multi_provider_buzones.sql` (deuda DT-20, 7 días, fuera de alcance).
- Reinicio del backend de staging (operación, no parte del sprint de migraciones).
- Prueba empírica de RLS con rol no-bypass (no bloqueante; el DDL está correcto).
