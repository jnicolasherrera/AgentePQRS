---
tags:
  - brain/maestro
---

# Directivas Claude Code -- FlexPQR / Aequitas

## Identidad del Proyecto

- **Nombre comercial:** FlexPQR (antes Aequitas)
- **Dominio:** flexpqr.com (landing), app.flexpqr.com (dashboard)
- **Proposito:** Plataforma enterprise SaaS multi-tenant para gestion de PQRS (Peticiones, Quejas, Reclamos, Solicitudes) y Tutelas bajo normativa colombiana.

## Reglas de Oro

1. **Nunca exponer secretos.** Toda credencial vive en variables de entorno o docker-compose env. Jamas hardcodear API keys, passwords ni tokens en el codigo fuente.
2. **Multitenancy es innegociable.** Toda query a PostgreSQL debe pasar por Row-Level Security (RLS). El `cliente_id` del JWT se inyecta en `app.current_tenant_id` antes de cada conexion.
3. **Arquitectura Event-Driven.** Los emails entrantes no se procesan sincrono. Se encolan a Kafka (`pqrs.raw.emails`) y los workers los clasifican en background.
4. **Clasificacion hibrida.** Primero keywords + scoring engine (rapido, gratis). Si confianza < 0.70, escalar a Claude Haiku via Anthropic API.
5. **Dead Letter Queue obligatoria.** Todo consumer Kafka debe enviar mensajes irrecuperables a `pqrs.events.dead_letter`, nunca bloquear la particion.
6. **SLA Legal Colombiano.** Los plazos (TUTELA=2 dias habiles, PETICION=15, etc.) se calculan automaticamente con triggers de PostgreSQL y tabla de festivos.
7. **Idioma del codigo:** Python (backend/workers), TypeScript (frontend). Comentarios y variables de negocio en espanol. Logs y docstrings pueden ser en espanol.
8. **Branch strategy:** main es la rama principal. Ramas feature/hotfix se crean desde main.

## Stack Tecnologico

| Capa          | Tecnologia                          |
|---------------|-------------------------------------|
| Frontend      | Next.js 14 + TypeScript + Tailwind  |
| Backend API   | FastAPI + asyncpg + Pydantic        |
| Base de datos | PostgreSQL 15 con RLS               |
| Cache/PubSub  | Redis 7                             |
| Message Broker| Apache Kafka (Confluent 7.3)        |
| Storage       | MinIO (S3-compatible)               |
| IA            | Anthropic Claude (Haiku)            |
| Proxy         | Nginx con SSL/TLS                   |
| Contenedores  | Docker Compose                      |

## Roles del Sistema

- `super_admin` -- Ve todos los tenants, bypass RLS via `app.is_superuser`
- `admin` -- Administrador de un tenant especifico
- `coordinador` -- Coordinador de equipo dentro del tenant
- `analista` -- Abogado/analista que trabaja los casos
- `auditor` -- Solo lectura para auditoria
- `bot` -- Cuenta de servicio para workers automaticos


## Deploy en Produccion (18.228.54.9)

```bash
# Conectar al servidor
ssh -i ~/.ssh/flexpqr-prod.pem ubuntu@18.228.54.9
cd ~/PQRS_V2

# Pull de cambios
git pull origin develop

# Levantar con rebuild — backend y workers
docker compose up -d --build backend_v2
docker compose up -d --build master_worker_v2

# FRONTEND — procedimiento especial obligatorio
# docker compose up --build NO funciona para el frontend porque los volumenes
# de desarrollo (bind mount ./frontend:/app + anonymous volume /app/.next)
# sobrescriben el .next del Dockerfile.
# SIEMPRE usar este procedimiento para deployar cambios de frontend:
docker exec pqrs_v2_frontend sh -c 'cd /app && npm run build'
docker compose restart frontend_v2
# Verificar que levanto correctamente:
docker logs pqrs_v2_frontend --tail=20

# Backup de base de datos (antes de cualquier cambio en DB)
docker exec pqrs_v2_db pg_dump -U pqrs_admin -d pqrs_v2 -F c -f /tmp/backup_$(date +%Y%m%d_%H%M).dump
docker cp pqrs_v2_db:/tmp/backup_*.dump ~/backups/
```

## Lecciones Aprendidas

### Frontend — Volumenes de desarrollo bloquean rebuild (27/03/2026)
**Sintoma:** Cambios de codigo en el frontend no se reflejan en produccion
despues de `docker compose up -d --build frontend_v2`.
**Causa raiz:** El docker-compose.yml tiene bind mounts de desarrollo:
- `./frontend:/app` — sobrescribe el /app del image con los archivos del host
- `/app/.next` — volumen anonimo persiste el .next viejo entre rebuilds

El build del Dockerfile genera el .next correcto, pero el volumen anonimo
lo reemplaza al iniciar el contenedor.
**Fix operativo:** Buildear dentro del contenedor corriendo:
```bash
docker exec pqrs_v2_frontend sh -c 'cd /app && npm run build'
docker compose restart frontend_v2
```
**Fix definitivo pendiente:** Crear un docker-compose.prod.yml sin los volumenes
de desarrollo y usar `docker compose -f docker-compose.prod.yml up -d --build`.

## Referencias

- [[01_ARQUITECTURA_MAESTRA]]
- [[09_EXCELENCIA_INGENIERIA_Y_GIT]]
- [[13_EQUIPOS_DE_AGENTES_Y_ORQUESTACION]]
