import asyncio
import json
from fastapi import APIRouter, Request, HTTPException
from sse_starlette.sse import EventSourceResponse
import redis.asyncio as redis
import logging
from app.core.security import decode_access_token
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


async def _stream_generator(request: Request, tenant_id: str, user_id: str, role: str):
    r = redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()

    # super_admin ve TODOS los tenants via pattern subscription
    if role == "super_admin":
        await pubsub.psubscribe("pqrs.events.*")
        channel = "pqrs.events.*"
    else:
        channel = f"pqrs.events.{tenant_id}"
        await pubsub.subscribe(channel)
    logger.info(f"SSE suscrito — channel={channel} role={role}")

    last_ping = asyncio.get_event_loop().time()
    try:
        while True:
            if await request.is_disconnected():
                logger.info(f"SSE desconectado — channel={channel}")
                break

            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is not None and message.get("type") in ("message", "pmessage"):
                raw = message["data"]
                data = json.loads(raw)

                if role in ("analista", "abogado"):
                    if data.get("asignado_a") != user_id:
                        continue

                yield {"event": "new_pqr", "data": raw}
            else:
                # Keepalive cada 30s para evitar que proxies (nginx, Cloudflare) cierren la conexión idle
                now = asyncio.get_event_loop().time()
                if now - last_ping >= 30:
                    yield {"event": "ping", "data": ""}
                    last_ping = now

    except Exception as e:
        logger.error(f"Error en SSE generator — channel={channel}: {e}")
    finally:
        if role == "super_admin":
            await pubsub.punsubscribe("pqrs.events.*")
        else:
            await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        logger.info(f"SSE cleanup — channel={channel}")


@router.get("/listen")
async def listen_pqrs(request: Request):
    token = request.query_params.get("token")
    payload = decode_access_token(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="Token requerido para SSE")

    tenant_id = payload.get("tenant_uuid")
    user_id = payload.get("usuario_id")
    role = payload.get("role", "analista")

    return EventSourceResponse(_stream_generator(request, tenant_id, user_id, role))
