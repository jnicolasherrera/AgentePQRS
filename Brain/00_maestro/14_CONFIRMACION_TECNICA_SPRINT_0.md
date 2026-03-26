# Confirmacion Tecnica Sprint 0 -- FlexPQR

## Verificacion de Infraestructura Base

### PostgreSQL V2
- [x] Pool asyncpg funcional con init/close en lifespan
- [x] RLS habilitado en: usuarios, pqrs_casos, pqrs_adjuntos, pqrs_comentarios, config_buzones
- [x] Variables de sesion: app.current_tenant_id, app.current_user_id, app.current_role, app.is_superuser
- [x] Worker `aequitas_worker` con BYPASSRLS para inserciones cross-tenant
- [x] Triggers: fn_set_fecha_vencimiento, fn_audit_pqrs_casos
- [x] Tabla festivos_colombia para calculo de dias habiles

### Kafka
- [x] Confluent 7.3 con ZooKeeper
- [x] Topic `pqrs.raw.emails` creado automaticamente por producer
- [x] Topic `pqrs.events.dead_letter` para DLQ
- [x] Producer con acks=all, idempotence=true, gzip compression
- [x] Consumer group `aequitas_classifier_group` con commit manual

### Redis
- [x] Redis 7 Alpine con persistencia RDB
- [x] Password habilitado
- [x] PubSub funcional para SSE (canales pqrs.events.{tenant_id})
- [x] Dedup de webhooks con SETNX + TTL 7 dias

### MinIO
- [x] Bucket `pqrs-vault` creado automaticamente
- [x] Upload/download funcional
- [x] Presigned URLs con 2h TTL
- [x] Health check con `mc ready local`

### Backend FastAPI
- [x] Lifespan: init DB pool + init Kafka producer
- [x] CORS configurado para todos los origenes necesarios
- [x] Rate limiting con SlowAPI
- [x] 7 routers montados (auth, stream, stats, casos, ai, admin, webhooks)
- [x] Health check: `GET /` -> `{"status": "ok"}`

### Frontend Next.js
- [x] App Router con layout raiz
- [x] Zustand auth store con persistencia localStorage
- [x] Axios interceptors para JWT auto-attach
- [x] SessionGuardProvider para re-auth inline
- [x] Build optimizado con Dockerfile multi-stage

### Nginx
- [x] SSL/TLS con certificados
- [x] Proxy para frontend, API y SSE
- [x] Security headers (HSTS, X-Frame-Options, etc.)
- [x] SSE con buffering off y timeout 3600s

### Docker Compose
- [x] 9 servicios orquestados con dependencias
- [x] Volumes persistentes para postgres, redis, minio
- [x] Health checks en postgres y minio
- [x] restart: unless-stopped en workers
