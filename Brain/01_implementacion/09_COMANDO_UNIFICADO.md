# Comando Unificado -- FlexPQR

## Arranque Completo

```bash
# 1. Levantar infraestructura
sudo docker compose up -d

# 2. Verificar estado
sudo docker compose ps

# 3. Aplicar migraciones (primera vez)
for f in 01_schema_v2.sql 02_rls_security_v2.sql 03_advanced_features_v2.sql \
         04_multi_tenant_config_v2.sql 05_multi_provider_buzones.sql 08_plantillas_schema.sql; do
  cat $f | docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2
done

# 4. Crear admin (primera vez)
docker exec pqrs_v2_backend python create_admin.py

# 5. Seed de datos demo (opcional)
docker exec pqrs_v2_backend python seed.py
```

## Servicios Disponibles

```
Frontend:      http://localhost:3002
Backend API:   http://localhost:8001
PostgreSQL:    localhost:5434
Redis:         localhost:6381
MinIO API:     http://localhost:9020
MinIO Console: http://localhost:9021
Kafka:         localhost:9093
```

## Comandos Frecuentes

```bash
# Ver logs de un servicio
sudo docker compose logs -f backend_v2
sudo docker compose logs -f master_worker_v2
sudo docker compose logs -f kafka_v2

# Conectar a PostgreSQL
docker exec -it pqrs_v2_db psql -U pqrs_admin -d pqrs_v2

# Conectar a Redis
docker exec -it pqrs_v2_redis redis-cli -a NuSvuOWiQtGWkZleg-zwqUZzs6DewuaK

# Rebuild y restart
sudo docker compose build backend_v2 && sudo docker compose up -d backend_v2
sudo docker compose build frontend_v2 && sudo docker compose up -d frontend_v2

# Parar todo
sudo docker compose down

# Parar todo y borrar datos
sudo docker compose down -v
```

## Script de Despliegue Ubuntu

El archivo `deploy_ubuntu.sh` automatiza la instalacion de Docker y el arranque en un servidor Ubuntu nuevo.
