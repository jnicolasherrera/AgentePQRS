# Fixes de Producto — Abril 2026

## Fix 1: RBAC Tab Enviados — analista ve solo sus propios envíos (8 abril 2026)

### Problema
El endpoint GET /enviados/historial devolvía todos los enviados del tenant
sin filtrar por usuario. El rol analista/abogado veía los envíos de todos.

### Causa raíz
La query filtraba solo por `c.cliente_id` (tenant) pero no por `a.usuario_id`.

### Fix aplicado
**Archivo**: `backend/app/api/routes/casos.py`

Lógica implementada:
```python
ROLES_VEN_TODO = {"admin", "coordinador", "super_admin", "auditor"}

# admin/coordinador/super_admin/auditor → ven todos los enviados del tenant
# analista/abogado → ven solo WHERE a.usuario_id = su propio UUID
```

Campo usado: `current_user.usuario_id` (Optional[str] en UserInToken)

### Archivos modificados
- `backend/app/api/routes/casos.py`
- `frontend/src/components/ui/enviados-tab.tsx` (estado vacío descriptivo)
- `frontend/src/components/ui/firma-modal.tsx` (toast resultado envío)

### Toast de resultado de envío
- **Componente**: `firma-modal.tsx`
- Verde (`bg-emerald-500/90`): envío exitoso con cantidad de respuestas
- Rojo (`bg-red-500/90`): error con mensaje descriptivo
- Auto-dismiss: 6 segundos
- Posición: fixed bottom-6 right-6 z-50

### Verificación en producción
- `smena@arcsas.com.co` (rol abogado): ve sus 3 envíos propios
- `plombana@arcsas.com.co` (rol admin): ve todos los del tenant

---

## Fix 2: Round-robin asignación — incluir rol abogado (8 abril 2026)

### Problema
61 casos llegaron sin asignar (`asignado_a = NULL`) en arcsas.com.co.
Los analistas no los veían.

### Causa raíz
La query de round-robin en `master_worker_outlook.py` línea 235 filtraba:
```sql
AND u.rol = 'analista'
```
El tenant arcsas.com.co (Abogados Recovery) usa `rol='abogado'` (legacy V1).
La query no encontraba analistas → `asignado_a` quedaba NULL.

### Fix aplicado
**Archivo**: `backend/master_worker_outlook.py` (línea 235)
```sql
-- Antes:
AND u.rol = 'analista'
-- Después:
AND u.rol IN ('analista', 'abogado')
```

### Acción retroactiva
59 casos reasignados con query round-robin en producción.
Distribución final:
| Abogado | Casos |
|---------|-------|
| smena | 16 |
| jvillalba | 12 |
| dpenaranda | 11 |
| kgomez | 11 |
| jpalacio | 10 |
| jburitica | 10 |

### Estado post-fix
- Casos sin asignar en producción: **0**
- Worker procesando normalmente

### Lección aprendida
**SIEMPRE** incluir `rol='abogado'` junto a `rol='analista'` en cualquier query
que filtre por rol de operador. El tenant Recovery usa el rol legacy
y seguirá usándolo hasta migración formal.

---

## Fix 3: Eliminación de correos — FK constraint (8 abril 2026)

### Problema
Al confirmar eliminación de casos desde la bandeja, el backend devolvía error
silencioso. El modal se cerraba pero los casos no se borraban.

### Causa raíz
```
asyncpg.exceptions.ForeignKeyViolationError: update or delete on table "pqrs_casos"
violates foreign key constraint "audit_log_respuestas_caso_id_fkey"
```
Las tablas hijas tienen FK hacia `pqrs_casos` sin CASCADE.

### Fix aplicado
En los 3 endpoints de DELETE (`admin.py`), se eliminan registros hijos primero:
```python
await conn.execute("DELETE FROM pqrs_adjuntos WHERE caso_id = ANY($1::uuid[])", uuids)
await conn.execute("DELETE FROM pqrs_comentarios WHERE caso_id = ANY($1::uuid[])", uuids)
await conn.execute("DELETE FROM audit_log_respuestas WHERE caso_id = ANY($1::uuid[])", uuids)
await conn.execute("DELETE FROM pqrs_clasificacion_feedback WHERE caso_id = ANY($1::uuid[])", uuids)
await conn.execute("DELETE FROM pqrs_casos WHERE id = ANY($1::uuid[])...", uuids)
```

### Tablas con FK hacia pqrs_casos
1. `pqrs_adjuntos` (caso_id)
2. `pqrs_comentarios` (caso_id)
3. `audit_log_respuestas` (caso_id)
4. `pqrs_clasificacion_feedback` (caso_id)

---

## Fix 4: Password reset producción (8 abril 2026)

### Acción
Reset de contraseña para `nicolas.herrera@flexfintech.com` en producción.
```sql
UPDATE usuarios SET password_hash = crypt('Armando2026!', gen_salt('bf', 12)),
debe_cambiar_password = false, updated_at = NOW()
WHERE email = 'nicolas.herrera@flexfintech.com';
```
