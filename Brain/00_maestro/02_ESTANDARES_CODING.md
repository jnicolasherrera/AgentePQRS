---
tags:
  - brain/maestro
---

# Estandares de Coding -- FlexPQR

## Python (Backend / Workers)

### Estructura de Archivos
- `backend/app/main.py` -- Punto de entrada FastAPI, routers, lifespan
- `backend/app/core/` -- Config, DB pool, security/JWT, modelos ORM
- `backend/app/api/routes/` -- Routers por dominio (auth, casos, stats, ai, admin, stream, webhooks)
- `backend/app/services/` -- Logica de negocio (clasificador, scoring, kafka, storage, zoho, plantillas)
- `backend/app/enums.py` -- Enums compartidos (TipoCaso, EstadoCaso, Prioridad)

### Convenciones Python
- **Async first:** Todas las funciones de I/O usan `async/await` con asyncpg directo
- **No ORM para queries criticas:** Las queries de rendimiento se escriben en SQL puro via asyncpg
- **Modelos SQLAlchemy:** Solo como referencia de esquema, no como fuente de verdad para DDL
- **Pydantic v2:** Para validacion de request/response bodies
- **Logging:** `logging.getLogger("NOMBRE_MODULO")` con formato estandar
- **Tipo hints:** Obligatorio en funciones publicas
- **Imports:** Absolutos desde `app.core.*` o `app.services.*`

### Seguridad
- Passwords: bcrypt via `bcrypt.hashpw/checkpw`
- JWT: python-jose con HS256, expire configurable (default 480 min)
- Rate limiting: SlowAPI en endpoints sensibles
- HMAC-SHA256: Para validacion de webhooks de Microsoft Graph
- Redis dedup: SETNX con TTL 7 dias para idempotencia de webhooks

## TypeScript (Frontend)

### Estructura de Archivos
- `frontend/src/app/` -- App Router (layout, pages)
- `frontend/src/components/ui/` -- Componentes reutilizables (ReAuthModal, SessionGuardProvider)
- `frontend/src/hooks/` -- Custom hooks (useSessionGuard)
- `frontend/src/lib/` -- Utilidades (api.ts con Axios)
- `frontend/src/store/` -- Estado global (authStore con Zustand)

### Convenciones TypeScript
- **Zustand para estado global:** Con middleware `persist` para auth
- **Axios interceptors:** Auto-attach JWT en requests, dispatch evento en 401
- **Custom events:** `FLEXPQR_SESSION_EXPIRED`, `FLEXPQR_REAUTH_SUCCESS` para flujo de re-auth
- **'use client'** solo en componentes que usan hooks de React
- **Tailwind CSS:** Para estilos, sin CSS modules

## SQL

### Migraciones
- Archivos SQL numerados en la raiz: `01_schema_v2.sql`, `02_rls_security_v2.sql`, etc.
- No se usa Alembic actualmente. Las migraciones se aplican manualmente.
- Fuente de verdad: archivos SQL, no los modelos ORM.

### Convenciones SQL
- UUIDs como primary keys (uuid_generate_v4)
- `created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP`
- `cliente_id UUID NOT NULL REFERENCES clientes_tenant(id) ON DELETE CASCADE` en toda tabla tenant-scoped
- Indices en `cliente_id`, `estado`, `caso_id` para las queries mas frecuentes
- Nombres de tablas y columnas en snake_case espanol


## Referencias

- [[01_ARQUITECTURA_MAESTRA]]
- [[09_EXCELENCIA_INGENIERIA_Y_GIT]]
- [[test_backend_seguridad]]
- [[test_frontend_e2e_playwright]]
