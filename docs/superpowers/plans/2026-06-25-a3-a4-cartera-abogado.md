# Plan — A3/A4 filtro de cartera (`asignado_a`)

Spec: `docs/superpowers/specs/2026-06-25-a3-a4-cartera-abogado-design.md`
Archivo único a tocar: `backend/app/api/routes/casos.py` (prod == main en estas 2 funciones, verificado).

## Fase 1 — Implementación (Claude Code CLI)

### Tarea 1.1 — A3: filtro de cartera en `get_caso_detalle`
En la query de `get_caso_detalle`, cambiar el WHERE:
- DE:  `WHERE c.id = $1 AND ($2 OR c.cliente_id = $3)`
- A:   `WHERE c.id = $1 AND ($2 OR c.cliente_id = $3) AND ($4 OR c.asignado_a = $5)`
Agregar los 2 params nuevos a la llamada `fetchrow`, después de los existentes:
- `$4`: `current_user.role in {"admin","coordinador","super_admin","auditor"}`
- `$5`: `uuid.UUID(current_user.usuario_id)`
**Verificar:** `python -m py_compile`; el WHERE tiene `c.asignado_a = $5`.

### Tarea 1.2 — A4: guard de reasignación + scope de cartera en `update_caso`
1. Al inicio de `update_caso` (antes de armar `updates`), agregar:
   ```
   ROLES_VEN_TODO = {"admin", "coordinador", "super_admin", "auditor"}
   if "asignado_a" in payload and current_user.role not in ROLES_VEN_TODO:
       raise HTTPException(status_code=403, detail="No autorizado para reasignar casos")
   ```
2. En el UPDATE final, cambiar el WHERE:
   - DE:  `WHERE id = ${idx_id} AND (${idx_id+1} OR cliente_id = ${idx_id+2})`
   - A:   `WHERE id = ${idx_id} AND (${idx_id+1} OR cliente_id = ${idx_id+2}) AND (${idx_id+3} OR asignado_a = ${idx_id+4})`
   y agregar 2 values nuevos al final, EN ORDEN:
   - `current_user.role in ROLES_VEN_TODO`
   - `uuid.UUID(current_user.usuario_id)`
**Verificar:** `python -m py_compile`; el guard 403 existe; el UPDATE tiene `asignado_a = $`.

### Tarea 1.3 — Verificar diff
`git diff` debe mostrar SOLO: WHERE de get_caso_detalle (+2 params), guard 403, WHERE de update_caso (+2 values).
Nada más. CRLF intacto.

## Fase 2 — Validación en staging
Sembrar en `pqrs_staging`: 1 tenant, 2 abogados (A, B) + 1 admin, 2 casos (1 cartera A, 1 cartera B).
Script Python con asyncpg DENTRO de `pqrs_staging_backend`, simulando cada rol (token-equivalente:
pasar role + usuario_id + tenant a la lógica). Matriz de la spec (6 casos). Todos deben pasar.

## Fase 3 — Deploy quirúrgico a prod
1. SSH prod. Backup: `cp casos.py casos.py.bak.20260625d` (preserva C1+A1+A3/A4-previos).
2. `docker cp` del casos.py parcheado (CRLF) → `pqrs_v2_backend:/app/app/api/routes/casos.py`.
3. `docker exec ... python -m py_compile` (compila) + `docker restart pqrs_v2_backend`.
4. Verificar: `curl -sk https://localhost/` → 200; grep del fix presente.
5. Prueba con datos reales (2 abogados reales de Recovery): detalle ajeno → 404; propio → 200; reasignar como abogado → 403.

## Rollback
`cp casos.py.bak.20260625d casos.py` en el contenedor + restart.