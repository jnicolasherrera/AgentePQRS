# Migracion y Modo God (Super Admin)

## Aplicar Migraciones

Las migraciones son archivos SQL que se aplican en orden numerico:

```bash
# Desde el host, contra el contenedor de PostgreSQL
cat 01_schema_v2.sql | docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2
cat 02_rls_security_v2.sql | docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2
cat 03_advanced_features_v2.sql | docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2
cat 04_multi_tenant_config_v2.sql | docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2
cat 05_multi_provider_buzones.sql | docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2
cat 08_plantillas_schema.sql | docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2
```

## Crear Super Admin

Script `create_admin.py` en la raiz del proyecto crea un usuario super_admin:

```bash
docker exec pqrs_v2_backend python create_admin.py
```

## Modo God (Super Admin)

El rol `super_admin` tiene capacidades especiales:

1. **RLS Bypass:** Cuando `role == 'super_admin'`, el backend ejecuta `set_config('app.is_superuser', 'true', false)` lo que satisface la condicion OR en todas las politicas RLS
2. **Cross-tenant visibility:** Ve casos, usuarios y config de todos los tenants
3. **SSE global:** Se suscribe a `pqrs.events.*` (pattern subscription) para ver todos los eventos
4. **Filtro por cliente_id:** En endpoints de stats y admin, puede pasar `?cliente_id=UUID` para filtrar por tenant especifico

## Rol aequitas_worker

Este rol de PostgreSQL tiene `BYPASSRLS` nativo. Se usa exclusivamente por:
- `worker_ai_consumer.py` para insertar casos clasificados
- `master_worker_outlook.py` para insertar casos desde polling de buzones

La conexion se hace directamente con asyncpg usando `WORKER_DB_URL`, no via el pool del backend.

## Seed de Datos

```bash
# Seed de datos demo
docker exec pqrs_v2_backend python seed.py

# Seed de plantillas Recovery
docker exec pqrs_v2_backend python seed_demo_abogado.py

# Seed de FlexFintech
python seed_flexfintech.py
```
