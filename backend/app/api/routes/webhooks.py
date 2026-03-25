import hashlib
import hmac
import json
import logging
import uuid

import redis.asyncio as redis
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, Response

from app.core.config import settings

logger = logging.getLogger("WEBHOOKS_INGESTOR")
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

REDIS_DEDUP_TTL_SECONDS = 604800  # 7 días


def _get_redis() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def _verify_hmac_sha256(payload: bytes, signature_header: str, secret: str) -> bool:
    """Valida firma HMAC-SHA256. Tiempo constante para evitar timing attacks."""
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


async def _dedup_and_publish(payload_bytes: bytes, source: str, r: redis.Redis) -> None:
    """Dedup por message_id via Redis SETNX → publica a Kafka si es nuevo."""
    from app.services.kafka_producer import publish_email_event

    try:
        data = json.loads(payload_bytes)
    except json.JSONDecodeError:
        logger.warning(f"[{source}] Payload no es JSON válido — descartando")
        return

    for notification in data.get("value", []):
        resource_data = notification.get("resourceData", {})
        message_id = resource_data.get("id", "")

        if not message_id:
            logger.warning(f"[{source}] Notificación sin resourceData.id — descartando")
            continue

        # Idempotencia: SETNX con TTL 7 días
        already_seen = not await r.set(
            f"webhook:msgid:{message_id}", "1", nx=True, ex=REDIS_DEDUP_TTL_SECONDS
        )
        if already_seen:
            logger.info(f"[{source}] Duplicado detectado — message_id={message_id} — descartando")
            continue

        correlation_id = str(uuid.uuid4())
        # Microsoft Graph pone el tenant en clientState al crear la suscripción
        tenant_id = notification.get("clientState", "") or "unknown"

        event = {
            "source": source,
            "message_id": message_id,
            "resource": notification.get("resource", ""),
            "change_type": notification.get("changeType", ""),
            "subscription_id": notification.get("subscriptionId", ""),
            "raw_notification": notification,
        }

        await publish_email_event(event, tenant_id=tenant_id, correlation_id=correlation_id)
        logger.info(
            f"[{source}] Evento publicado — correlation_id={correlation_id} message_id={message_id}"
        )


# ── Microsoft Graph ────────────────────────────────────────────────────────────

@router.get("/microsoft-graph")
async def microsoft_graph_validation(validationToken: str = Query(...)) -> PlainTextResponse:
    """Handshake de Microsoft Graph: devuelve el token tal cual para validar el endpoint."""
    return PlainTextResponse(content=validationToken, media_type="text/plain")


@router.post("/microsoft-graph", status_code=202)
async def ingest_microsoft_graph(request: Request, background: BackgroundTasks) -> Response:
    """
    Recibe notificaciones de Microsoft Graph.
    Valida HMAC-SHA256, responde 202 inmediatamente y delega procesamiento al background.
    """
    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature", "")

    if not _verify_hmac_sha256(payload, signature, settings.microsoft_webhook_secret):
        logger.warning("Microsoft Graph webhook: firma HMAC inválida — rechazando")
        raise HTTPException(status_code=403, detail="Firma invalida")

    r = _get_redis()
    background.add_task(_dedup_and_publish, payload, "microsoft-graph", r)
    return Response(status_code=202)


# ── Google Workspace ───────────────────────────────────────────────────────────

@router.post("/google-workspace", status_code=202)
async def ingest_google_workspace(request: Request, background: BackgroundTasks) -> Response:
    """
    Recibe notificaciones de Google Workspace (Gmail Push Notifications).
    Valida X-Goog-Channel-Token, responde 202 inmediatamente y delega al background.
    """
    channel_token = request.headers.get("X-Goog-Channel-Token", "")

    if channel_token != settings.google_webhook_token:
        logger.warning("Google webhook: token inválido — rechazando")
        raise HTTPException(status_code=403, detail="Token invalido")

    payload = await request.body()
    r = _get_redis()
    background.add_task(_dedup_and_publish, payload, "google-workspace", r)
    return Response(status_code=202)
