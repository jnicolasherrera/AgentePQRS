"""Tests unitarios de capabilities (sprint Tutelas)."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.services.capabilities import (
    grant_capability,
    list_user_capabilities,
    user_has_capability,
)


USER = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT = uuid.UUID("22222222-2222-2222-2222-222222222222")
GRANTED_BY = uuid.UUID("33333333-3333-3333-3333-333333333333")


# ── user_has_capability ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scope_especifico_match_exacto_devuelve_true():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"ok": 1})
    assert await user_has_capability(USER, "CAN_SIGN_DOCUMENT", "TUTELA", conn) is True


@pytest.mark.asyncio
async def test_scope_especifico_sin_match_devuelve_false():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    assert await user_has_capability(USER, "CAN_SIGN_DOCUMENT", "PETICION", conn) is False


@pytest.mark.asyncio
async def test_scope_null_global():
    # Sin scope especificado → solo mira caps globales (scope IS NULL).
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"ok": 1})
    result = await user_has_capability(USER, "CAN_MANAGE_USERS", None, conn)
    assert result is True
    # La query debe filtrar por scope IS NULL (implícito por el texto SQL).
    called_sql = conn.fetchrow.call_args[0][0]
    assert "scope IS NULL" in called_sql


@pytest.mark.asyncio
async def test_scope_null_global_cubre_consulta_con_scope_especifico():
    """Una capability con scope NULL debe matchear cuando pido un scope específico."""
    conn = AsyncMock()
    # Simulamos que la query con "scope IS NULL OR scope = $3" matchea (porque existe la global).
    conn.fetchrow = AsyncMock(return_value={"ok": 1})
    result = await user_has_capability(USER, "CAN_VIEW_ALL", "TUTELA", conn)
    assert result is True
    called_sql = conn.fetchrow.call_args[0][0]
    assert "scope IS NULL OR scope = $3" in called_sql


# ── grant_capability ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_grant_idempotente_on_conflict_do_nothing():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"cliente_id": TENANT})
    conn.execute = AsyncMock(return_value=None)

    await grant_capability(USER, "CAN_APPROVE_RESPONSE", "TUTELA", GRANTED_BY, conn)
    await grant_capability(USER, "CAN_APPROVE_RESPONSE", "TUTELA", GRANTED_BY, conn)

    assert conn.execute.await_count == 2
    called_sql = conn.execute.call_args[0][0]
    assert "ON CONFLICT" in called_sql
    assert "DO NOTHING" in called_sql


@pytest.mark.asyncio
async def test_grant_para_usuario_inexistente_falla():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="no existe"):
        await grant_capability(USER, "CAN_SIGN_DOCUMENT", "TUTELA", None, conn)


@pytest.mark.asyncio
async def test_grant_obtiene_cliente_id_del_usuario():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"cliente_id": TENANT})
    conn.execute = AsyncMock(return_value=None)

    await grant_capability(USER, "CAN_SIGN_DOCUMENT", "TUTELA", GRANTED_BY, conn)

    # Verificamos que en los params del INSERT va el cliente_id obtenido.
    args = conn.execute.await_args[0]
    # Posición: (SQL, usuario_id, cliente_id, capability, scope, granted_by).
    assert args[1] == USER
    assert args[2] == TENANT
    assert args[3] == "CAN_SIGN_DOCUMENT"


# ── list_user_capabilities ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_ordenado_nulls_first():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[
        {"id": "a", "capability": "CAN_APPROVE_RESPONSE", "scope": None, "granted_at": None, "granted_by": None},
        {"id": "b", "capability": "CAN_SIGN_DOCUMENT", "scope": "TUTELA", "granted_at": None, "granted_by": None},
    ])
    result = await list_user_capabilities(USER, conn)
    assert len(result) == 2
    sql = conn.fetch.call_args[0][0]
    assert "NULLS FIRST" in sql
    assert "revoked_at IS NULL" in sql
