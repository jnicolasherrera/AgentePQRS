# Migraciones SQL

## Estrategia de Migracion

FlexPQR usa archivos SQL numerados en la raiz del proyecto, aplicados manualmente. No se usa Alembic ni otro framework de migraciones actualmente.

## Archivos de Migracion

| # | Archivo                          | Contenido                                          |
|---|----------------------------------|-----------------------------------------------------|
| 1 | 01_schema_v2.sql                 | Tablas base: clientes_tenant, usuarios, pqrs_casos + indices |
| 2 | 02_rls_security_v2.sql           | RLS en usuarios y pqrs_casos con FORCE                |
| 3 | 03_advanced_features_v2.sql      | pqrs_adjuntos, pqrs_comentarios + RLS + cliente_id    |
| 4 | 04_multi_tenant_config_v2.sql    | config_buzones, super_admin bypass, seed inicial       |
| 5 | 05_multi_provider_buzones.sql    | Campo proveedor (OUTLOOK/ZOHO) en config_buzones      |
| 6 | 08_plantillas_schema.sql         | Tabla plantillas_respuesta                            |

## Aplicar Migraciones

```bash
# Contra el contenedor de PostgreSQL
for f in 01_schema_v2.sql 02_rls_security_v2.sql 03_advanced_features_v2.sql \
         04_multi_tenant_config_v2.sql 05_multi_provider_buzones.sql 08_plantillas_schema.sql; do
  cat $f | docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2
done
```

## Seed Scripts

| Script                          | Descripcion                                  |
|---------------------------------|----------------------------------------------|
| create_admin.py                 | Crea usuario super_admin                     |
| seed.py                         | Seed de datos demo basicos                   |
| seed_demo_abogado.py            | Seed de datos para demo de abogados          |
| seed_flexfintech.py             | Seed de tenant FlexFintech                   |
| seed_historical_v2.py           | Seed de datos historicos                     |
| 09_seed_plantillas_recovery.py  | Seed de plantillas Recovery en la BD         |
| scripts/seed_historical_recovery.py | Seed historico para Recovery              |

## Convencion para Nuevas Migraciones

1. Nombrar con numero secuencial: `XX_descripcion.sql`
2. Usar `CREATE TABLE IF NOT EXISTS` e `IF NOT EXISTS` en indices
3. Incluir RLS si la tabla tiene `cliente_id`
4. Incluir politica con bypass para super_admin
5. Agregar la tabla al modelo ORM en `backend/app/core/models.py` como referencia
