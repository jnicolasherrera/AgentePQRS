"""
Tests del fix smoke E2E (sprint Tutelas, 2026-04-27).

Verifica que `insert_pqrs_caso` propaga al INSERT:
- external_msg_id leído del event con fallback (external_msg_id / message_id / id).
- documento_peticionante_hash extraído de metadata_especifica.accionante.documento_hash.

Mocks asyncpg.Pool/Connection para evitar DB real. Solo valida la query
generada y los parámetros enviados.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_classifier import ClassificationResult
from app.services.db_inserter import insert_pqrs_caso


TENANT = uuid.UUID("00000000-0001-0001-0001-000000000001")
CORR_ID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")


def _clasif(tipo: str = "TUTELA") -> ClassificationResult:
    return ClassificationResult(
        tipo_caso=tipo, prioridad="ALTA", plazo_dias=2,
        cedula=None, nombre_cliente=None, es_juzgado=True,
        confianza=0.9, borrador=None,
    )


def _event(extra: dict | None = None) -> dict:
    base = {
        "tenant_id": str(TENANT),
        "correlation_id": str(CORR_ID),
        "subject": "asunto", "body": "cuerpo", "sender": "x@y.invalid",
        "date": "2026-04-27T10:00:00+00:00",
    }
    if extra:
        base.update(extra)
    return base


def _mock_pool(returned_caso_id: uuid.UUID) -> MagicMock:
    """Construye un asyncpg.Pool falso cuyo `acquire()` retorna una conn fake."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=returned_caso_id)
    # _round_robin_analista usa fetchrow.
    conn.fetchrow = AsyncMock(return_value=None)

    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=cm)
    return pool, conn


# ── T1 — external_msg_id se propaga ──────────────────────────────────

@pytest.mark.asyncio
async def test_external_msg_id_se_propaga_al_insert():
    expected_id = uuid.uuid4()
    pool, conn = _mock_pool(expected_id)
    event = _event({"external_msg_id": "SMOKE_AGENTE3_xyz"})

    await insert_pqrs_caso(event, _clasif(), pool)

    args = conn.fetchval.await_args[0]
    sql = args[0]
    assert "external_msg_id" in sql
    # Posición $14 según el INSERT actual: cliente_id($1)..fecha_vencimiento($13)
    # external_msg_id($14), documento_peticionante_hash($15).
    # Args: (sql, $1, $2, ..., $15) → índice 14 en args es $14.
    assert args[14] == "SMOKE_AGENTE3_xyz"


@pytest.mark.asyncio
async def test_external_msg_id_fallback_a_message_id():
    expected_id = uuid.uuid4()
    pool, conn = _mock_pool(expected_id)
    event = _event({"message_id": "<gmail-msg-001@mail>"})

    await insert_pqrs_caso(event, _clasif(), pool)
    args = conn.fetchval.await_args[0]
    assert args[14] == "<gmail-msg-001@mail>"


@pytest.mark.asyncio
async def test_external_msg_id_fallback_a_id():
    expected_id = uuid.uuid4()
    pool, conn = _mock_pool(expected_id)
    event = _event({"id": "outlook-msg-AAaaA"})

    await insert_pqrs_caso(event, _clasif(), pool)
    args = conn.fetchval.await_args[0]
    assert args[14] == "outlook-msg-AAaaA"


@pytest.mark.asyncio
async def test_external_msg_id_ausente_queda_null():
    expected_id = uuid.uuid4()
    pool, conn = _mock_pool(expected_id)
    event = _event()  # sin external_msg_id ni message_id ni id

    await insert_pqrs_caso(event, _clasif(), pool)
    args = conn.fetchval.await_args[0]
    assert args[14] is None


@pytest.mark.asyncio
async def test_external_msg_id_string_vacio_queda_null():
    expected_id = uuid.uuid4()
    pool, conn = _mock_pool(expected_id)
    event = _event({"external_msg_id": "   "})  # whitespace → None tras strip

    await insert_pqrs_caso(event, _clasif(), pool)
    args = conn.fetchval.await_args[0]
    assert args[14] is None


# ── T2 — documento_peticionante_hash se propaga ──────────────────────

@pytest.mark.asyncio
async def test_documento_hash_se_propaga_desde_metadata():
    expected_id = uuid.uuid4()
    pool, conn = _mock_pool(expected_id)
    event = _event({"external_msg_id": "x"})
    metadata = {
        "tipo_actuacion": "AUTO_ADMISORIO",
        "plazo_informe_horas": 16,
        "accionante": {"documento_hash": "a" * 64, "tipo_documento": "CC"},
    }

    await insert_pqrs_caso(event, _clasif("TUTELA"), pool, metadata_especifica=metadata)
    args = conn.fetchval.await_args[0]
    sql = args[0]
    assert "documento_peticionante_hash" in sql
    assert args[15] == "a" * 64


# ── T3 — sin metadata.accionante, doc_hash queda NULL (no rompe) ────

@pytest.mark.asyncio
async def test_doc_hash_null_si_metadata_sin_accionante():
    expected_id = uuid.uuid4()
    pool, conn = _mock_pool(expected_id)
    event = _event({"external_msg_id": "x"})

    # PQRS común sin metadata específica.
    await insert_pqrs_caso(event, _clasif("PETICION"), pool)
    args = conn.fetchval.await_args[0]
    assert args[15] is None  # documento_peticionante_hash


@pytest.mark.asyncio
async def test_doc_hash_null_si_accionante_sin_hash():
    expected_id = uuid.uuid4()
    pool, conn = _mock_pool(expected_id)
    event = _event({"external_msg_id": "x"})
    metadata = {
        "tipo_actuacion": "AUTO_ADMISORIO",
        "accionante": {"tipo_documento": "CC"},  # sin documento_hash
    }
    await insert_pqrs_caso(event, _clasif("TUTELA"), pool, metadata_especifica=metadata)
    args = conn.fetchval.await_args[0]
    assert args[15] is None


@pytest.mark.asyncio
async def test_doc_hash_null_si_accionante_no_es_dict():
    """Defensa: si el extractor falló y accionante quedó como string, no rompe."""
    expected_id = uuid.uuid4()
    pool, conn = _mock_pool(expected_id)
    event = _event({"external_msg_id": "x"})
    metadata = {"tipo_actuacion": "AUTO_ADMISORIO", "accionante": "raw_string"}
    await insert_pqrs_caso(event, _clasif("TUTELA"), pool, metadata_especifica=metadata)
    args = conn.fetchval.await_args[0]
    assert args[15] is None
