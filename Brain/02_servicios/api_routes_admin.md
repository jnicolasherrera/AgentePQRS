---
tags:
  - brain/api
---

# API Routes: Admin

## Archivo
`backend/app/api/routes/admin.py`

## Prefijo
`/api/v2/admin`

## Descripcion
Endpoints de administracion: gestion de equipo, configuracion de buzones, listado de casos avanzado con filtros, feedback de clasificacion IA, y listado de clientes (tenants).

## Endpoints

### PUT /me/nombre
- **Acceso:** Cualquier usuario autenticado
- **Funcion:** Actualiza el nombre del usuario logueado
- **Body:** `{ "nombre": "string" }`

### POST /me/password
- **Acceso:** Cualquier usuario autenticado
- **Funcion:** Cambia la password del usuario logueado
- **Validaciones:** Verifica password actual con bcrypt, nueva password >= 8 chars
- **Body:** `{ "current_password": "string", "new_password": "string" }`

### GET /team
- **Acceso:** Solo admin / super_admin
- **Funcion:** Lista los analistas del tenant
- **Retorna:** id, nombre, email, rol, is_active, created_at

### GET /config/buzones
- **Acceso:** Solo admin / super_admin
- **Funcion:** Lista los buzones configurados del tenant
- **Retorna:** email_buzon, proveedor, is_active

### GET /casos
- **Acceso:** Solo admin / super_admin
- **Funcion:** Listado paginado de casos con filtros avanzados
- **Parametros:** page, page_size, tipo, estado, asignado_a, es_pqrs, q (busqueda texto), sort_by, sort_dir, cliente_id (super_admin)
- **Ordenamiento soportado:** radicado, asunto, tipo, estado, prioridad, recibido, vencimiento, asignado
- **Join:** LEFT JOIN usuarios para nombre del asignado

### POST /casos/{caso_id}/feedback
- **Acceso:** Solo admin / super_admin
- **Funcion:** Marca feedback de clasificacion IA (es_pqrs, clasificacion_correcta)
- **Efecto:** Actualiza `es_pqrs` en el caso e inserta en `pqrs_clasificacion_feedback`
- **Retorna:** Conteo de correcciones acumuladas del tenant

### GET /clientes
- **Acceso:** Solo admin / super_admin
- **Funcion:** Lista todos los tenants registrados
- **super_admin:** Ve todos los tenants
- **admin:** Ve solo su tenant
