# Rollback plan — Sprint Tutelas

**Documento de contingencia.** Si el sprint Tutelas en staging (o en el futuro deploy a prod) introduce regresiones graves, este documento describe los pasos de reversión segura.

**Última revisión:** 2026-04-27 (post Agente 6).

## Pre-requisitos

- SSH a `flexpqr-staging` (o `flexpqr-prod` si es deploy productivo).
- Backup pre-deploy existente. Si no se hizo, capturar **antes** de cualquier rollback:
  ```bash
  ssh flexpqr-staging "docker exec pqrs_v2_db pg_dump -F c pqrs_v2 > /tmp/pre_rollback_$(date +%s).dump"
  ```

## Triage rápido (5 min)

**¿Es un bug del código Python o del schema DB?**

| Síntoma | Causa probable | Acción |
|---|---|---|
| Errores `column "X" does not exist` | Migración faltante en DB o pull sin re-aplicar | `./scripts/migrate.sh --env=staging` |
| Errores en pipeline (`enrich_tutela`, `vinculacion`) | Código Python | Rollback código (sección 1) |
| Triggers comportándose mal | Migración 19 (función `fn_set_fecha_vencimiento`) | Rollback selectivo migración 19 (sección 2) |
| Casos sin `correlation_id` | Migración 22 falló o se revirtió | Re-aplicar mig 22 (`./scripts/migrate.sh --env=staging`) |
| Backend o workers no arrancan | Image / dependency / bind mount | Rollback container (sección 3) |
| Tutelas sin metadata | Claude API down o `ANTHROPIC_API_KEY` revocada | Verificar key. Pipeline fallback es defensivo, no debería romper nada. |

## 1. Rollback código Python (sin tocar DB)

Útil si los módulos nuevos del Agente 2/3 introdujeron bugs y queremos volver a la versión pre-sprint.

```bash
# 1. En el repo local:
git log --oneline | grep -i "Agente\|sprint"   # localizar el commit anterior al sprint
# Pre-sprint: 0713f74 (fix(sla): festivos_colombia)

# 2. Revertir code-only (NO migraciones SQL):
#    El sprint introdujo módulos nuevos como sla_engine, pipeline, enrichers, vinculacion.
#    Esos NO existen pre-sprint. Revertirlos = borrar archivos.

# Opción A — revert quirúrgico (preserva commits de Brain):
git revert --no-commit \
  bba7f67 \   # refactor(workers): 3 workers invocan pipeline unificado
  e28e355 \   # fix(db_inserter): propagar external_msg_id...
  f6a9ca8 \   # feat(db): db_inserter acepta metadata...
  6b3bf9f \   # feat(pipeline): unificador
  443f915 \   # feat(scoring): semaforo polimorfico
  57530fa \   # feat(capabilities)
  2105773 \   # feat(sla)
  be47e66 \   # feat(ai): tutela_extractor
  0a6f59c \   # feat(enrichers): dispatcher
  f866dd1     # feat(services): vinculacion
git commit -m "revert(sprint-tutelas): rollback codigo Python pre-sprint"
git push origin develop

# 3. En staging server:
ssh flexpqr-staging "cd ~/PQRS_V2 && git pull origin develop && docker compose -f docker-compose.yml -f docker-compose.staging.override.yml restart backend_v2 master_worker_v2 demo_worker_v2"

# 4. Verificar que el sistema procesa PQRS normal (sin tutelas):
ssh flexpqr-staging "curl -s http://localhost:8001/"
```

**Side effect:** las migraciones 18-22 quedan aplicadas en DB (no las tocamos). Las columnas `metadata_especifica`, `tutela_*`, `correlation_id`, `documento_peticionante_hash` siguen existiendo. Quedan NULL en INSERTs futuros (no hay enricher invocado). El trigger DB `fn_set_fecha_vencimiento` queda en su versión 14 vieja si revertimos la migración 19 también; para preservar SLA simple, **mejor no revertir mig 19 con código rollback**.

## 2. Rollback selectivo de migración 19 (trigger híbrido)

Si el trigger híbrido `fn_set_fecha_vencimiento` (3 capas) está causando problemas, restaurar la versión simple de la migración 14:

```sql
BEGIN;
CREATE OR REPLACE FUNCTION fn_set_fecha_vencimiento()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.tipo_caso IS NOT NULL AND NEW.fecha_recibido IS NOT NULL THEN
    NEW.fecha_vencimiento := calcular_fecha_vencimiento(
      NEW.fecha_recibido, NEW.cliente_id, NEW.tipo_caso
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Quitar el registro de mig 19 ya aplicada para que pueda re-aplicarse después.
DELETE FROM aequitas_migrations WHERE filename = '19_tutelas_pipeline_foundation.sql';
COMMIT;
```

Esto restaura la lógica original sin remover las columnas `metadata_especifica`/`tutela_*`. El pipeline Python deja de intentar precalcular fecha y todo cae al SP sectorial.

## 3. Rollback container (versión imagen anterior)

Si el problema es solo de container (bind mount mal apuntado, env var perdida, etc.):

```bash
ssh flexpqr-staging "
  cd ~/PQRS_V2 &&
  # Apagar con override (apaga bind mounts):
  docker compose -f docker-compose.yml -f docker-compose.staging.override.yml down &&
  # Levantar SIN override (vuelve al modo COPY . . sin bind):
  docker compose up -d
"
```

⚠️ Esto pierde los caps de logs del override. Aceptable para un rollback temporal.

## 4. Rollback completo de migraciones DB (CASE EXTREMO)

⚠️ **Solo si todo lo anterior falló y el schema está corrupto.** Implica restore desde dump.

```bash
# 1. Obtener un dump pre-sprint. Si no se hizo, no hay vuelta atrás indolora.
#    Backup más reciente válido: pre-sprint = pre 2026-04-23.
#    Si no existe, es imposible rollback sin pérdida de datos.

# 2. Restore (DESTRUYE DATOS POST-SPRINT):
ssh flexpqr-staging "docker exec -i pqrs_v2_db pg_restore --clean --if-exists -U pqrs_admin -d pqrs_v2 < /tmp/pre_sprint.dump"

# 3. La tabla aequitas_migrations queda como estaba pre-sprint, así que migrate.sh
#    re-aplicará 18-22 si querés volver a aplicar. Decidir si.
```

⚠️ **NO ejecutar el restore en prod sin autorización explícita de Nico + ventana coordinada.** Pierde los datos productivos del periodo del sprint.

## 5. Revocar capabilities ARC (case si se otorgaron mal)

```sql
UPDATE user_capabilities
SET revoked_at = NOW()
WHERE cliente_id = 'effca814-b0b5-4329-96be-186c0333ad4b'
  AND scope = 'TUTELA'
  AND revoked_at IS NULL;
```

Conserva el historial (no borra). Re-otorgar luego con `grant_capability`.

## 6. Caso del smoke en staging

Si en algún rollback masivo vas a hacer `pg_restore` de staging, antes de eso preserva el caso `0f83ce56-7f9c-4209-ba3d-2a5be8ef33ae`:

```sql
-- O bien anota su existencia, o re-créalo manualmente luego.
-- Ese caso es referencia del test_arc_smoke_case_persiste (Agente 4 QA).
```

Alternativamente, ejecutar el smoke de nuevo (consume 1 call Claude) post-restore.

## 7. Quién avisa qué cuando

- **Nico**: notifica al stakeholder operativo (Paola Lombana ARC) si el rollback toca tutelas en runtime.
- **Si el rollback es de prod**: comunicar a Dante / Martín antes de tocar.
- **CloudWatch alarms**: silenciar las nuevas alarmas tutela (si están deployadas) durante la ventana de rollback para no spammear.

## 8. Verificación post-rollback

| Check | Cómo |
|---|---|
| Backend up | `curl http://staging:8001/` → 200 |
| Workers up | `docker compose ps` → master_worker, demo_worker UP |
| DB intacta | `SELECT COUNT(*) FROM pqrs_casos WHERE cliente_id = '<arc>';` ≥ pre-rollback |
| ARC seed intacto | `pytest tests/integration/test_arc_regression.py -v` con `RUN_STAGING_REGRESSION=1` |
| Smoke | Crear caso QUEJA simple via INSERT directo + verificar trigger calculó fecha |

## 9. Trazabilidad

Cualquier rollback debe documentarse en:
- Commit message con prefijo `revert(sprint-tutelas):`.
- Entrada nueva en `Brain/CHANGELOG.md` bajo `[Unreleased]`.
- Update de `Brain/sprints/SPRINT_TUTELAS_S123_PROGRESS.md` marcando el rollback.
