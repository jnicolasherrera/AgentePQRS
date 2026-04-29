"""
Tests DT-32 — reconnect logic asyncpg en master_worker_outlook + demo_worker.

Cobertura de la helper `_ensure_alive_connection`:
- T1: conn=None → crea nueva.
- T2: conn vivo (is_closed=False) → retorna mismo conn, no recrea.
- T3: conn cerrado (is_closed=True) → cierra y recrea.
- T4: cierre de conn vieja silencioso si lanza excepción.
- T5: si asyncpg.connect falla durante recreación, propaga la excepción.

Stub `app.services.storage_engine` antes de imports (DT-29).
"""
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Stub eager imports (DT-29 + dependencias C extension).
_storage_stub = MagicMock()
_storage_stub.upload_file = AsyncMock(return_value="stub/path")
_storage_stub.client = MagicMock()
_storage_stub.BUCKET_NAME = "stub"
sys.modules["app.services.storage_engine"] = _storage_stub

# pandas y msal no son necesarios para los tests de helper (solo importados
# en master_worker_outlook). Stub para que el import del módulo no falle.
for _mod in ("pandas", "msal"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# master_worker_outlook._ensure_alive_connection
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_master_worker_creates_conn_when_none():
    import master_worker_outlook as mw

    fake_new_conn = MagicMock()
    fake_new_conn.is_closed = MagicMock(return_value=False)

    with patch("master_worker_outlook.asyncpg.connect", new=AsyncMock(return_value=fake_new_conn)) as mock_connect:
        conn, recreated = await mw._ensure_alive_connection(None, "stub-dsn")

    assert conn is fake_new_conn
    assert recreated is True
    mock_connect.assert_awaited_once_with("stub-dsn", command_timeout=30, timeout=10)


@pytest.mark.asyncio
async def test_master_worker_keeps_alive_conn():
    import master_worker_outlook as mw

    alive_conn = MagicMock()
    alive_conn.is_closed = MagicMock(return_value=False)

    with patch("master_worker_outlook.asyncpg.connect", new=AsyncMock()) as mock_connect:
        conn, recreated = await mw._ensure_alive_connection(alive_conn, "stub-dsn")

    assert conn is alive_conn
    assert recreated is False
    mock_connect.assert_not_awaited()


@pytest.mark.asyncio
async def test_master_worker_recreates_closed_conn():
    import master_worker_outlook as mw

    closed_conn = MagicMock()
    closed_conn.is_closed = MagicMock(return_value=True)
    closed_conn.close = AsyncMock()

    new_conn = MagicMock()
    new_conn.is_closed = MagicMock(return_value=False)

    with patch("master_worker_outlook.asyncpg.connect", new=AsyncMock(return_value=new_conn)) as mock_connect:
        conn, recreated = await mw._ensure_alive_connection(closed_conn, "stub-dsn")

    assert conn is new_conn
    assert recreated is True
    closed_conn.close.assert_awaited_once()
    mock_connect.assert_awaited_once_with("stub-dsn", command_timeout=30, timeout=10)


@pytest.mark.asyncio
async def test_master_worker_swallows_close_error_on_dead_conn():
    """Si la conn vieja explota al cerrar, igual recrea sin propagar."""
    import master_worker_outlook as mw

    bad_conn = MagicMock()
    bad_conn.is_closed = MagicMock(return_value=True)
    bad_conn.close = AsyncMock(side_effect=RuntimeError("boom"))

    new_conn = MagicMock()
    new_conn.is_closed = MagicMock(return_value=False)

    with patch("master_worker_outlook.asyncpg.connect", new=AsyncMock(return_value=new_conn)):
        conn, recreated = await mw._ensure_alive_connection(bad_conn, "stub-dsn")

    assert conn is new_conn
    assert recreated is True


@pytest.mark.asyncio
async def test_master_worker_propagates_recreate_failure():
    """Si asyncpg.connect falla, la excepción se propaga al caller."""
    import master_worker_outlook as mw

    with patch("master_worker_outlook.asyncpg.connect",
               new=AsyncMock(side_effect=ConnectionRefusedError("DB down"))):
        with pytest.raises(ConnectionRefusedError):
            await mw._ensure_alive_connection(None, "stub-dsn")


@pytest.mark.asyncio
async def test_master_worker_force_recreates_apparently_alive_conn():
    """T8: force=True recrea aunque is_closed() retorne False.

    Caso real: conn rota a nivel TCP/protocol (asyncpg no detectó). El except
    del loop principal captura InterfaceError del fetch y llama al helper con
    force=True para forzar la recreación.
    """
    import master_worker_outlook as mw

    apparently_alive = MagicMock()
    apparently_alive.is_closed = MagicMock(return_value=False)  # mentira: conn rota TCP
    apparently_alive.close = AsyncMock()

    new_conn = MagicMock()
    new_conn.is_closed = MagicMock(return_value=False)

    with patch("master_worker_outlook.asyncpg.connect", new=AsyncMock(return_value=new_conn)) as mock_connect:
        conn, recreated = await mw._ensure_alive_connection(apparently_alive, "stub-dsn", force=True)

    assert conn is new_conn
    assert recreated is True
    apparently_alive.close.assert_awaited_once()
    mock_connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_master_worker_passes_timeouts_on_connect():
    """T9: las nuevas conexiones se crean con command_timeout=30 + timeout=10."""
    import master_worker_outlook as mw

    new_conn = MagicMock(is_closed=MagicMock(return_value=False))
    with patch("master_worker_outlook.asyncpg.connect", new=AsyncMock(return_value=new_conn)) as mock_connect:
        await mw._ensure_alive_connection(None, "stub-dsn")

    mock_connect.assert_awaited_once_with("stub-dsn", command_timeout=30, timeout=10)


@pytest.mark.asyncio
async def test_demo_worker_passes_timeouts_on_connect():
    """T9 demo: idem para demo_worker."""
    import demo_worker as dw

    new_conn = MagicMock(is_closed=MagicMock(return_value=False))
    with patch("demo_worker.asyncpg.connect", new=AsyncMock(return_value=new_conn)) as mock_connect:
        await dw._ensure_alive_connection(None, "stub-dsn")

    mock_connect.assert_awaited_once_with("stub-dsn", command_timeout=30, timeout=10)


# ─────────────────────────────────────────────────────────────────────────────
# demo_worker._ensure_alive_connection (mismo contrato)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_demo_worker_recreates_closed_conn():
    import demo_worker as dw

    closed_conn = MagicMock()
    closed_conn.is_closed = MagicMock(return_value=True)
    closed_conn.close = AsyncMock()

    new_conn = MagicMock()
    new_conn.is_closed = MagicMock(return_value=False)

    with patch("demo_worker.asyncpg.connect", new=AsyncMock(return_value=new_conn)):
        conn, recreated = await dw._ensure_alive_connection(closed_conn, "stub-dsn")

    assert conn is new_conn
    assert recreated is True
    closed_conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_demo_worker_keeps_alive_conn():
    import demo_worker as dw

    alive_conn = MagicMock()
    alive_conn.is_closed = MagicMock(return_value=False)

    with patch("demo_worker.asyncpg.connect", new=AsyncMock()) as mock_connect:
        conn, recreated = await dw._ensure_alive_connection(alive_conn, "stub-dsn")

    assert conn is alive_conn
    assert recreated is False
    mock_connect.assert_not_awaited()
