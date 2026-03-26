# Excelencia en Ingenieria y Git -- FlexPQR

## Estrategia de Git

- **Rama principal:** `main`
- **Convencion de ramas:** `feature/`, `hotfix/`, `fix/`
- **Commits recientes siguen el patron:** `tipo(scope): descripcion`
  - Ejemplo: `fix(auth): session expired inline reauth modal with request retry`
  - Ejemplo: `feat: codigo base de produccion FlexPQR`

## Principios de Ingenieria

### 1. Seguridad como Primera Clase
- Todo secreto en variables de entorno, nunca en codigo
- RLS en PostgreSQL para aislamiento de tenants
- HMAC-SHA256 para validacion de webhooks
- bcrypt para hashing de passwords
- Rate limiting en endpoints sensibles (10/min login)
- Redis SETNX para idempotencia de webhooks (TTL 7 dias)

### 2. Resiliencia
- Kafka producer con retry de 5 intentos al inicializar
- AI Classifier con retry exponencial (5 intentos)
- Dead Letter Queue para mensajes irrecuperables
- MinIO ensure_bucket con 3 reintentos
- Zoho token backoff de 90s ante rate limits
- Backend arranca sin Kafka (degrada gracefully)

### 3. Observabilidad
- Logging estructurado con modulos nombrados (MAIN, AI_CONSUMER, KAFKA_PRODUCER, etc.)
- correlation_id end-to-end desde webhook hasta insert en DB
- Audit log inmutable: `logs_auditoria` con delta_antes/delta_despues
- Audit log de respuestas: `audit_log_respuestas` con IP origen y metadata JSON

### 4. Trazabilidad Legal
- Numero de radicado unico por caso (PQRS-YYYY-XXXXXXXX)
- SLA calculado automaticamente por trigger SQL
- Semaforo SLA: VERDE, AMARILLO, ROJO
- Festivos de Colombia en tabla dedicada para calculo de dias habiles
- Acuse de recibo automatico al ciudadano al radicar

### 5. Idempotencia
- Kafka producer con `enable_idempotence=True` y `acks=all`
- Redis dedup de webhooks con `webhook:msgid:{id}`
- Consumer commit manual solo despues de persistencia exitosa o DLQ
