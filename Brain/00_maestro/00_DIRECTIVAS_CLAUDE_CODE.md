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
