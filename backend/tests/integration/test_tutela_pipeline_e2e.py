"""
Tests integración E2E del pipeline tutela con asyncpg + AsyncAnthropic mockeados.

6 escenarios oficiales del sprint Tutelas v3:
1. TUTELA con extractor exitoso, sin matches → caso creado, vinculación None.
2. TUTELA con 1 match PQRS previo → caso creado + metadata.vinculacion='PQRS_NO_CONTESTADO'.
3. TUTELA con múltiples matches → metadata.vinculacion='MULTIPLE_MATCHES'.
4. TUTELA con extracción fallida → fallback dict, fecha_vencimiento por trigger DB.
5. TUTELA con medida provisional plazo CALENDARIO → trigger DB calcula vencimiento del informe principal; medida persistida en metadata.
6. TUTELA con plazo CALENDARIO 24h → sla_engine calcula fecha_recibido + 24h.

Mocks: AsyncAnthropic + asyncpg.Pool/Connection. NO toca DB real.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_classifier import ClassificationResult


TENANT = uuid.UUID("00000000-0001-0001-0001-000000000001")


def _clasif_tutela() -> ClassificationResult:
    return ClassificationResult(
        tipo_caso="TUTELA", prioridad="ALTA", plazo_dias=2,
        cedula=None, nombre_cliente=None, es_juzgado=True,
        confianza=0.95, borrador=None,
    )


def _event(extra: dict | None = None) -> dict:
    base = {
        "tenant_id": str(TENANT),
        "correlation_id": str(uuid.uuid4()),
        "subject": "Tutela test E2E",
        "body": "SYNTHETIC_FIXTURE_V1\nAcción de tutela. Plazo 2 días hábiles.\nDocumento accionante: 1011223344.",
        "sender": "juzgado@fixture.invalid",
        "date": "2026-04-27T10:00:00+00:00",
        "external_msg_id": f"E2E-{uuid.uuid4().hex[:12]}",
    }
    if extra:
        base.update(extra)
    return base


def _mock_pool_with_inserter() -> tuple[MagicMock, AsyncMock]:
    """Pool/conn falsos. fetchval del INSERT retorna un caso_id nuevo."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=uuid.uuid4())
    conn.fetchrow = AsyncMock(return_value=None)  # _round_robin_analista
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value=None)

    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=cm)
    return pool, conn


def _mock_claude_response(input_dict: dict) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.input = input_dict
    response = MagicMock()
    response.content = [block]
    return response


# ── Escenario 1 — TUTELA exitosa, sin matches de vinculación ─────────

@pytest.mark.asyncio
async def test_e2e_tutela_sin_matches_vinculacion():
    pool, conn = _mock_pool_with_inserter()
    extracted = {
        "tipo_actuacion": "AUTO_ADMISORIO",
        "plazo_informe_horas": 16, "plazo_tipo": "HABILES",
        "accionante": {"documento_raw": "1011223344", "tipo_documento": "CC"},
        "_confidence": {"plazo_informe_horas": 0.95},
    }
    with patch("anthropic.AsyncAnthropic") as mock_cls, \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
        mock_cls.return_value.messages.create = AsyncMock(
            return_value=_mock_claude_response(extracted)
        )
        from app.services import pipeline as pl
        # vinculación retorna None → conn.fetch para vinculación devuelve []
        caso_id = await pl.process_classified_event(
            _clasif_tutela(), _event(), TENANT, conn, pool,
        )

    assert caso_id is not None
    # Verificar que el INSERT se invocó.
    assert conn.fetchval.await_count >= 1
    # external_msg_id en argumentos del INSERT (índice 14).
    insert_args = conn.fetchval.await_args[0]
    assert insert_args[14] is not None  # external_msg_id propagado
    # documento_peticionante_hash en $15 (extractor lo hasheó).
    assert insert_args[15] is not None and len(insert_args[15]) == 64


# ── Escenario 2 — TUTELA con 1 match → PQRS_NO_CONTESTADO ───────────

@pytest.mark.asyncio
async def test_e2e_tutela_un_match_pqrs_no_contestado():
    pool, conn = _mock_pool_with_inserter()
    extracted = {
        "tipo_actuacion": "AUTO_ADMISORIO",
        "plazo_informe_horas": 16, "plazo_tipo": "HABILES",
        "accionante": {"documento_raw": "9999", "tipo_documento": "CC"},
        "_confidence": {"plazo_informe_horas": 0.92},
    }
    # Simulamos que vinculacion encuentra 1 match sin enviado_at.
    prev_pqrs_row = {
        "id": uuid.uuid4(),
        "numero_radicado": "PQRS-2026-AAAAAA",
        "tipo_caso": "QUEJA",
        "estado": "ABIERTO",
        "fecha_recibido": datetime(2026, 4, 1, tzinfo=timezone.utc),
        "enviado_at": None,
    }
    # `vinculacion.vincular_con_pqrs_previo` usa `conn.fetch` para la query y
    # `conn.execute` para el UPDATE. Configuramos ambos.
    conn.fetch = AsyncMock(return_value=[prev_pqrs_row])

    with patch("anthropic.AsyncAnthropic") as mock_cls, \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
        mock_cls.return_value.messages.create = AsyncMock(
            return_value=_mock_claude_response(extracted)
        )
        from app.services import pipeline as pl
        caso_id = await pl.process_classified_event(
            _clasif_tutela(), _event(), TENANT, conn, pool,
        )

    # vinculacion debe haber ejecutado el UPDATE de metadata con motivo PQRS_NO_CONTESTADO.
    update_calls = [c for c in conn.execute.await_args_list
                    if c.args and "metadata_especifica" in (c.args[0] or "")]
    assert len(update_calls) >= 1, "vinculacion no actualizó metadata"
    # Verificar el JSONB con el motivo.
    payload = update_calls[0].args[1]
    parsed = json.loads(payload)
    assert parsed["motivo"] == "PQRS_NO_CONTESTADO"


# ── Escenario 3 — TUTELA con múltiples matches → MULTIPLE_MATCHES ───

@pytest.mark.asyncio
async def test_e2e_tutela_multiples_matches():
    pool, conn = _mock_pool_with_inserter()
    extracted = {
        "tipo_actuacion": "AUTO_ADMISORIO",
        "plazo_informe_horas": 16, "plazo_tipo": "HABILES",
        "accionante": {"documento_raw": "1234", "tipo_documento": "CC"},
        "_confidence": {"plazo_informe_horas": 0.9},
    }
    matches = [
        {"id": uuid.uuid4(), "numero_radicado": f"PQRS-{i}", "tipo_caso": "QUEJA",
         "estado": "ABIERTO", "fecha_recibido": datetime(2026, 4, 1, tzinfo=timezone.utc),
         "enviado_at": None}
        for i in range(3)
    ]
    conn.fetch = AsyncMock(return_value=matches)

    with patch("anthropic.AsyncAnthropic") as mock_cls, \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
        mock_cls.return_value.messages.create = AsyncMock(
            return_value=_mock_claude_response(extracted)
        )
        from app.services import pipeline as pl
        await pl.process_classified_event(
            _clasif_tutela(), _event(), TENANT, conn, pool,
        )

    update_calls = [c for c in conn.execute.await_args_list
                    if c.args and "metadata_especifica" in (c.args[0] or "")]
    assert len(update_calls) >= 1
    parsed = json.loads(update_calls[0].args[1])
    assert parsed["motivo"] == "MULTIPLE_MATCHES"
    assert len(parsed["matches_ids"]) == 3


# ── Escenario 4 — Extracción falla → fallback, fecha por trigger ────

@pytest.mark.asyncio
async def test_e2e_tutela_extraccion_falla_fallback():
    pool, conn = _mock_pool_with_inserter()
    with patch("anthropic.AsyncAnthropic") as mock_cls, \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
        # Claude lanza excepción → enrich_tutela cae al fallback defensivo.
        mock_cls.return_value.messages.create = AsyncMock(side_effect=RuntimeError("rate limit"))
        from app.services import pipeline as pl
        await pl.process_classified_event(
            _clasif_tutela(), _event(), TENANT, conn, pool,
        )

    insert_args = conn.fetchval.await_args[0]
    # metadata_especifica ($12) tiene _extraction_failed=True.
    metadata_payload = insert_args[12]
    metadata = json.loads(metadata_payload)
    assert metadata.get("_extraction_failed") is True
    assert metadata.get("_requiere_revision_humana") is True
    # fecha_vencimiento ($13) None → trigger DB se encarga.
    assert insert_args[13] is None


# ── Escenario 5 — Medida provisional plazo CALENDARIO ────────────────

@pytest.mark.asyncio
async def test_e2e_tutela_con_medida_provisional():
    pool, conn = _mock_pool_with_inserter()
    extracted = {
        "tipo_actuacion": "AUTO_ADMISORIO",
        "plazo_informe_horas": 48, "plazo_tipo": "HABILES",
        "medidas_provisionales": [
            {"descripcion": "Entrega medicamento",
             "plazo_horas": 24, "plazo_tipo": "CALENDARIO",
             "fecha_auto": "2026-04-27"}
        ],
        "accionante": {"documento_raw": "5050", "tipo_documento": "CC"},
        "_confidence": {"plazo_informe_horas": 0.88},
    }
    with patch("anthropic.AsyncAnthropic") as mock_cls, \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
        mock_cls.return_value.messages.create = AsyncMock(
            return_value=_mock_claude_response(extracted)
        )
        from app.services import pipeline as pl
        await pl.process_classified_event(
            _clasif_tutela(), _event(), TENANT, conn, pool,
        )

    insert_args = conn.fetchval.await_args[0]
    metadata = json.loads(insert_args[12])
    assert metadata.get("medidas_provisionales")
    assert metadata["medidas_provisionales"][0]["plazo_horas"] == 24


# ── Escenario 6 — TUTELA plazo CALENDARIO 24h → sla_engine calcula ──

@pytest.mark.asyncio
async def test_e2e_tutela_calendario_sla_engine_calcula():
    pool, conn = _mock_pool_with_inserter()
    extracted = {
        "tipo_actuacion": "AUTO_ADMISORIO",
        "plazo_informe_horas": 24, "plazo_tipo": "CALENDARIO",
        "accionante": {"documento_raw": "1717", "tipo_documento": "CC"},
        "_confidence": {"plazo_informe_horas": 0.97},
    }
    with patch("anthropic.AsyncAnthropic") as mock_cls, \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
        mock_cls.return_value.messages.create = AsyncMock(
            return_value=_mock_claude_response(extracted)
        )
        from app.services import pipeline as pl
        await pl.process_classified_event(
            _clasif_tutela(), _event({"date": "2026-04-27T10:00:00+00:00"}), TENANT, conn, pool,
        )

    insert_args = conn.fetchval.await_args[0]
    fecha_venc = insert_args[13]
    assert fecha_venc is not None
    # CALENDARIO 24h desde 2026-04-27 10:00 → 2026-04-28 10:00.
    expected = datetime(2026, 4, 28, 10, 0, tzinfo=timezone.utc)
    assert fecha_venc == expected, f"esperado {expected}, recibido {fecha_venc}"
