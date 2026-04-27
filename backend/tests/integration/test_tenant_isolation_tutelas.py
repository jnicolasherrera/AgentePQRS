"""
Tests aislamiento multi-tenant para vinculación tutelas + capabilities.

Escenarios:
1. Tenant A tiene PQRS previo con doc_hash X. Tenant B inserta TUTELA con mismo
   doc_hash X → vinculación NO encuentra match (filtro cliente_id).
2. Tenant A tiene PQRS previo con doc_hash X. Tenant A inserta TUTELA con mismo
   doc_hash X → vinculación SÍ encuentra match.
3. user_capabilities: usuario del tenant A no debe ver capabilities del tenant B
   (RLS + filtrado en query).

Mocks asyncpg, NO toca DB real (pero verifica el SQL generado contiene los
filtros correctos).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.services.capabilities import list_user_capabilities, user_has_capability
from app.services.vinculacion import vincular_con_pqrs_previo


TENANT_A = uuid.UUID("00000000-0001-0001-0001-000000000001")
TENANT_B = uuid.UUID("00000000-0002-0002-0002-000000000002")
USER_A = uuid.UUID("00000000-0001-1001-0001-000000000001")
TUTELA_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
DOC_HASH = "x" * 64


def _row(id_str: str, enviado: bool = False) -> dict:
    return {
        "id": uuid.UUID(id_str),
        "numero_radicado": "PQRS-2026-AAAAAA",
        "tipo_caso": "QUEJA",
        "estado": "ABIERTO",
        "fecha_recibido": datetime(2026, 4, 1, tzinfo=timezone.utc),
        "enviado_at": datetime(2026, 4, 5, tzinfo=timezone.utc) if enviado else None,
    }


# ── Vinculación ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_vinculacion_tenant_b_no_ve_pqrs_de_tenant_a():
    """
    Tenant A tiene QUEJA con doc_hash X. Tenant B busca con mismo doc_hash y
    espera 0 matches. La query filtra por cliente_id=$1 que en este caso es
    TENANT_B → solo recibe rows de TENANT_B (que en el mock es []).
    """
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])  # Tenant B sin matches.
    conn.execute = AsyncMock(return_value=None)

    result = await vincular_con_pqrs_previo(TUTELA_ID, TENANT_B, DOC_HASH, conn)
    assert result is None

    # Verificamos que la query filtró por TENANT_B y NO por TENANT_A.
    args = conn.fetch.await_args[0]
    assert args[1] == TENANT_B  # cliente_id en $1
    assert args[1] != TENANT_A


@pytest.mark.asyncio
async def test_vinculacion_mismo_tenant_si_encuentra_match():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[_row("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")])
    conn.execute = AsyncMock(return_value=None)

    result = await vincular_con_pqrs_previo(TUTELA_ID, TENANT_A, DOC_HASH, conn)
    assert result is not None
    assert result["motivo"] == "PQRS_NO_CONTESTADO"


@pytest.mark.asyncio
async def test_vinculacion_query_excluye_tutelas_previas():
    """
    El SQL de la query debe excluir tipo_caso='TUTELA' para evitar cascadeo:
    una tutela nueva no se vincula con tutelas anteriores del mismo accionante.
    """
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    await vincular_con_pqrs_previo(TUTELA_ID, TENANT_A, DOC_HASH, conn)
    sql = conn.fetch.await_args[0][0]
    assert "tipo_caso != 'TUTELA'" in sql


@pytest.mark.asyncio
async def test_vinculacion_excluye_caso_actual():
    """El SQL excluye el propio caso_id (id != $3)."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    await vincular_con_pqrs_previo(TUTELA_ID, TENANT_A, DOC_HASH, conn)
    sql = conn.fetch.await_args[0][0]
    assert "id != $3" in sql


# ── Capabilities aislamiento ──────────────────────────────────────

@pytest.mark.asyncio
async def test_user_has_capability_no_ve_de_otro_tenant():
    """
    user_has_capability filtra por usuario_id, así que un user_id que pertenece a
    tenant B nunca matcheará grants de tenant A. La policy RLS refuerza esto a
    nivel DB. Aquí verificamos la query.
    """
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    result = await user_has_capability(USER_A, "CAN_SIGN_DOCUMENT", "TUTELA", conn)
    assert result is False
    sql = conn.fetchrow.call_args[0][0]
    assert "usuario_id = $1" in sql
    assert "revoked_at IS NULL" in sql


@pytest.mark.asyncio
async def test_list_user_capabilities_solo_user_id_pasado():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    await list_user_capabilities(USER_A, conn)
    sql = conn.fetch.call_args[0][0]
    args = conn.fetch.call_args[0][1:]
    assert "usuario_id = $1" in sql
    assert args[0] == USER_A


# ── Sanity: query de vinculación tiene los filtros completos ──────

@pytest.mark.asyncio
async def test_vinculacion_query_tiene_3_filtros_aislamiento():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    await vincular_con_pqrs_previo(TUTELA_ID, TENANT_A, DOC_HASH, conn, ventana_dias=30)
    sql = conn.fetch.await_args[0][0]
    # Aislamiento por: cliente_id, doc_hash, no-tutela, no-self.
    for clause in [
        "cliente_id = $1",
        "documento_peticionante_hash = $2",
        "tipo_caso != 'TUTELA'",
        "id != $3",
    ]:
        assert clause in sql, f"Falta filtro: {clause}"
