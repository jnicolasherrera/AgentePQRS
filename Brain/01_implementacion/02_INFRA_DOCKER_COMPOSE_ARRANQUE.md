---
tags:
  - brain/implementacion
---

# Infraestructura: Docker Compose y Arranque

## Archivo Principal

`docker-compose.yml` en la raiz del proyecto define 9+ servicios.

## Orden de Arranque

```bash
# 1. Levantar toda la infraestructura
sudo docker compose up -d

# 2. Verificar que todo esta corriendo
sudo docker compose ps

# 3. Ver logs en tiempo real
sudo docker compose logs -f backend_v2
sudo docker compose logs -f master_worker_v2
```

## Servicios y Dependencias

```
postgres_v2 (sin dependencias)
redis_v2 (sin dependencias)
zookeeper_v2 (sin dependencias)
kafka_v2 -> zookeeper_v2
minio_v2 (sin dependencias)
backend_v2 -> postgres_v2, redis_v2, kafka_v2
master_worker_v2 -> postgres_v2, redis_v2, minio_v2
demo_worker_v2 -> postgres_v2, redis_v2
frontend_v2 -> backend_v2
nginx_ssl -> frontend_v2, backend_v2
```

## Health Checks

- **PostgreSQL:** `pg_isready -U pqrs_admin -d pqrs_v2` (interval 10s, 5 retries)
- **MinIO:** `mc ready local` (interval 10s, 5 retries)

## Volumes Persistentes

| Volume        | Contenido                        |
|---------------|----------------------------------|
| pg_data       | Datos de PostgreSQL              |
| redis_data    | Snapshot RDB de Redis            |
| minio_v2_data | Archivos adjuntos del bucket     |

## Comandos Utiles

```bash
# Rebuild un servicio especifico
sudo docker compose build backend_v2
sudo docker compose up -d backend_v2

# Ver logs de un servicio
sudo docker compose logs -f --tail=100 master_worker_v2

# Reiniciar todo
sudo docker compose down && sudo docker compose up -d

# Limpiar todo (DESTRUCTIVO)
sudo docker compose down -v  # Borra volumes
```

## Configuracion de Redis

Redis esta protegido con password: se pasa via `--requirepass` en el command.
Los clientes deben usar la URL con password: `redis://:PASSWORD@redis_v2:6379`


## Referencias

- [[01_INFRA_PREREQUISITOS_LOCAL]]
- [[03_BACKEND_VERIFICACION_SALUD]]
- [[04_FRONTEND_VERIFICACION_CONECTIVIDAD]]
- [[06_INFRA_COLD_START_FIXES]]
