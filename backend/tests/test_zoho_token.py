"""Regresión del bug de la caída de 13 días (mayo 2026) — C3.

Cuando el refresh_token de ARC quedó revocado, Zoho devolvía 200 con
{"error": ...} sin access_token; el código hacía res["access_token"] → KeyError
y reintentaba sin pausa, disparando el rate-limit del endpoint OAuth.
Ahora se maneja con gracia: ZohoAuthError + backoff largo, sin KeyError.
"""
import pytest
from unittest.mock import patch, MagicMock

from app.services.zoho_engine import ZohoServiceV2, ZohoAuthError, ZohoRateLimitError


def _resp(status, json_data=None, text=""):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = json_data if json_data is not None else {}
    m.text = text
    return m


@pytest.fixture(autouse=True)
def _clean_registries():
    for d in (ZohoServiceV2._backoff_registry, ZohoServiceV2._token_cache,
              ZohoServiceV2._consecutive_failures):
        d.clear()
    yield
    for d in (ZohoServiceV2._backoff_registry, ZohoServiceV2._token_cache,
              ZohoServiceV2._consecutive_failures):
        d.clear()


def test_token_exitoso():
    svc = ZohoServiceV2("cid", "secret", "rt_ok")
    with patch("app.services.zoho_engine.requests.post",
               return_value=_resp(200, {"access_token": "AT", "expires_in": 3600})):
        assert svc._get_access_token() == "AT"


def test_token_revocado_lanza_auth_error_no_keyerror():
    """El escenario exacto de la caída: 200 + error, sin access_token."""
    svc = ZohoServiceV2("cid", "secret", "rt_revocado")
    with patch("app.services.zoho_engine.requests.post",
               return_value=_resp(200, {"error": "invalid_code"}, '{"error":"invalid_code"}')):
        with pytest.raises(ZohoAuthError):
            svc._get_access_token()
    # Quedó backoff largo registrado → no se martilla el endpoint OAuth.
    assert "rt_revocado" in ZohoServiceV2._backoff_registry


def test_rate_limit_lanza_rate_limit_error_y_backoff():
    svc = ZohoServiceV2("cid", "secret", "rt_rate")
    with patch("app.services.zoho_engine.requests.post",
               return_value=_resp(429, {"error": "Access Denied"},
                                  "You have made too many requests")):
        with pytest.raises(ZohoRateLimitError):
            svc._get_access_token()
    assert "rt_rate" in ZohoServiceV2._backoff_registry


def test_json_invalido_no_crashea():
    """Si Zoho devuelve un body no-JSON, se trata como auth error, sin explotar."""
    svc = ZohoServiceV2("cid", "secret", "rt_badjson")
    bad = _resp(500, None, "<html>Internal Server Error</html>")
    bad.json.side_effect = ValueError("no json")
    with patch("app.services.zoho_engine.requests.post", return_value=bad):
        with pytest.raises(ZohoAuthError):
            svc._get_access_token()
