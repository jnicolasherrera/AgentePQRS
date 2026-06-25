# Spec — C2: Migración a RLS real (aislamiento multi-tenant por Postgres)

**Fecha:** 2026-06-25
**Origen:** Hallazgo C2 de la auditoría full 2026-06-25 (`Brain/auditoria/00_INFORME_MAESTRO.md`). Dimensionamiento previo: `Brain/auditoria/C2_dimensionamiento_RLS.md`.
**Alcance:** Backend (conexión DB) + esquema DB (policies RLS) + testing por rol. Multi-tenant (FlexFintech, Abogados Recovery, Demo).

## Problema

El backend se conecta a Postgres como **`pqrs_admin`** (`rolsuper=t`, `rolbypassrls=t`). Ese rol **ignora todas las Row-Level Security policies**. Resultado: el aislamiento entre tenants NO lo garantiza la base de datos — depende 100% de que cada query del código incluya manualmente `WHERE cliente_id = <tenant>`. Cualquier query que olvide ese filtro es una **fuga cross-tenant** (ej. el bug C1 `download_adjunto`, y los riesgos A3/A4 sobre carteras). El RLS ya está parcialmente configurado pero **inerte**.

## Estado actual (verificado en prod 2026-06-25)

- **Código YA inyecta el contexto RLS**: `backend/app/core/db.py` `get_db_connection` setea por request `app.current_tenant_id`, `app.current_user_id`, `app.current_role`, `app.is_superuser` vía `set_config(..., is_local=false)` y los limpia en el `finally`. Existe `execute_in_rls_context` para workers.
- **Rol destino ya existe**: `pqrs_backend` (`rolsuper=f`, `rolbypassrls=f`) con GRANTs SELECT/INSERT/UPDATE/DELETE sobre las 20 tablas.
- **10/20 tablas ya tienen RLS + policy** y las policies usan exactamente `current_setting('app.current_tenant_id')::uuid OR current_setting('app.is_superuser')='true'` — compatible con lo que el código setea.
- **Falta**: el backend NO usa `pqrs_backend` (usa `pqrs_admin`); 4 tablas multi-tenant sin policy; casos especiales sin definir.

## Decisiones tomadas

1. **El backend se conecta como `pqrs_backend`** (no-superuser, RLS activo). El cambio es vía variable de entorno (`DATABASE_URL` en `.env`/compose de prod), NO hardcode en `config.py`. Reversible: volver a `pqrs_admin` + restart.
2. **El aislamiento de tenant lo garantiza Postgres** (RLS), el código mantiene sus `WHERE cliente_id` como defensa en profundidad (no se remueven).
3. **`app.is_superuser` sigue siendo el bypass legítimo** para `super_admin` (ya lo setea el código y lo leen las policies). NO se toca esa lógica.
4. **Workers fuera de alcance de C2**: `master_worker` usa `aequitas_worker` (`rolbypassrls=t`). Se deja bypasseando por ahora (worker confiable, no expuesto a usuarios). Migrarlo es un C2-fase-2 separado.
5. **Despliegue: STAGING primero.** Hay stack `pqrs_staging_*` en la misma máquina. Se valida ahí por rol antes de prod.
6. **`set_config` con `is_local=false`** se mantiene por ahora (el código ya lo usa y limpia en finally). Migrar a `SET LOCAL` transaccional es una mejora deseable pero NO bloqueante para C2 (se evalúa en el plan; riesgo MEDIO de fuga por conexión reusada del pool, hoy mitigado por la limpieza en finally).

## Comportamiento esperado (criterios de aceptación por rol)

Con el backend corriendo como `pqrs_backend` (RLS activo), para CADA tabla multi-tenant:

| Rol | Comportamiento esperado |
|---|---|
| `super_admin` | Ve/opera TODOS los tenants (vía `app.is_superuser='true'`). Sin cambios respecto a hoy. |
| `admin` (de un tenant) | Ve/opera SOLO filas de su `cliente_id`. Una query a otro tenant devuelve 0 filas (no error). |
| `abogado` / `analista` | Ve SOLO su tenant a nivel RLS; el filtro de cartera (`asignado_a`) sigue a nivel código. |
| `auditor` | Ve su tenant (lectura). |
| Sin tenant / token inválido | RLS no matchea → 0 filas. Login y `/auth/me` deben seguir funcionando (ver caso especial `clientes_tenant`). |

**Invariante de no-regresión:** TODOS los flujos que hoy funcionan para un usuario legítimo dentro de su tenant deben seguir funcionando idénticos. El cambio solo debe BLOQUEAR accesos cross-tenant indebidos, nunca accesos legítimos.

## Cambios por capa

### DB — activar RLS + policy en las 4 tablas multi-tenant que faltan
Tablas: `audit_log_respuestas`, `borrador_feedback`, `kb_ingestion_log`, `pqrs_clasificacion_feedback`.
- `ALTER TABLE ... ENABLE ROW LEVEL SECURITY;`
- `CREATE POLICY tenant_isolation_<tabla>_policy ON <tabla> FOR ALL USING (cliente_id = current_setting('app.current_tenant_id', true)::uuid OR current_setting('app.is_superuser', true) = 'true');`
- **Columnas verificadas en prod (2026-06-25):**
  - `borrador_feedback`, `kb_ingestion_log`, `pqrs_clasificacion_feedback` → tienen `cliente_id` → **policy directa** (patrón de arriba).
  - **`audit_log_respuestas` NO tiene `cliente_id`** (sí `caso_id`) → **policy por JOIN**: `USING (caso_id IN (SELECT id FROM pqrs_casos WHERE cliente_id = current_setting('app.current_tenant_id', true)::uuid) OR current_setting('app.is_superuser', true) = 'true')`. Alternativa a evaluar en el plan: agregar columna `cliente_id` denormalizada (más simple para la policy, pero requiere backfill + mantener en el INSERT). **Decidir en el plan: JOIN vs columna.**

### DB — casos especiales (definir en el plan, requieren análisis)
- **`clientes_tenant`** (tabla de tenants): un usuario debe poder leer SU propio tenant (login/`/auth/me`). Policy especial: `id = current_setting('app.current_tenant_id')::uuid OR is_superuser`. **Crítico** — si esto queda mal, se rompe el login.
- **`plantillas_respuesta`**: definir si es global (sin RLS) o por-tenant (con policy). Hoy sin RLS.
- **`festivos_colombia`, `aequitas_migrations(_lock)`**: globales, se dejan SIN RLS (correcto).
- **`pqrs_comentarios_bak_20260625`**: backup temporal, BORRAR antes de C2 (ya validado el cleanup).

### DB — GRANTs y secuencias
- Verificar que `pqrs_backend` tenga `USAGE` sobre las secuencias usadas por columnas `serial`/`default nextval` (los GRANTs de tabla no incluyen secuencias). Si falta, `GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO pqrs_backend;`.
- Verificar GRANT `EXECUTE` sobre funciones que el backend invoque, si las hay.

### Código — cambiar el rol de conexión
- `DATABASE_URL` pasa a usar `pqrs_backend` en el `.env`/compose de prod (y staging). El default de `config.py:5` se puede actualizar también a `pqrs_backend` para coherencia, pero el valor efectivo SIEMPRE viene de env.
- **NO** se remueven los `WHERE cliente_id` existentes (defensa en profundidad).

## Riesgos y mitigaciones

- **ALTO — query sin filtro que hoy anda por el bypass → 0 filas en silencio tras RLS.** No lanza error, devuelve datos vacíos (ej. "el dashboard aparece vacío"). Mitigación: testing exhaustivo por rol en staging sobre TODOS los endpoints de lectura; revisar logs por queries que devuelvan 0 inesperadamente.
- **CRÍTICO — `clientes_tenant` sin policy correcta → login roto.** Mitigación: policy especial + test de login de los 3 tenants ANTES de tocar prod.
- **MEDIO — INSERT falla por secuencia sin GRANT.** Mitigación: GRANT de secuencias + test de creación de caso/comentario.
- **MEDIO — conexión del pool reusa contexto de tenant anterior.** Hoy mitigado por la limpieza en `finally` de `get_db_connection`. Evaluar `SET LOCAL` en el plan.
- **BAJO — workers (`aequitas_worker` bypass) no afectados** (fuera de alcance).

## Estrategia de validación / rollback

1. Aplicar policies nuevas + GRANTs en **staging** (`pqrs_staging_db`).
2. Cambiar el backend de staging a `pqrs_backend`, restart.
3. Test matriz rol × flujo (login, bandeja, detalle de caso, envío de lote, stats/dashboard, plantillas, adjuntos) para los 3 tenants + super_admin.
4. Test negativo: usuario de tenant A NO accede a datos de tenant B (repetir el patrón del test de C1 sobre varias tablas).
5. Solo tras OK en staging → replicar en prod (deploy quirúrgico de DDL + cambio de env var + restart backend).
6. **Rollback:** revertir `DATABASE_URL` a `pqrs_admin` + restart (instantáneo). Las policies nuevas son aditivas y se pueden `DROP POLICY` sin afectar el bypass.

## Fuera de alcance (futuro)
- Migrar workers a un rol no-bypass (C2-fase-2).
- Migrar `set_config(is_local=false)` → `SET LOCAL` transaccional (mejora de robustez).
- Remover los `WHERE cliente_id` redundantes del código (se conservan como defensa en profundidad).

## Tests (resumen — se detallan en el plan)
- Por cada tabla con policy nueva: super_admin ve todo; admin de tenant A ve solo A; cross-tenant = 0 filas.
- Login + `/auth/me` OK para los 3 tenants (valida `clientes_tenant`).
- Creación de caso/comentario OK (valida GRANTs de secuencia).
- No-regresión: suite de tests existente (`backend/tests/`) pasa con `pqrs_backend`.
