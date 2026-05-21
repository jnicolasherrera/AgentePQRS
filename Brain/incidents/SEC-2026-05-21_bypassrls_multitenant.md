# SEC-2026-05-21 — Aislamiento multi-tenant no protegido por RLS (BYPASSRLS)

**Severidad:** ALTA (seguridad — posible fuga cross-tenant en producción)
**Estado:** detectado 2026-05-21, remediación pendiente
**Detectado durante:** análisis de arquitectura / Fase 2 (item RLS)

## Hallazgo

El backend se conecta a PostgreSQL con el rol **`pqrs_admin`**, que tiene
**`BYPASSRLS = true`**. Verificado:

```
pqrs_casos.relrowsecurity = true        (RLS "activado" en la tabla)
pqrs_admin.rolbypassrls   = true        (rol del backend — IGNORA las policies)
aequitas_worker.rolbypassrls = true
```

`get_db_connection` (db.py) setea `app.current_tenant_id` por conexión, y existen
políticas RLS en `pqrs_casos`. **Pero como el rol de conexión tiene BYPASSRLS, las
políticas no se aplican.** El aislamiento entre tenants (ARC / FlexFintech / Demo)
depende **únicamente** del filtro explícito `WHERE cliente_id` en cada query.

## Impacto

Endpoints que consultan `pqrs_casos` **sin** filtro explícito de `cliente_id`
devuelven/operan sobre datos de **todos los tenants**. Identificados (a auditar en
detalle):
- `casos.py` `/borrador/pendientes` (leak ya conocido como "C1" del tablero)
- `stats.py` — WHERE dinámico (verificar que incluya cliente_id siempre)
- varios `WHERE id = $1` (acceso por id sin verificar pertenencia al tenant)
- `ai.py` — `SELECT/UPDATE pqrs_casos WHERE id = $1`

Razón por la que no estalló aún: la mayoría de los endpoints de listado SÍ filtran
por `cliente_id`; el riesgo está en los que no, y en accesos por id conocido.

## Remediación propuesta (sprint de seguridad)

1. **Auditoría completa**: clasificar cada endpoint que toca `pqrs_casos`/`pqrs_adjuntos`/
   `audit_log_respuestas` en: tenant-scoped (debe filtrar `cliente_id`) vs super_admin
   (ve todos, intencional).
2. **Filtro explícito `cliente_id`** en todos los tenant-scoped — defensa real (no
   depender de RLS dado el BYPASSRLS). Para acceso por id: `WHERE id=$1 AND cliente_id=$2`.
3. **Tests de aislamiento**: crear 2º tenant + casos, probar que A no ve B (modernizar
   los `test_rls_hierarchy` que hoy están en `scripts/manual/`).
4. **Evaluar** conectar el backend con un rol SIN BYPASSRLS para que RLS sea defensa
   en profundidad real (cuidado: super_admin necesita ver todos → vía rol/flag aparte).
5. **Validar en staging** con los 3 tenants reales antes de tocar prod.

## Por qué NO se parchea a ciegas

Agregar filtros sin distinguir endpoints super_admin rompería la visibilidad global
legítima (admin/coordinador/auditor). Y cambiar el rol de conexión sin entender qué
queries dependen del bypass puede romper el panel de super_admin. Requiere auditoría
+ tests + staging.
