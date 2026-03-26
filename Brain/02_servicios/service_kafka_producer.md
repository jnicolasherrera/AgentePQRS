# Service: Kafka Producer

## Archivo
`backend/app/services/kafka_producer.py`

## Descripcion
Produce mensajes a Apache Kafka para el pipeline de procesamiento de emails. Implementa el Claim Check Pattern para adjuntos grandes e inyecta metadata de trazabilidad.

## Topics

| Topic                    | Uso                              |
|--------------------------|----------------------------------|
| pqrs.raw.emails          | Emails crudos para clasificar    |
| pqrs.events.dead_letter  | Mensajes irrecuperables (DLQ)    |

## Inicializacion

`init_kafka_producer(bootstrap_servers)` con retry:
- Max 5 intentos, 5 segundos entre cada uno
- Configuracion: acks=all, idempotence=true, compresion gzip
- Serializer: JSON con `default=str` para datetimes

## Funcion Principal: publish_email_event(event, tenant_id, correlation_id)

### Flujo
1. Verifica que el producer este inicializado
2. **Claim Check Pattern:** Si `adjunto_bytes` > 1MB:
   - Sube a MinIO via storage_engine
   - Reemplaza bytes por `adjunto_s3_uri` en el evento
3. Inyecta metadata: `correlation_id`, `tenant_id`, `ingested_at` (UTC ISO)
4. Publica a `pqrs.raw.emails` con key=tenant_id (order garantizado por tenant)

### Claim Check Pattern
```
Evento original: {adjunto_bytes: <2MB de datos>}
-> Upload a MinIO: pqrs-vault/{tenant_id}/{correlation_id}.adjunto
-> Evento en Kafka: {adjunto_s3_uri: "tenant_id/correlation_id.adjunto"}
```

Beneficio: Kafka no transporta payloads pesados, mantiene latencia baja.

## Constantes
- `ADJUNTO_THRESHOLD_BYTES = 1MB` -- Umbral para Claim Check
- `KAFKA_INIT_MAX_RETRIES = 5`
- `KAFKA_INIT_RETRY_DELAY = 5s`

## Dependencias
- `aiokafka.AIOKafkaProducer`
- `app.services.storage_engine.upload_file` (para Claim Check)
