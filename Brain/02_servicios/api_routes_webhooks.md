---
tags:
  - brain/api
---

# API Routes: Webhooks

## Archivo
`backend/app/api/routes/webhooks.py`

## Prefijo
`/api/webhooks` (sin /v2/ -- proveedores externos no pasan por auth JWT)

## Descripcion
Endpoints para recibir notificaciones push de proveedores de email (Microsoft Graph, Google Workspace). Validan la firma/token, deduplicacan via Redis y publican a Kafka.

## Endpoints

### GET /webhooks/microsoft-graph
- **Funcion:** Handshake de validacion de Microsoft Graph
- **Parametro:** `validationToken` (query string)
- **Retorna:** El token tal cual en text/plain (requerido por Microsoft)

### POST /webhooks/microsoft-graph
- **Status:** 202 Accepted (responde inmediatamente)
- **Validacion:** HMAC-SHA256 del payload con `MICROSOFT_WEBHOOK_SECRET`
- **Header:** `X-Hub-Signature`
- **Procesamiento:** Background task via FastAPI `BackgroundTasks`

### POST /webhooks/google-workspace
- **Status:** 202 Accepted
- **Validacion:** Header `X-Goog-Channel-Token` contra `GOOGLE_WEBHOOK_TOKEN`
- **Procesamiento:** Background task

## Flujo Interno (_dedup_and_publish)

1. Parsea el payload JSON
2. Itera sobre `data.value[]` (array de notificaciones)
3. Extrae `resourceData.id` como message_id
4. **Idempotencia:** `SETNX webhook:msgid:{message_id}` con TTL 7 dias
   - Si ya existe: descarta (duplicado)
   - Si es nuevo: continua
5. Genera `correlation_id` unico
6. Extrae `tenant_id` de `clientState` de la notificacion
7. Publica a Kafka via `publish_email_event()`

## Seguridad
- HMAC-SHA256 con comparacion en tiempo constante (`hmac.compare_digest`)
- Sin JWT requerido (proveedores externos no autentican con Bearer tokens)
- Redis dedup previene procesamiento duplicado de webhooks reintentados

## Variables de Entorno
- `MICROSOFT_WEBHOOK_SECRET` -- Secreto compartido con Microsoft Graph
- `GOOGLE_WEBHOOK_TOKEN` -- Token de canal para Google Workspace


## Referencias

- [[backend_core]]
- [[service_kafka_producer]]
- [[03_ONBOARDING_INTEGRACIONES]]
