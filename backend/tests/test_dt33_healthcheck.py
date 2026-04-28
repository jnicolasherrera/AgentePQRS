"""
Tests DT-33 — healthcheck_worker.py.

Cobertura del script standalone:
- T1: archivo flag no existe → exit 1.
- T2: archivo flag viejo (>10min) → exit 1.
- T3: WORKER_DB_URL/DATABASE_URL no setadas → exit 1.
- T4: SELECT 1 falla (asyncpg.connect explota) → exit 1.
- T5: SELECT 1 retorna valor inesperado → exit 1.
- T6: flag reciente + DB OK → exit 0.

Ejecuta el script vía importación + asyncio.run en lugar de subprocess
para poder mockear asyncpg sin docker.
"""
from __future__ import annotations

import os
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Path al script
HC_PATH = os.path.join(os.path.dirname(__file__), "..", "healthcheck_worker.py")
HC_PATH = os.path.abspath(HC_PATH)


def _load_hc_module():
    """Carga healthcheck_worker.py como módulo, fresco cada vez para resetear estado."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("healthcheck_worker", HC_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_t1_flag_missing_exits_1(tmp_path, monkeypatch):
    monkeypatch.setenv("ACTIVITY_FLAG", str(tmp_path / "no_existe"))
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub")
    hc = _load_hc_module()

    with pytest.raises(SystemExit) as exc:
        hc._check_activity_flag()
    assert exc.value.code == 1


def test_t2_flag_too_old_exits_1(tmp_path, monkeypatch):
    flag = tmp_path / "flag"
    flag.write_text("old")
    # Forzar mtime a 20 min atrás
    old_mtime = time.time() - 20 * 60
    os.utime(str(flag), (old_mtime, old_mtime))

    monkeypatch.setenv("ACTIVITY_FLAG", str(flag))
    monkeypatch.setenv("HC_MAX_INACTIVITY_MINUTES", "10")
    hc = _load_hc_module()

    with pytest.raises(SystemExit) as exc:
        hc._check_activity_flag()
    assert exc.value.code == 1


def test_t3_no_dsn_exits_1(monkeypatch):
    monkeypatch.delenv("WORKER_DB_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    hc = _load_hc_module()

    import asyncio
    with pytest.raises(SystemExit) as exc:
        asyncio.run(hc._check_db())
    assert exc.value.code == 1


def test_t4_db_connect_fails_exits_1(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub")
    hc = _load_hc_module()

    import asyncio
    with patch.object(hc.asyncpg, "connect", new=AsyncMock(side_effect=ConnectionRefusedError("DB down"))):
        with pytest.raises(SystemExit) as exc:
            asyncio.run(hc._check_db())
    assert exc.value.code == 1


def test_t5_select_1_unexpected_value_exits_1(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub")
    hc = _load_hc_module()

    fake_conn = MagicMock()
    fake_conn.fetchval = AsyncMock(return_value=42)  # unexpected
    fake_conn.close = AsyncMock()

    import asyncio
    with patch.object(hc.asyncpg, "connect", new=AsyncMock(return_value=fake_conn)):
        with pytest.raises(SystemExit) as exc:
            asyncio.run(hc._check_db())
    assert exc.value.code == 1


def test_t6_full_health_exits_0(tmp_path, monkeypatch):
    flag = tmp_path / "flag"
    flag.write_text("recent")  # mtime = ahora
    monkeypatch.setenv("ACTIVITY_FLAG", str(flag))
    monkeypatch.setenv("HC_MAX_INACTIVITY_MINUTES", "10")
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub")
    hc = _load_hc_module()

    fake_conn = MagicMock()
    fake_conn.fetchval = AsyncMock(return_value=1)
    fake_conn.close = AsyncMock()

    import asyncio
    with patch.object(hc.asyncpg, "connect", new=AsyncMock(return_value=fake_conn)):
        with pytest.raises(SystemExit) as exc:
            asyncio.run(hc.main())
    assert exc.value.code == 0
