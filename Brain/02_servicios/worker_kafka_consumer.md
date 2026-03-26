---
tags:
  - brain/worker
---

# Worker: Kafka Consumer (AI Consumer)

## Archivo
`backend/worker_ai_consumer.py`

## Descripcion
Worker perpetuo que consume mensajes del topic `pqrs.raw.emails` en Kafka, los clasifica con IA y los persiste en PostgreSQL. Es el nucleo del pipeline de procesamiento asincrono.

## Configuracion

| Variable              | Default                                           |
|-----------------------|---------------------------------------------------|
| WORKER_DB_URL         | postgresql://aequitas_worker:changeme_worker@postgres_v2:5432/pqrs_v2 |
| KAFKA_BOOTSTRAP       | kafka_v2:29092                                    |
| REDIS_URL             | redis://redis_v2:6379                             |

## Componentes

### Consumer
- Topic: `pqrs.raw.emails`
- Group: `aequitas_classifier_group`
- Auto commit: FALSE (manual)
- Offset reset: `earliest`

### Producer (para DLQ)
- Topic: `pqrs.events.dead_letter`
- acks=all, idempotence=true

### Pool asyncpg
- Min 2, max 10 conexiones
- Rol: aequitas_worker (BYPASSRLS)

### Redis
- Para publicar notificaciones a SSE

## Flujo por Mensaje

```
1. Deserializar JSON del mensaje Kafka
2. classify_email_event(event) -> ClassificationResult
   - Clasificacion hibrida con retry exponencial
3. insert_pqrs_caso(event, result, pool) -> caso_id
   - Insercion con round-robin de analistas
4. Redis PUBLISH pqrs.events.{tenant_id}
   - Notificacion SSE al frontend
5. Consumer COMMIT offset
```

## Manejo de Errores

### PoisonPillError
- Clasificacion fallo despues de 5 reintentos
- Mensaje va a DLQ con: original_event, correlation_id, failure_reason, failed_at
- Offset se commitea para no bloquear

### Exception generica
- Cualquier error inesperado
- Tambien va a DLQ
- Se loguea con exc_info=True

### Commit siempre
- `await consumer.commit()` se ejecuta DESPUES de cada mensaje
- Tanto en exito como en DLQ
- Nunca bloquea la particion

## Ciclo de Vida

```
main():
  1. Crear pool asyncpg
  2. Conectar Redis
  3. Crear Kafka producer (DLQ)
  4. Crear Kafka consumer
  5. Loop infinito: async for msg in consumer

  finally:
    consumer.stop()
    producer.stop()
    pool.close()
    redis.aclose()
```

## Ejecucion

```bash
# Como contenedor Docker
docker compose run backend_v2 python worker_ai_consumer.py

# O dentro del contenedor
docker exec pqrs_v2_backend python worker_ai_consumer.py
```


## Referencias

- [[service_ai_classifier]]
- [[worker_db_inserter]]
- [[infra_docker_kafka_cluster]]
