---
tags:
  - brain/implementacion
---

# Filtro Global de Tenant -- FlexPQR

## Como Funciona el Aislamiento Multi-Tenant

### Capa 1: JWT Token
Cada token JWT contiene:
```json
{
  "sub": "email@ejemplo.com",
  "tenant_uuid": "uuid-del-tenant",
  "role": "admin|analista|super_admin",
  "usuario_id": "uuid-del-usuario",
  "nombre": "Nombre del usuario"
}
```

### Capa 2: Conexion a DB (get_db_connection)
Antes de ceder la conexion asyncpg al router:
1. Decodifica el JWT del header Authorization
2. Ejecuta `set_config('app.current_tenant_id', tenant_uuid)` en la conexion
3. Ejecuta `set_config('app.current_user_id', usuario_id)` si existe
4. Ejecuta `set_config('app.current_role', role)`
5. Si role == 'super_admin', ejecuta `set_config('app.is_superuser', 'true')`

Al finalizar (bloque finally):
- Resetea todas las variables a '' para evitar contaminacion en pool

### Capa 3: RLS en PostgreSQL
Cada tabla tiene politica RLS:
```sql
USING (
    cliente_id = current_setting('app.current_tenant_id', true)::UUID
    OR current_setting('app.is_superuser', true) = 'true'
)
```

PostgreSQL automaticamente filtra filas que no pertenecen al tenant del usuario logueado.

### Capa 4: Filtros en Codigo (defensa en profundidad)
Ademas de RLS, muchos endpoints verifican explicitamente:
- `current_user.role` para control de acceso por rol
- `current_user.tenant_uuid` para filtros explícitos en super_admin
- analista solo ve casos con `asignado_a = usuario_id`

## Funcion execute_in_rls_context

Para operaciones que necesitan cambiar el contexto RLS temporalmente:
```python
await execute_in_rls_context(conn, tenant_id, role, action_callable)
```

Esto permite a servicios internos ejecutar queries como otro tenant/rol, limpiando las variables al finalizar.

## Super Admin: Vision Global

Cuando un super_admin accede a endpoints con filtro por tenant:
- Sin `?cliente_id`: ve datos de todos los tenants
- Con `?cliente_id=UUID`: ve solo datos de ese tenant
- SSE: suscrito a `pqrs.events.*` via Redis psubscribe
