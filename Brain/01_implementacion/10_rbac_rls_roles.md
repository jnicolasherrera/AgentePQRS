---
tags:
  - brain/implementacion
---

# RBAC, RLS y Roles -- FlexPQR

## Sistema de Control de Acceso

FlexPQR implementa un sistema de seguridad de tres capas: RBAC (Role-Based Access Control) en la aplicacion, RLS (Row-Level Security) en la base de datos, y aislamiento fisico por tenant.

## Roles de Aplicacion

| Rol          | Permisos                                                      |
|--------------|---------------------------------------------------------------|
| super_admin  | Ver todos los tenants, bypass RLS, gestionar clientes         |
| admin        | Gestionar equipo, buzones, ver estadisticas de su tenant      |
| coordinador  | Asignar casos, supervisar analistas de su tenant              |
| analista     | Trabajar casos asignados, editar borradores, enviar respuestas|
| auditor      | Solo lectura para auditoria                                   |
| bot          | Cuenta de servicio para workers automaticos                   |

## Permisos por Endpoint

### Solo admin/super_admin:
- `GET /api/v2/admin/team` -- Listar equipo
- `GET /api/v2/admin/config/buzones` -- Configuracion de buzones
- `GET /api/v2/admin/clientes` -- Listar tenants
- `POST /api/v2/admin/casos/{id}/feedback` -- Feedback de clasificacion
- `GET /api/v2/stats/rendimiento` -- Rendimiento de abogados

### analista + admin + super_admin:
- `GET /api/v2/casos/enviados/historial` -- Historial de envios
- `GET /api/v2/stats/dashboard` -- Dashboard (analista ve solo sus casos)

### Cualquier usuario autenticado:
- `PUT /api/v2/admin/me/nombre` -- Cambiar nombre propio
- `POST /api/v2/admin/me/password` -- Cambiar password propio
- `GET /api/v2/casos/{id}` -- Detalle de caso (filtrado por RLS)
- `GET /api/v2/stream/listen` -- SSE (filtrado por rol)

## RLS Variables de Sesion

```sql
-- Se setean en cada conexion via get_db_connection()
app.current_tenant_id  -- UUID del tenant del usuario
app.current_user_id    -- UUID del usuario
app.current_role       -- Rol del usuario
app.is_superuser       -- 'true' solo para super_admin
```

## Roles de PostgreSQL

| Rol DB           | Privilegios | Usado por                    |
|------------------|-------------|------------------------------|
| pqrs_admin       | OWNER       | Backend FastAPI (via pool)   |
| aequitas_worker  | BYPASSRLS   | Workers Kafka, master_worker |
