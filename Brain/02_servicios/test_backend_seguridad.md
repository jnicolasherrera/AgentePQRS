# Tests: Backend Seguridad

## Archivos de Test

| Archivo                    | Descripcion                                     |
|----------------------------|-------------------------------------------------|
| backend/test_rls_hierarchy.py | Tests de aislamiento RLS entre tenants       |
| backend/test_schema.py     | Tests de validacion de esquema                   |
| backend/test_query.py      | Tests de queries basicos                         |
| backend/test_ai_drafts.py  | Tests de generacion de borradores IA             |
| backend/test_analyze_all.py| Tests del clasificador completo                  |
| backend/test_v1_v2_integration.py | Tests de integracion V1/V2               |
| backend/tests/             | Directorio de tests adicionales                  |

## Configuracion

`backend/pytest.ini` contiene la configuracion de pytest.

## Puntos Criticos de Seguridad a Testear

### 1. Aislamiento de Tenant (RLS)
- Un usuario de Tenant A NO puede ver casos de Tenant B
- `get_db_connection()` setea correctamente `app.current_tenant_id`
- Las variables se limpian en el finally

### 2. Control de Acceso por Rol
- Endpoints de admin rechazan con 403 si el rol no es admin/super_admin
- Analista solo ve sus casos asignados en SSE
- Super admin puede ver todos los tenants

### 3. Autenticacion
- Token expirado retorna 401
- Token invalido retorna 401
- Rate limiting de login (10/min) funciona

### 4. Webhooks
- HMAC invalido retorna 403 en Microsoft Graph
- Token invalido retorna 403 en Google Workspace
- Mensajes duplicados se descartan (Redis dedup)

### 5. Aprobacion de Lote
- Password incorrecta retorna 401
- Maximo 10 casos por lote (400 si se excede)

## Test de RLS Hierarchy

`test_rls_hierarchy.py` verifica:
- Creacion de tenants independientes
- Insercion de casos por tenant
- Aislamiento: queries desde un tenant no ven datos del otro
- Super admin bypass funciona


## Referencias

- [[backend_core]]
- [[02_ESTANDARES_CODING]]
