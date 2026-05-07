"""
worker_ai_consumer.py — Sprint 2: El Cerebro
Worker perpetuo que consume pqrs.raw.emails desde Kafka, clasifica con IA
y persiste en PostgreSQL. Commit manual de offsets: solo después de DB exitosa.
"""
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as redis
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from app.services.ai_classifier import classify_email_event, PoisonPillError
from app.services.pipeline import process_classified_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("AI_CONSUMER")

WORKER_DB_URL = os.environ.get(
    "WORKER_DB_URL",
    "postgresql://aequitas_worker:changeme_worker@postgres_v2:5432/pqrs_v2",
)
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka_v2:29092")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis_v2:6379")

KAFKA_TOPIC = "pqrs.raw.emails"
KAFKA_DLQ_TOPIC = "pqrs.events.dead_letter"
CONSUMER_GROUP = "aequitas_classifier_group"


async def _send_to_dlq(
    producer: AIOKafkaProducer,
    raw_value: bytes,
    correlation_id: str,
    reason: str,
) -> None:
    dlq_event = {
        "original_event": raw_value.decode("utf-8", errors="replace"),
        "correlation_id": correlation_id,
        "failure_reason": reason,
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }
    await producer.send_and_wait(
        KAFKA_DLQ_TOPIC,
        value=json.dumps(dlq_event, default=str).encode("utf-8"),
    )
    logger.warning(
        f"Evento enviado a DLQ — correlation_id={correlation_id} reason={reason}"
    )


async def _process_message(
    msg,
    pool: asyncpg.Pool,
    r: redis.Redis,
    producer: AIOKafkaProducer,
) -> None:
    correlation_id = "unknown"
    try:
        event = json.loads(msg.value)
        correlation_id = event.get("correlation_id", str(uuid.uuid4()))
        tenant_id = event.get("tenant_id", "")
        logger.info(f"Procesando — correlation_id={correlation_id} tenant={tenant_id}")

        # Clasificación IA — retry exponencial interno manejado por classify_email_event
        result = await classify_email_event(event)

        # Pipeline unificado post-clasificación: enrich + SLA python (tutelas) + INSERT + vinculación.
        async with pool.acquire() as conn:
            caso_id = await process_classified_event(
                result, event, uuid.UUID(tenant_id), conn, pool,
            )

        notification = {
            "tipo": "nuevo_caso",
            "caso_id": str(caso_id),
            "correlation_id": correlation_id,
            "tipo_caso": result.tipo_caso,
            "prioridad": result.prioridad,
            "tenant_id": tenant_id,
        }
        await r.publish(f"pqrs.events.{tenant_id}", json.dumps(notification))
        logger.info(
            f"Caso insertado y notificado — caso_id={caso_id} correlation_id={correlation_id}"
        )

    except PoisonPillError as e:
        # Mensaje irrecuperable — va a DLQ y el offset se commitea para no trancar la tubería
        await _send_to_dlq(producer, msg.value, correlation_id, str(e))

    except Exception as e:
        logger.error(
            f"Error no manejado — correlation_id={correlation_id}: {e}",
            exc_info=True,
        )
        await _send_to_dlq(producer, msg.value, correlation_id, f"UnhandledError: {e}")


async def main() -> None:
    pool = await asyncpg.create_pool(WORKER_DB_URL, min_size=2, max_size=10)
    r = redis.from_url(REDIS_URL, decode_responses=True)

    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        acks="all",
        enable_idempotence=True,
        value_serializer=lambda v: v if isinstance(v, bytes) else v.encode("utf-8"),
    )
    await producer.start()

    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=CONSUMER_GROUP,
        enable_auto_commit=False,       # MANUAL — commit solo después de procesamiento exitoso o DLQ
        auto_offset_reset="earliest",
        value_deserializer=lambda v: v, # raw bytes — deserializamos en _process_message
    )
    await consumer.start()
    logger.info(
        f"Consumer iniciado — topic={KAFKA_TOPIC} group={CONSUMER_GROUP}"
    )

    try:
        async for msg in consumer:
            await _process_message(msg, pool, r, producer)
            await consumer.commit()     # Commit SIEMPRE: éxito o DLQ — nunca bloqueamos la partición
    finally:
        await consumer.stop()
        await producer.stop()
        await pool.close()
        await r.aclose()
        logger.info("Consumer apagado limpiamente")


if __name__ == "__main__":
    asyncio.run(main())
