#!/usr/bin/env python3
"""DT-33 healthcheck funcional de workers (master_worker + demo_worker).

Verifica:
1. Archivo de actividad reciente (<MAX_INACTIVITY_MINUTES) — detecta zombies.
2. Conectividad DB con SELECT 1 — detecta pool muerto.

Exit 0 = healthy, exit 1 = unhealthy.

Variables de entorno:
- ACTIVITY_FLAG: path al flag de actividad (default /tmp/master_worker_last_activity).
- DATABASE_URL / WORKER_DB_URL: DSN postgres.
- HC_MAX_INACTIVITY_MINUTES: ventana de inactividad tolerada (default 10).
"""
import asyncio
import os
import sys
from datetime import datetime
import asyncpg


def _check_activity_flag():
    flag = os.environ.get("ACTIVITY_FLAG", "/tmp/master_worker_last_activity")
    max_minutes = int(os.environ.get("HC_MAX_INACTIVITY_MINUTES", "10"))
    if not os.path.exists(flag):
        print(f"UNHEALTHY: activity flag missing: {flag}", file=sys.stderr)
        sys.exit(1)
    age_seconds = datetime.now().timestamp() - os.path.getmtime(flag)
    age_minutes = age_seconds / 60
    if age_minutes > max_minutes:
        print(f"UNHEALTHY: last activity {age_minutes:.1f}min ago (max {max_minutes})", file=sys.stderr)
        sys.exit(1)


async def _check_db():
    dsn = os.environ.get("WORKER_DB_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        print("UNHEALTHY: WORKER_DB_URL/DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)
    try:
        conn = await asyncpg.connect(dsn, timeout=5, command_timeout=5)
    except Exception as e:
        print(f"UNHEALTHY: DB connect failed: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        result = await conn.fetchval("SELECT 1")
        if result != 1:
            print(f"UNHEALTHY: SELECT 1 returned {result!r}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"UNHEALTHY: SELECT 1 failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            await conn.close()
        except Exception:
            pass


async def main():
    _check_activity_flag()
    await _check_db()
    print("HEALTHY")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
