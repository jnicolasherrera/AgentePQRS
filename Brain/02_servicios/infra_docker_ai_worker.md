---
tags:
  - brain/infra
---

# Infraestructura: Docker AI Worker

## Archivo
`backend/worker_ai_consumer.py`

## Servicio Docker
No tiene servicio dedicado en docker-compose actualmente. El consumer se puede ejecutar como:
```bash
docker exec pqrs_v2_backend python worker_ai_consumer.py
```

## Descripcion
Worker perpetuo que consume mensajes de Kafka (`pqrs.raw.emails`), clasifica con IA y persiste en PostgreSQL. Es el corazon del pipeline de procesamiento.

## Configuracion

| Variable              | Default                                                  |
|-----------------------|----------------------------------------------------------|
| WORKER_DB_URL         | postgresql://aequitas_worker:changeme_worker@postgres_v2:5432/pqrs_v2 |
| KAFKA_BOOTSTRAP       | kafka_v2:29092                                           |
| REDIS_URL             | redis://redis_v2:6379                                    |

## Flujo de Procesamiento

```
Kafka (pqrs.raw.emails)
  -> Deserializar JSON
  -> classify_email_event() [AI Classifier con retry exponencial]
  -> insert_pqrs_caso() [DB Inserter con round-robin de analistas]
  -> Redis publish (pqrs.events.{tenant_id}) [SSE notification]
  -> Kafka commit offset
```

## Manejo de Errores

### PoisonPillError
- Lanzado cuando classify_email_event agota sus 5 reintentos
- Se envia el mensaje a `pqrs.events.dead_letter` (DLQ)
- Se commitea el offset para no bloquear la particion

### Error No Manejado
- Cualquier otra excepcion
- Tambien va a DLQ con razon "UnhandledError"
- Se commitea el offset

### Commit Strategy
- `enable_auto_commit=False` -- Commit manual
- Commit SIEMPRE despues de cada mensaje: exito o DLQ
- Nunca se bloquea la particion

## Consumer Group
- Group ID: `aequitas_classifier_group`
- Auto offset reset: `earliest`

## Conexiones
- asyncpg Pool: min_size=2, max_size=10 (aequitas_worker con BYPASSRLS)
- AIOKafkaConsumer + AIOKafkaProducer (para DLQ)
- Redis async para publish de notificaciones


## Referencias

- [[infra_docker_kafka_cluster]]
- [[worker_kafka_consumer]]
- [[service_ai_classifier]]
