---
tags:
  - brain/test
---

# Tests: Worker IA Consumer

## Archivo del Worker
`backend/worker_ai_consumer.py`

## Puntos Criticos a Testear

### 1. Procesamiento Normal
- Evento valido de Kafka se clasifica correctamente
- Caso se inserta en PostgreSQL con datos correctos
- Notificacion se publica a Redis
- Offset se commitea despues de la insercion

### 2. PoisonPillError
- Despues de 5 reintentos por RateLimitError, el mensaje va a DLQ
- DLQ contiene: original_event, correlation_id, failure_reason, failed_at
- Offset se commitea (no bloquea la particion)

### 3. Error No Manejado
- Excepciones inesperadas van a DLQ
- Error se loguea con traceback completo
- Offset se commitea

### 4. Round Robin de Analistas
- Si hay 3 analistas activos, se distribuyen equitativamente
- Si no hay analistas, asignado_a queda NULL
- Se asigna al analista con menos casos ABIERTOS

### 5. Claim Check Inverso
- Si el evento tiene adjunto_s3_uri, se descarga de MinIO
- Si la descarga falla, la clasificacion continua sin adjunto
- Solo se envian 3000 bytes del adjunto al clasificador

## Mock de Kafka

`backend/mock_kafka.py` permite simular mensajes Kafka para pruebas manuales.

## Test de Integracion

```bash
# Ejecutar el worker en modo test
docker exec pqrs_v2_backend python -c "
import asyncio
from worker_ai_consumer import _process_message
# ... simular mensaje y pool
"
```

## Dependencias a Mockear
- Kafka consumer/producer (aiokafka)
- asyncpg pool
- Redis client
- Anthropic API (para evitar costos en tests)
- MinIO client (para Claim Check)


## Referencias

- [[worker_kafka_consumer]]
- [[service_ai_classifier]]
