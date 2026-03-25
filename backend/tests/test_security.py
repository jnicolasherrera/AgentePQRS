from datetime import timedelta

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)

_PAYLOAD = {
    "sub": "usuario@example.com",
    "tenant_uuid": "11111111-1111-1111-1111-111111111111",
    "role": "agente",
}


def test_create_access_token_returns_string():
    token = create_access_token(data=_PAYLOAD.copy())
    assert isinstance(token, str)
    assert len(token) > 0


def test_decode_valid_token():
    token = create_access_token(data=_PAYLOAD.copy(), expires_delta=timedelta(minutes=5))
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == _PAYLOAD["sub"]
    assert payload["tenant_uuid"] == _PAYLOAD["tenant_uuid"]
    assert payload["role"] == _PAYLOAD["role"]


def test_decode_invalid_token_returns_none():
    result = decode_access_token("esto.no.es.un.jwt.valido")
    assert result is None


def test_decode_expired_token_returns_none():
    # expires_delta negativo genera un token ya vencido en el momento de creación
    token = create_access_token(data=_PAYLOAD.copy(), expires_delta=timedelta(seconds=-1))
    result = decode_access_token(token)
    assert result is None


def test_verify_password_correct():
    plain = "MiPasswordSegura123"
    hashed = get_password_hash(plain)
    assert verify_password(plain, hashed) is True


def test_verify_password_wrong():
    hashed = get_password_hash("PasswordCorrecta")
    assert verify_password("PasswordEquivocada", hashed) is False
