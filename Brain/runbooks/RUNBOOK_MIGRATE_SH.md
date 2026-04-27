# Runbook — `scripts/migrate.sh`

**Audiencia:** ops, dev.
**Última revisión:** 2026-04-27.
**Archivo:** `scripts/migrate.sh` (origin/develop).

Documento operativo. Cómo aplicar migraciones, rollback, desbloquear lock, consultar historial.

Para arquitectura del sprint, ver [[SPRINT_TUTELAS_S123]].

## 1. Anatomía

`migrate.sh` aplica las SQLs de `migrations/` (top-level, sin `migrations/baseline/`) en orden lexicográfico contra el ambiente target via SSH + `docker exec`. Mantiene historial en la tabla `aequitas_migrations` (filename + sha256 + applied_at + applied_by) y un lock por tabla (`aequitas_migrations_lock`).

Convenciones:
- `00_baseline_schema.sql` = baseline pg_dump schema-only de prod.
- `0X_..._.sql` (1-13, 15-21) = migraciones formales del sistema.
- `99_seed_*.sql` = fixtures sintéticos solo-staging (guard `--env != staging` aborta).

## 2. Flags

| Flag | Efecto |
|---|---|
| `--env=staging` | Apunta al host SSH `flexpqr-staging`. Permite aplicar `99_seed_*`. |
| `--env=prod` | Apunta a `flexpqr-prod`. **ABORTA** si encuentra archivo `99_seed_*` en `migrations/`. |
| `--dry-run` | Lista qué se aplicaría, no toca DB. |

## 3. Uso típico

### Listar migraciones que se aplicarían (dry-run)

```bash
./scripts/migrate.sh --env=staging --dry-run
```

Salida esperada:
```
→ Inventariando migraciones en /.../migrations...
  X archivo(s):
    - 00_baseline_schema.sql
    - 14_regimen_sectorial.sql
    - 18_check_semaforo_extendido.sql
    - 19_tutelas_pipeline_foundation.sql
    - 20_user_capabilities.sql
    - 21_tutelas_view.sql
    - 22_add_correlation_id.sql
    - 99_seed_staging.sql

→ Procesando migraciones...
  ✓ ya aplicada: 00_baseline_schema.sql
  ...
  [DRY-RUN] aplicaría: 22_add_correlation_id.sql  (sha256=b5b76852a9e6...)
```

### Aplicar pendientes

```bash
./scripts/migrate.sh --env=staging
```

Idempotente: re-ejecutar con todo aplicado da `Resumen: 0 aplicada(s), N ya aplicadas/skipped`.

### Aplicar contra prod (ventana controlada)

```bash
# 1. Backup pre-deploy:
ssh flexpqr-prod "docker exec pqrs_v2_db pg_dump -F c pqrs_v2 > /tmp/pre_deploy_$(date +%s).dump"

# 2. Dry-run primero:
./scripts/migrate.sh --env=prod --dry-run

# 3. Aplicar:
./scripts/migrate.sh --env=prod
```

⚠️ El runner aborta si encuentra `99_seed_*`. Eso es intencional — staging-only fixture data.

## 4. Consultar historial

```sql
SELECT id, filename, substring(sha256, 1, 12) AS sha,
       applied_at, applied_by
FROM aequitas_migrations
ORDER BY applied_at;
```

`sha256` permite detectar si un archivo ya aplicado fue modificado posteriormente (auditoría de tampering).

## 5. Advisory lock colgado — desbloqueo

Si `migrate.sh` se mata mid-run (Ctrl+C, SSH dropout), la fila de lock queda. Síntoma del próximo run:

```
ERROR: no se pudo tomar el lock de migraciones. Otro run está activo o quedó un lock stale.
  Lock actual: migrate-sh-nico-12345-1761578400 since 2026-04-27 14:02:00
```

Resolver:

```sql
DELETE FROM aequitas_migrations_lock WHERE lock_id = 1;
```

Verificar antes que **nadie** está corriendo `migrate.sh` ahora mismo (otro dev, cron). Si hay duda, verificar PID del lock_tag:
- Tag formato: `migrate-sh-<user>-<pid>-<timestamp>`.
- Si ese PID no está corriendo → safe to delete.

## 6. Rollback de migración individual

⚠️ **`migrate.sh` NO tiene `--rollback` automático.** Razón: las migraciones son DDL irreversible (`ADD COLUMN`, `CREATE TABLE`) y un rollback automático genérico es peligroso.

Procedimiento manual:

1. **Identificar la migración a revertir:**
   ```sql
   SELECT * FROM aequitas_migrations WHERE filename = 'NN_xxx.sql';
   ```

2. **Escribir SQL de reverso explícito.** Ejemplo para revertir `22_add_correlation_id.sql`:
   ```sql
   BEGIN;
   ALTER TABLE pqrs_casos DROP COLUMN IF EXISTS correlation_id;
   DROP INDEX IF EXISTS idx_pqrs_correlation;
   DELETE FROM aequitas_migrations WHERE filename = '22_add_correlation_id.sql';
   COMMIT;
   ```

3. **Aplicarlo en `BEGIN;` ... `COMMIT;` con `psql` directo**, fuera de `migrate.sh`.

4. **Verificar** con la query de información_schema que la columna/tabla efectivamente desapareció.

5. **Si la migración había insertado datos** (e.g. la 14 inserta `sla_regimen_config` y `festivos_colombia`), evaluar si esos datos también deben removerse. Revisar el archivo SQL original.

## 7. Aplicar migración nueva

1. Crear archivo en `migrations/` con prefijo numérico siguiente (`23_xxx.sql`).
2. Validar localmente con `--dry-run`.
3. Aplicar a staging primero: `./scripts/migrate.sh --env=staging`.
4. Validar con queries de `information_schema`.
5. Si todo OK, escribir RUNBOOK / actualizar Brain si la migración cambia el schema visible.
6. Para prod: backup + ventana + `--env=prod`.

## 8. Bug fix conocido: `((X++))` con `set -e`

Bug fixeado en commit `100b6de` (post Agente 1 staging rebuild). El runner usaba `((SKIPPED++))` que aborta con `set -e` cuando la variable está en 0 (post-increment retorna el valor anterior = 0 = "failure"). Corregido a `SKIPPED=$((SKIPPED + 1))`.

Si alguien clona una versión vieja del script, **observación de síntoma**: el runner se detiene tras la primera "✓ ya aplicada" sin procesar las siguientes migraciones.

## 9. DT-29 — `--noconftest` en pytest

Por separación: cuando se ejecutan **tests** del backend en env local, hay que pasar `--noconftest` para evitar que el `conftest.py` global intente cargar `app.main` que importa `storage_engine` con retries de MinIO. No tiene relación directa con `migrate.sh` — solo afecta a la suite de tests. Documentado en [[DEUDAS_PENDIENTES]] DT-29.

## 10. Migraciones del sprint Tutelas (referencia)

| # | Archivo | Qué hace |
|---|---|---|
| 18 | `18_check_semaforo_extendido.sql` | ADD COLUMN `semaforo_sla` + CHECK 5 valores (VERDE/AMARILLO/NARANJA/ROJO/NEGRO). |
| 19 | `19_tutelas_pipeline_foundation.sql` | `metadata_especifica` JSONB + `tutela_*` cols + `documento_peticionante_hash` + `config_hash_salt` + 3 índices + trigger híbrido `fn_set_fecha_vencimiento`. |
| 20 | `20_user_capabilities.sql` | Tabla `user_capabilities` + RLS + grants default ARC TUTELA. |
| 21 | `21_tutelas_view.sql` | MATERIALIZED VIEW `tutelas_view` polimórfica + 3 índices. |
| 22 | `22_add_correlation_id.sql` | ADD COLUMN `correlation_id` UUID NOT NULL + índice (fix smoke E2E). |

Las anteriores (00, 14) más el seed (99) son baseline + sectorial + fixture staging.
