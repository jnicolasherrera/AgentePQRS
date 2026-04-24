"""
capabilities.py — Capabilities granulares por usuario.

Se apoya en la tabla `user_capabilities` creada por la migración 20:
    (usuario_id, capability, scope, granted_by, granted_at, revoked_at, UNIQUE).

Semántica:
- scope NULL  → la capability aplica a cualquier tipo_caso (global).
- scope 'X'   → la capability solo aplica al tipo_caso X.

Las 3 funciones trabajan con `asyncpg.Connection` y son async.
RLS a nivel DB está activo (policy tenant_isolation_user_caps_policy); igualmente
todas las queries van filtradas por usuario para aislamiento en el plano aplicación.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

import asyncpg

logger = logging.getLogger("CAPABILITIES")


async def user_has_capability(
    user_id: uuid.UUID,
    capability: str,
    tipo_caso_scope: Optional[str],
    conn: asyncpg.Connection,
) -> bool:
    """
    True si el usuario tiene la capability con scope NULL (global) o con el
    scope específico solicitado, y la capability no está revocada.
    """
    if tipo_caso_scope is None:
        # Consultamos solo scope NULL.
        row = await conn.fetchrow(
            """
            SELECT 1 FROM user_capabilities
            WHERE usuario_id = $1
              AND capability = $2
              AND scope IS NULL
              AND revoked_at IS NULL
            LIMIT 1
            """,
            user_id,
            capability,
        )
        return row is not None

    # scope específico: matchea NULL (global) o el scope exacto.
    row = await conn.fetchrow(
        """
        SELECT 1 FROM user_capabilities
        WHERE usuario_id = $1
          AND capability = $2
          AND (scope IS NULL OR scope = $3)
          AND revoked_at IS NULL
        LIMIT 1
        """,
        user_id,
        capability,
        tipo_caso_scope,
    )
    return row is not None


async def grant_capability(
    user_id: uuid.UUID,
    capability: str,
    tipo_caso_scope: Optional[str],
    granted_by: Optional[uuid.UUID],
    conn: asyncpg.Connection,
) -> None:
    """
    Otorga una capability al usuario. Idempotente vía ON CONFLICT DO NOTHING.
    Obtiene `cliente_id` del usuario automáticamente.
    """
    cliente_id_row = await conn.fetchrow(
        "SELECT cliente_id FROM usuarios WHERE id = $1",
        user_id,
    )
    if cliente_id_row is None:
        raise ValueError(f"Usuario {user_id} no existe")

    cliente_id = cliente_id_row["cliente_id"]

    await conn.execute(
        """
        INSERT INTO user_capabilities (usuario_id, cliente_id, capability, scope, granted_by)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (usuario_id, capability, scope) DO NOTHING
        """,
        user_id,
        cliente_id,
        capability,
        tipo_caso_scope,
        granted_by,
    )
    logger.info(
        "Capability otorgada — user=%s capability=%s scope=%s by=%s",
        user_id, capability, tipo_caso_scope, granted_by,
    )


async def list_user_capabilities(
    user_id: uuid.UUID,
    conn: asyncpg.Connection,
) -> list[dict[str, Any]]:
    """
    Lista todas las capabilities activas del usuario, ordenadas por capability
    y luego por scope con NULLS FIRST (globales antes que scoped).
    """
    rows = await conn.fetch(
        """
        SELECT id, capability, scope, granted_at, granted_by
        FROM user_capabilities
        WHERE usuario_id = $1
          AND revoked_at IS NULL
        ORDER BY capability ASC, scope ASC NULLS FIRST
        """,
        user_id,
    )
    return [dict(r) for r in rows]
