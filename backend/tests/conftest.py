import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import get_db_connection
from app.core.security import create_access_token


@pytest.fixture
def mock_db_connection():
    """Conexión asyncpg falsa: métodos async que retornan None por defecto."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value=None)
    return conn


@pytest.fixture
def test_client(mock_db_connection):
    """
    TestClient con la dependencia get_db_connection reemplazada por un mock.
    get_db_connection es un async generator, así que el override debe serlo también.
    """
    async def override_get_db():
        yield mock_db_connection

    app.dependency_overrides[get_db_connection] = override_get_db
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_user():
    return {
        "email": "agente@test.com",
        "tenant_uuid": "11111111-1111-1111-1111-111111111111",
        "role": "agente",
        "nombre": "Agente Test",
        "usuario_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    }


@pytest.fixture
def admin_user():
    return {
        "email": "admin@test.com",
        "tenant_uuid": "22222222-2222-2222-2222-222222222222",
        "role": "admin",
        "nombre": "Admin Test",
        "usuario_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    }


@pytest.fixture
def valid_token(mock_user):
    return create_access_token(
        data={
            "sub": mock_user["email"],
            "tenant_uuid": mock_user["tenant_uuid"],
            "role": mock_user["role"],
            "nombre": mock_user["nombre"],
            "usuario_id": mock_user["usuario_id"],
        },
        expires_delta=timedelta(minutes=30),
    )


@pytest.fixture
def analista_user():
    return {
        "email": "analista@test.com",
        "tenant_uuid": "11111111-1111-1111-1111-111111111111",
        "role": "analista",
        "nombre": "Analista Test",
        "usuario_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    }


@pytest.fixture
def analista_token(analista_user):
    return create_access_token(
        data={
            "sub": analista_user["email"],
            "tenant_uuid": analista_user["tenant_uuid"],
            "role": analista_user["role"],
            "nombre": analista_user["nombre"],
            "usuario_id": analista_user["usuario_id"],
        },
        expires_delta=timedelta(minutes=30),
    )


@pytest.fixture
async def fake_redis():
    """FakeRedis async para tests aislados sin Redis real."""
    import fakeredis.aioredis as fakeredis_async
    r = fakeredis_async.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()
