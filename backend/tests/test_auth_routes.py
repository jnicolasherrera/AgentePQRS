import uuid
import pytest
from unittest.mock import AsyncMock

from app.core.security import get_password_hash
from app.core.db import get_db_connection
from app.main import app
from fastapi.testclient import TestClient


_TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_PLAIN_PASSWORD = "TestPassword123"
_HASHED_PASSWORD = get_password_hash(_PLAIN_PASSWORD)


def _make_fake_record():
    """
    asyncpg.Record no es instanciable directamente en tests.
    Usamos un dict con __getitem__ para que route pueda acceder via usuario["campo"].
    """
    return {
        "id": _USER_ID,
        "cliente_id": _TENANT_ID,
        "nombre": "Agente De Prueba",
        "password_hash": _HASHED_PASSWORD,
        "rol": "agente",
        "debe_cambiar_password": False,
        "cliente_nombre": "Empresa Test S.A.",
    }


def _build_client_with_mock_conn(mock_conn):
    """Construye un TestClient con get_db_connection sobreescrito."""
    async def override_get_db():
        yield mock_conn

    app.dependency_overrides[get_db_connection] = override_get_db
    client = TestClient(app, raise_server_exceptions=False)
    return client


def test_login_credenciales_validas():
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=_make_fake_record())
    mock_conn.execute = AsyncMock(return_value=None)

    client = _build_client_with_mock_conn(mock_conn)
    try:
        response = client.post(
            "/api/v2/auth/login",
            json={"email": "agente@test.com", "password": _PLAIN_PASSWORD},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["rol"] == "agente"
        assert data["user"]["email"] == "agente@test.com"
    finally:
        app.dependency_overrides.clear()


def test_login_usuario_no_existe_retorna_401():
    mock_conn = AsyncMock()
    # fetchrow retorna None → usuario no encontrado
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock(return_value=None)

    client = _build_client_with_mock_conn(mock_conn)
    try:
        response = client.post(
            "/api/v2/auth/login",
            json={"email": "noexiste@test.com", "password": "cualquiera"},
        )
        assert response.status_code == 401
        assert "Credenciales" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_login_password_incorrecta_retorna_401():
    mock_conn = AsyncMock()
    # El usuario existe pero la contraseña en el mock es la correcta;
    # enviamos una diferente en el request.
    mock_conn.fetchrow = AsyncMock(return_value=_make_fake_record())
    mock_conn.execute = AsyncMock(return_value=None)

    client = _build_client_with_mock_conn(mock_conn)
    try:
        response = client.post(
            "/api/v2/auth/login",
            json={"email": "agente@test.com", "password": "PasswordEquivocada999"},
        )
        assert response.status_code == 401
        assert "Credenciales" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
