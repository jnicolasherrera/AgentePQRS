#!/bin/bash
# Inicializar la base de datos de staging con schema + datos base
# Ejecutar desde la raiz del repo en el servidor:
#   bash scripts/init_staging_db.sh

set -e

echo "Esperando que PostgreSQL staging este listo..."
until docker exec pqrs_staging_db pg_isready -U pqrs_admin -d pqrs_staging 2>/dev/null; do
  sleep 2
done
echo "PostgreSQL staging listo."

echo "Aplicando schema..."
docker cp 01_schema_v2.sql pqrs_staging_db:/tmp/01_schema_v2.sql
docker exec pqrs_staging_db psql -U pqrs_admin -d pqrs_staging -f /tmp/01_schema_v2.sql

echo "Aplicando RLS..."
docker cp 02_rls_security_v2.sql pqrs_staging_db:/tmp/02_rls_security_v2.sql
docker exec pqrs_staging_db psql -U pqrs_admin -d pqrs_staging -f /tmp/02_rls_security_v2.sql

# Aplicar schemas adicionales si existen
for f in 03_advanced_features_v2.sql 04_multi_tenant_config_v2.sql 05_multi_provider_buzones.sql 08_plantillas_schema.sql; do
  if [ -f "$f" ]; then
    echo "Aplicando $f..."
    docker cp "$f" pqrs_staging_db:/tmp/"$f"
    docker exec pqrs_staging_db psql -U pqrs_admin -d pqrs_staging -f /tmp/"$f" 2>/dev/null || true
  fi
done

echo "Creando admin de staging..."
docker exec pqrs_staging_db psql -U pqrs_admin -d pqrs_staging -c "
INSERT INTO clientes_tenant (id, nombre, dominio, is_active)
VALUES ('11111111-1111-1111-1111-111111111111', 'Staging FlexPQR', 'staging.flexpqr.com', TRUE)
ON CONFLICT (id) DO NOTHING;
"

# Crear usuario admin con password Staging2026!
docker cp scripts/seed_demo_data.py pqrs_staging_backend:/tmp/seed_demo_data.py 2>/dev/null || true
docker exec pqrs_staging_backend python3 -c "
import bcrypt, asyncio, asyncpg, os, uuid
async def main():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    h = bcrypt.hashpw(b'Staging2026!', bcrypt.gensalt()).decode()
    await conn.execute('''
        INSERT INTO usuarios (id, cliente_id, email, password_hash, nombre, rol, is_active, debe_cambiar_password)
        VALUES (\$1, \$2, \$3, \$4, \$5, \$6, TRUE, FALSE)
        ON CONFLICT (email) DO UPDATE SET password_hash = \$4
    ''', uuid.UUID('aaaa0000-0000-0000-0000-000000000000'),
        uuid.UUID('11111111-1111-1111-1111-111111111111'),
        'admin@staging.flexpqr.com', h, 'Admin Staging', 'super_admin')
    print('Admin staging creado: admin@staging.flexpqr.com / Staging2026!')
    await conn.close()
asyncio.run(main())
"

echo ""
echo "========================================="
echo "  STAGING INICIALIZADO"
echo "========================================="
echo "  DB:       pqrs_staging (puerto 5435)"
echo "  Backend:  http://18.228.54.9:8002"
echo "  Frontend: http://18.228.54.9:3003"
echo "  Admin:    admin@staging.flexpqr.com / Staging2026!"
echo "========================================="
