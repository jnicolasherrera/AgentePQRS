---
tags:
  - brain/api
---

# Backend Core

## Archivos

### backend/app/core/config.py
- Clase `Settings` con Pydantic BaseSettings
- Carga automatica desde `.env`
- **Variables:** database_url, redis_url, jwt_secret_key, jwt_algorithm, access_token_expire_minutes (480), anthropic_api_key, kafka_bootstrap_servers, microsoft_webhook_secret, google_webhook_token
- **Business rules:** `PLAZOS_DIAS_HABILES` y `PRIORIDADES` como diccionarios constantes

### backend/app/core/db.py
- Pool asyncpg con init/close en lifespan
- `get_db_connection()` -- Dependency de FastAPI que:
  1. Decodifica JWT del header
  2. Setea variables RLS en la conexion PostgreSQL
  3. Cede la conexion al endpoint
  4. Limpia variables en el finally
- `execute_in_rls_context()` -- Ejecuta una accion con un contexto RLS especifico
- `get_raw_pool()` -- Acceso directo al pool para operaciones internas

### backend/app/core/security.py
- `verify_password()` -- bcrypt check
- `get_password_hash()` -- bcrypt hash
- `create_access_token()` -- JWT con claims de tenant, rol, usuario
- `decode_access_token()` -- Decodifica y valida JWT
- `get_current_user()` -- Dependency de FastAPI que retorna `UserInToken`
- **UserInToken:** email, tenant_uuid, role, nombre, usuario_id

### backend/app/core/models.py
- Modelos SQLAlchemy 2.0 como referencia de esquema (NO fuente de verdad para DDL)
- Modelos: ClienteTenant, Usuario, PqrsCaso, PqrsAdjunto, PqrsComentario, ConfigBuzon, PlantillaRespuesta, AuditLogRespuesta, LogAuditoria, FestivosColombia
- Constraints: CheckConstraint para roles validos, semaforo_sla, accion de auditoria

### backend/app/enums.py
- `TipoCaso`: TUTELA, PETICION, QUEJA, RECLAMO, SOLICITUD, CONSULTA, FELICITACION
- `EstadoCaso`: NUEVO, EN_PROCESO, PENDIENTE_INFO, RESPONDIDO, CERRADO, VENCIDO
- `Prioridad`: CRITICA, ALTA, MEDIA, BAJA

### backend/app/main.py
- FastAPI app con lifespan (init pool + Kafka producer)
- CORS middleware
- SlowAPI rate limiting
- 7 routers montados
- Health check en `GET /`


## Referencias

- [[01_ARQUITECTURA_MAESTRA]]
- [[api_routes_casos]]
- [[api_routes_admin]]
- [[api_routes_stream]]
- [[api_routes_ai]]
- [[api_routes_webhooks]]
