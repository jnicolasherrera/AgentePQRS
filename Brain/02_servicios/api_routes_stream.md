# API Routes: Stream (SSE)

## Archivo
`backend/app/api/routes/stream.py`

## Prefijo
`/api/v2/stream`

## Descripcion
Server-Sent Events (SSE) para notificaciones en tiempo real de nuevos casos PQRS. Usa Redis PubSub como canal de comunicacion entre workers y frontend.

## Endpoints

### GET /listen
- **Acceso:** Requiere token JWT como query parameter (`?token=...`)
- **Nota:** SSE no soporta headers custom, por eso el token va como query param
- **Retorna:** `EventSourceResponse` con streaming indefinido

## Funcionamiento

### Suscripcion por Rol
- **super_admin:** Se suscribe con `psubscribe("pqrs.events.*")` -- ve TODOS los tenants
- **admin/coordinador:** Se suscribe a `pqrs.events.{tenant_id}` -- solo su tenant
- **analista:** Se suscribe al canal del tenant pero filtra por `asignado_a == user_id`

### Eventos Emitidos
```
event: new_pqr
data: {"tipo":"nuevo_caso","caso_id":"uuid","correlation_id":"uuid","tipo_caso":"TUTELA","prioridad":"CRITICA","tenant_id":"uuid"}
```

### Keepalive
- Cada 30 segundos envia un evento `ping` vacio
- Evita que Nginx/Cloudflare/proxies cierren la conexion idle

### Redis Canales
- **Pattern:** `pqrs.events.{tenant_id}` (un canal por tenant)
- **Publisher:** `worker_ai_consumer.py` despues de insertar un caso
- **Subscriber:** Este endpoint SSE

## Configuracion Nginx para SSE

```nginx
location /api/v2/stream/ {
    proxy_pass http://pqrs_v2_backend:8000/api/v2/stream/;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 3600s;
    proxy_http_version 1.1;
    proxy_set_header Connection '';
    chunked_transfer_encoding on;
}
```

## Dependencias
- `sse-starlette` -- Libreria para SSE en FastAPI/Starlette
- `redis.asyncio` -- Cliente Redis asincrono
- `app.core.security.decode_access_token` -- Decodifica JWT sin Depends
