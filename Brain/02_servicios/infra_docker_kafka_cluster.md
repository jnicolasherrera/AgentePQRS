---
tags:
  - brain/infra
---

# Infraestructura: Docker Kafka Cluster

## Servicios

### ZooKeeper
- **Imagen:** confluentinc/cp-zookeeper:7.3.0
- **Puerto host:** 2182 -> 2181 container
- **Config:** ZOOKEEPER_CLIENT_PORT=2181, TICK_TIME=2000

### Kafka
- **Imagen:** confluentinc/cp-kafka:7.3.0
- **Puerto host:** 9093 -> 9092 container
- **Depende de:** zookeeper_v2
- **Listeners:**
  - PLAINTEXT://kafka_v2:29092 (intra-docker, para backend/workers)
  - PLAINTEXT_HOST://localhost:9092 (acceso desde host)
- **Config:** BROKER_ID=1, REPLICATION_FACTOR=1 (single-node)

## Topics

| Topic                      | Uso                                    | Particiones |
|----------------------------|----------------------------------------|-------------|
| pqrs.raw.emails            | Emails crudos para clasificar          | Auto        |
| pqrs.events.dead_letter    | Mensajes irrecuperables (DLQ)          | Auto        |

## Producer (backend)

**Archivo:** `backend/app/services/kafka_producer.py`

- Se inicializa en el lifespan del backend
- **Garantias:** acks=all, idempotence=true
- **Compresion:** gzip
- **Serializer:** JSON con `default=str`
- **Partitioning:** key=tenant_id.encode("utf-8") (orden por tenant)
- **Retry al inicializar:** 5 intentos con 5s entre cada uno
- **Claim Check:** Adjuntos > 1MB se suben a MinIO; solo URI en el mensaje

## Consumer (worker)

**Archivo:** `backend/worker_ai_consumer.py`

- **Group:** aequitas_classifier_group
- **Auto commit:** False (manual despues de procesamiento)
- **Offset reset:** earliest
- **Deserializer:** raw bytes (deserializacion manual en _process_message)

## Monitoreo

Actualmente no hay Kafka UI/monitor configurado. Planificado: mcp-kafka-monitor.

Para debug manual:
```bash
# Ver topics
docker exec pqrs_v2_kafka kafka-topics --list --bootstrap-server localhost:9092

# Ver mensajes del topic
docker exec pqrs_v2_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic pqrs.raw.emails \
  --from-beginning
```


## Referencias

- [[01_ARQUITECTURA_MAESTRA]]
- [[infra_docker_ai_worker]]
- [[service_kafka_producer]]
