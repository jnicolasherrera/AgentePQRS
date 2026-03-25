import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from aiokafka import AIOKafkaProducer

logger = logging.getLogger("KAFKA_PRODUCER")

KAFKA_TOPIC_EMAILS = "pqrs.raw.emails"
KAFKA_TOPIC_DLQ = "pqrs.events.dead_letter"

ADJUNTO_THRESHOLD_BYTES = 1 * 1024 * 1024

_producer: Optional[AIOKafkaProducer] = None

KAFKA_INIT_MAX_RETRIES = 5
KAFKA_INIT_RETRY_DELAY = 5


async def init_kafka_producer(bootstrap_servers: str) -> None:
    global _producer
    for attempt in range(KAFKA_INIT_MAX_RETRIES):
        try:
            _producer = AIOKafkaProducer(
                bootstrap_servers=bootstrap_servers,
                acks="all",
                enable_idempotence=True,
                compression_type="gzip",
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            )
            await _producer.start()
            logger.info(f"Kafka producer iniciado — bootstrap: {bootstrap_servers}")
            return
        except Exception as e:
            _producer = None
            if attempt < KAFKA_INIT_MAX_RETRIES - 1:
                logger.warning(
                    f"Kafka no listo (intento {attempt + 1}/{KAFKA_INIT_MAX_RETRIES}): {e} "
                    f"— reintentando en {KAFKA_INIT_RETRY_DELAY}s"
                )
                await asyncio.sleep(KAFKA_INIT_RETRY_DELAY)
            else:
                logger.error(f"Kafka no disponible después de {KAFKA_INIT_MAX_RETRIES} intentos")
                raise


async def close_kafka_producer() -> None:
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None
        logger.info("Kafka producer cerrado")


async def publish_email_event(
    event: dict,
    tenant_id: str,
    correlation_id: str,
) -> None:
    """
    Publica un evento de email a Kafka.
    - Inyecta correlation_id y timestamp de ingesta antes de publicar.
    - Claim Check Pattern: adjuntos > ADJUNTO_THRESHOLD_BYTES se suben a MinIO;
      solo la URI del objeto viaja en el mensaje Kafka.
    - Particiona por tenant_id (key) para garantizar orden por cliente.
    """
    if _producer is None:
        raise RuntimeError(
            "Kafka producer no inicializado — llamar init_kafka_producer() primero"
        )

    # Claim Check Pattern — adjunto pesado sale del evento y va a MinIO
    adjunto_bytes: Optional[bytes] = event.pop("adjunto_bytes", None)
    if adjunto_bytes and len(adjunto_bytes) > ADJUNTO_THRESHOLD_BYTES:
        from app.services.storage_engine import upload_file

        object_name = await upload_file(
            adjunto_bytes,
            f"{correlation_id}.adjunto",
            folder=tenant_id,
        )
        event["adjunto_s3_uri"] = object_name
        logger.info(
            f"Claim Check: adjunto ({len(adjunto_bytes)} bytes) subido a MinIO → {object_name}"
        )

    event["correlation_id"] = correlation_id
    event["tenant_id"] = tenant_id
    event["ingested_at"] = datetime.now(timezone.utc).isoformat()

    await _producer.send_and_wait(
        KAFKA_TOPIC_EMAILS,
        value=event,
        key=tenant_id.encode("utf-8"),
    )
    logger.info(
        f"Evento publicado en Kafka — correlation_id={correlation_id} tenant={tenant_id}"
    )
