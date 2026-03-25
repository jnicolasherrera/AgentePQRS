"""
test_webhooks.py — Sprint 4 QA Backend: Webhooks HMAC + Google Token + Dedup
7 tests de seguridad. Router montado en main.py con prefix="/api" → URLs: /api/webhooks/...
"""
import hashlib
import hmac as hmac_lib
import json

import pytest
import fakeredis.aioredis as fakeredis_async
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.api.routes.webhooks import _dedup_and_publish

# main.py: app.include_router(webhooks.router, prefix="/api")
# router tiene prefix="/webhooks" → URL final: /api/webhooks/<endpoint>
MICROSOFT_URL = "/api/webhooks/microsoft-graph"
GOOGLE_URL = "/api/webhooks/google-workspace"

TEST_MICROSOFT_SECRET = "test-secret"
TEST_GOOGLE_TOKEN = "test-google-token"


def _build_hmac_signature(payload: bytes, secret: str) -> str:
    digest = hmac_lib.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _microsoft_payload(message_id: str = "msg-abc-001") -> bytes:
    data = {
        "value": [
            {
                "resourceData": {"id": message_id},
                "resource": "Users/user/Messages/msg-abc-001",
                "changeType": "created",
                "subscriptionId": "sub-001",
                "clientState": "11111111-1111-1111-1111-111111111111",
            }
        ]
    }
    return json.dumps(data).encode()


# ── 1. Handshake GET ────────────────────────────────────────────────────────────

def test_microsoft_graph_handshake_returns_validation_token():
    """GET ?validationToken=abc123 debe devolver el token como texto plano (200)."""
    with TestClient(app) as client:
        response = client.get(MICROSOFT_URL, params={"validationToken": "abc123"})

    assert response.status_code == 200
    assert response.text == "abc123"
    assert "text/plain" in response.headers.get("content-type", "")


# ── 2. POST Microsoft Graph — HMAC válida ───────────────────────────────────────

def test_microsoft_graph_valid_hmac_returns_202(monkeypatch):
    """POST con firma HMAC-SHA256 correcta debe retornar 202."""
    monkeypatch.setattr(settings, "microsoft_webhook_secret", TEST_MICROSOFT_SECRET)

    payload = _microsoft_payload()
    signature = _build_hmac_signature(payload, TEST_MICROSOFT_SECRET)

    with patch("app.services.kafka_producer.publish_email_event", new_callable=AsyncMock):
        with TestClient(app) as client:
            response = client.post(
                MICROSOFT_URL,
                content=payload,
                headers={"X-Hub-Signature": signature},
            )

    assert response.status_code == 202


# ── 3. POST Microsoft Graph — HMAC inválida ────────────────────────────────────

def test_microsoft_graph_invalid_hmac_returns_403(monkeypatch):
    """POST con firma HMAC falsa debe retornar 403 — imposible suplantar Microsoft."""
    monkeypatch.setattr(settings, "microsoft_webhook_secret", TEST_MICROSOFT_SECRET)

    payload = _microsoft_payload()

    with TestClient(app) as client:
        response = client.post(
            MICROSOFT_URL,
            content=payload,
            headers={"X-Hub-Signature": "sha256=invalidsignature"},
        )

    assert response.status_code == 403


# ── 4. POST Microsoft Graph — sin header X-Hub-Signature ──────────────────────

def test_microsoft_graph_missing_hmac_returns_403(monkeypatch):
    """POST sin header X-Hub-Signature debe retornar 403."""
    monkeypatch.setattr(settings, "microsoft_webhook_secret", TEST_MICROSOFT_SECRET)

    payload = _microsoft_payload()

    with TestClient(app) as client:
        response = client.post(MICROSOFT_URL, content=payload)

    assert response.status_code == 403


# ── 5. POST Google Workspace — token válido ────────────────────────────────────

def test_google_workspace_valid_token_returns_202(monkeypatch):
    """POST con X-Goog-Channel-Token correcto debe retornar 202."""
    monkeypatch.setattr(settings, "google_webhook_token", TEST_GOOGLE_TOKEN)

    payload = json.dumps({"historyId": "12345"}).encode()

    with patch("app.services.kafka_producer.publish_email_event", new_callable=AsyncMock):
        with TestClient(app) as client:
            response = client.post(
                GOOGLE_URL,
                content=payload,
                headers={"X-Goog-Channel-Token": TEST_GOOGLE_TOKEN},
            )

    assert response.status_code == 202


# ── 6. POST Google Workspace — token inválido ──────────────────────────────────

def test_google_workspace_invalid_token_returns_403(monkeypatch):
    """POST con token incorrecto debe retornar 403."""
    monkeypatch.setattr(settings, "google_webhook_token", TEST_GOOGLE_TOKEN)

    payload = json.dumps({"historyId": "12345"}).encode()

    with TestClient(app) as client:
        response = client.post(
            GOOGLE_URL,
            content=payload,
            headers={"X-Goog-Channel-Token": "wrong-token"},
        )

    assert response.status_code == 403


# ── 7. Dedup: mismo message_id → Kafka llamado solo una vez ───────────────────

async def test_dedup_same_message_id_publishes_only_once():
    """
    _dedup_and_publish llamado dos veces con el mismo message_id
    debe invocar publish_email_event exactamente una vez.
    """
    r = fakeredis_async.FakeRedis(decode_responses=True)
    payload = _microsoft_payload(message_id="dedup-msg-001")

    with patch(
        "app.services.kafka_producer.publish_email_event",
        new_callable=AsyncMock,
    ) as mock_publish:
        await _dedup_and_publish(payload, "microsoft-graph", r)
        await _dedup_and_publish(payload, "microsoft-graph", r)

    mock_publish.assert_called_once()
    await r.aclose()
