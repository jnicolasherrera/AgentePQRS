# Backend: Verificacion de Salud

## Endpoint de Health Check

```
GET / -> {"status": "ok", "message": "FlexPQR API esta VIVO."}
```

## Verificacion Manual

```bash
# Desde el host
curl http://localhost:8001/
curl http://localhost:8001/api/v2/auth/login -X POST \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"test"}'

# Desde dentro de Docker
docker exec pqrs_v2_backend curl http://localhost:8000/
```

## Que Hace el Backend al Arrancar (Lifespan)

1. `init_db_pool()` -- Crea pool de conexiones asyncpg a PostgreSQL
2. `init_kafka_producer()` -- Conecta producer a Kafka (con 5 reintentos, 5s entre cada uno)
   - Si Kafka no esta disponible, el backend arranca de todas formas con un warning
3. Al apagar: `close_kafka_producer()` + `close_db_pool()`

## Routers Montados

| Prefijo              | Modulo   | Descripcion                         |
|----------------------|----------|-------------------------------------|
| /api/v2/auth         | auth     | Login, change-password              |
| /api/v2/stream       | stream   | SSE listen                          |
| /api/v2/stats        | stats    | Dashboard, rendimiento, tendencias  |
| /api/v2/casos        | casos    | CRUD casos, borradores, lote envio  |
| /api/v2/ai           | ai       | Extraccion IA, generacion drafts    |
| /api/v2/admin        | admin    | Team, buzones, feedback, clientes   |
| /api/webhooks        | webhooks | Microsoft Graph, Google Workspace   |

## Middleware

- **CORS:** Origenes permitidos configurados en main.py
- **Rate Limiting:** SlowAPI con `get_remote_address` como key
- **Error Handler:** `_rate_limit_exceeded_handler` para 429

## Senales de Problema

- Log `"Error al conectar al Pool PQRS V2"` -> PostgreSQL no esta arriba
- Log `"Kafka no disponible"` -> Kafka no arranco o ZooKeeper fallo
- HTTP 500 `"Database Pool no inicializado"` -> Pool fallo al iniciar
