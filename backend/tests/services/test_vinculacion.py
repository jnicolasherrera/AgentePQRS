"""Tests unitarios de vinculacion (mocks asyncpg.Connection)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.services.vinculacion import vincular_con_pqrs_previo


TENANT = uuid.UUID("00000000-0001-0001-0001-000000000001")
TENANT_B = uuid.UUID("00000000-0002-0002-0002-000000000002")
TUTELA_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
DOC_HASH = "a" * 64


def _row(id_str: str, tipo: str = "QUEJA", estado: str = "ABIERTO", enviado: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": uuid.UUID(id_str),
        "numero_radicado": f"PQRS-2026-{id_str[:6].upper()}",
        "tipo_caso": tipo,
        "estado": estado,
        "fecha_recibido": now - timedelta(days=5),
        "enviado_at": now if enviado else None,
    }


# ── PQRS sin respuesta → PQRS_NO_CONTESTADO ─────────────────────────

@pytest.mark.asyncio
async def test_match_unico_sin_respuesta():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[_row("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", enviado=False)])
    conn.execute = AsyncMock(return_value=None)

    result = await vincular_con_pqrs_previo(TUTELA_ID, TENANT, DOC_HASH, conn)

    assert result is not None
    assert result["motivo"] == "PQRS_NO_CONTESTADO"
    assert len(result["matches"]) == 1
    assert result["matches"][0]["enviado_at"] is None
    # Persiste en metadata_especifica.
    conn.execute.assert_awaited_once()
    sql = conn.execute.await_args[0][0]
    assert "metadata_especifica" in sql
    assert "jsonb_build_object" in sql


# ── PQRS con respuesta previa → RESPUESTA_INSATISFACTORIA ───────────

@pytest.mark.asyncio
async def test_match_unico_con_respuesta():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[_row("cccccccc-cccc-cccc-cccc-cccccccccccc", enviado=True)])
    conn.execute = AsyncMock(return_value=None)

    result = await vincular_con_pqrs_previo(TUTELA_ID, TENANT, DOC_HASH, conn)

    assert result["motivo"] == "RESPUESTA_INSATISFACTORIA"
    assert result["matches"][0]["enviado_at"] is not None


# ── Varios matches → MULTIPLE_MATCHES ───────────────────────────────

@pytest.mark.asyncio
async def test_multiples_matches():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[
        _row("11111111-1111-1111-1111-111111111111"),
        _row("22222222-2222-2222-2222-222222222222", enviado=True),
        _row("33333333-3333-3333-3333-333333333333"),
    ])
    conn.execute = AsyncMock(return_value=None)

    result = await vincular_con_pqrs_previo(TUTELA_ID, TENANT, DOC_HASH, conn)

    assert result["motivo"] == "MULTIPLE_MATCHES"
    assert len(result["matches"]) == 3
    assert len(result["data"]["matches_ids"]) == 3


# ── Sin matches → None (no persiste nada) ───────────────────────────

@pytest.mark.asyncio
async def test_sin_matches_retorna_none():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value=None)

    result = await vincular_con_pqrs_previo(TUTELA_ID, TENANT, DOC_HASH, conn)

    assert result is None
    conn.execute.assert_not_called()


# ── La query filtra por tenant (aislamiento) ────────────────────────

@pytest.mark.asyncio
async def test_query_filtra_por_cliente_id():
    """Verifica que la query SQL incluye el filtro `cliente_id = $1`."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value=None)

    await vincular_con_pqrs_previo(TUTELA_ID, TENANT, DOC_HASH, conn)

    sql = conn.fetch.await_args[0][0]
    assert "cliente_id = $1" in sql
    assert "documento_peticionante_hash = $2" in sql
    # Excluye tutelas y el propio caso.
    assert "tipo_caso != 'TUTELA'" in sql
    assert "id != $3" in sql

    # Argumentos en el orden correcto: cliente_id, doc_hash, caso_id, ventana.
    args = conn.fetch.await_args[0]
    assert args[1] == TENANT
    assert args[2] == DOC_HASH
    assert args[3] == TUTELA_ID


# ── UPDATE falla pero pipeline no crashea ───────────────────────────

@pytest.mark.asyncio
async def test_update_falla_retorna_resultado_igual():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[_row("dddddddd-dddd-dddd-dddd-dddddddddddd")])
    conn.execute = AsyncMock(side_effect=RuntimeError("connection dropped"))

    # No debe propagar la excepción — el UPDATE falla silenciosamente.
    result = await vincular_con_pqrs_previo(TUTELA_ID, TENANT, DOC_HASH, conn)

    assert result["motivo"] == "PQRS_NO_CONTESTADO"
    assert len(result["matches"]) == 1
