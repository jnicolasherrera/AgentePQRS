"""
Test de carga liviana: 50 tutelas en lote, Claude mockeado.

Verifica:
- pipeline procesa 50 eventos sin crashear.
- Tiempo total razonable (con Claude mockeado, p50 << 8s; este test no mide
  Claude real, mide el resto del pipeline + asyncpg mock + sla_engine).
- Cada uno termina con caso_id único.
- No hay leaks de memoria evidentes (ej. el dict ENRICHERS no crece).

NO consume Claude real. NO toca DB real.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_classifier import ClassificationResult
from app.services.enrichers import ENRICHERS


TENANT = uuid.UUID("00000000-0001-0001-0001-000000000001")


def _clasif() -> ClassificationResult:
    return ClassificationResult(
        tipo_caso="TUTELA", prioridad="ALTA", plazo_dias=2,
        cedula=None, nombre_cliente=None, es_juzgado=True,
        confianza=0.92, borrador=None,
    )


def _event(idx: int) -> dict:
    return {
        "tenant_id": str(TENANT),
        "correlation_id": str(uuid.uuid4()),
        "subject": f"Tutela burst #{idx}",
        "body": "SYNTHETIC_FIXTURE_V1\nAcción de tutela. Plazo 2 días hábiles.",
        "sender": f"juzgado{idx}@fixture.invalid",
        "date": "2026-04-27T10:00:00+00:00",
        "external_msg_id": f"BURST-{idx:03d}",
    }


def _mock_pool_with_unique_ids(count: int) -> tuple[MagicMock, AsyncMock, list[uuid.UUID]]:
    ids = [uuid.uuid4() for _ in range(count)]
    iter_ids = iter(ids)
    conn = AsyncMock()
    conn.fetchval = AsyncMock(side_effect=lambda *a, **k: next(iter_ids))
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value=None)
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=cm)
    return pool, conn, ids


@pytest.mark.asyncio
async def test_burst_50_tutelas_pipeline_sin_crash():
    pool, conn, expected_ids = _mock_pool_with_unique_ids(50)
    extracted = {
        "tipo_actuacion": "AUTO_ADMISORIO",
        "plazo_informe_horas": 16, "plazo_tipo": "HABILES",
        "accionante": {"documento_raw": "1", "tipo_documento": "CC"},
        "_confidence": {"plazo_informe_horas": 0.93},
    }

    block = MagicMock(); block.type = "tool_use"; block.input = extracted
    response = MagicMock(); response.content = [block]

    with patch("anthropic.AsyncAnthropic") as mock_cls, \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
        mock_cls.return_value.messages.create = AsyncMock(return_value=response)

        from app.services import pipeline as pl
        t0 = time.time()
        results: list[uuid.UUID] = []
        for i in range(50):
            cid = await pl.process_classified_event(
                _clasif(), _event(i), TENANT, conn, pool,
            )
            results.append(cid)
        elapsed = time.time() - t0

    # 50 IDs únicos.
    assert len(results) == 50
    assert len(set(results)) == 50
    # Todos coinciden con los IDs que el mock prefijó.
    assert results == expected_ids

    # Tiempo razonable con Claude mockeado: <30s en env local (típico < 5s).
    assert elapsed < 30, f"burst 50 tomó {elapsed:.1f}s, demasiado"


@pytest.mark.asyncio
async def test_burst_no_crece_enrichers_dict():
    """El dict ENRICHERS debe quedar con el mismo size tras procesar muchos eventos."""
    initial_size = len(ENRICHERS)

    pool, conn, _ = _mock_pool_with_unique_ids(20)
    extracted = {
        "tipo_actuacion": "AUTO_ADMISORIO", "plazo_informe_horas": 16,
        "plazo_tipo": "HABILES", "_confidence": {"plazo_informe_horas": 0.9},
    }
    block = MagicMock(); block.type = "tool_use"; block.input = extracted
    response = MagicMock(); response.content = [block]

    with patch("anthropic.AsyncAnthropic") as mock_cls, \
         patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
        mock_cls.return_value.messages.create = AsyncMock(return_value=response)
        from app.services import pipeline as pl
        for i in range(20):
            await pl.process_classified_event(_clasif(), _event(i), TENANT, conn, pool)

    assert len(ENRICHERS) == initial_size, (
        f"ENRICHERS creció de {initial_size} a {len(ENRICHERS)} — posible leak"
    )


@pytest.mark.asyncio
async def test_burst_50_pqrs_normales_via_trigger_db():
    """Burst de 50 PQRS normales (no-TUTELA). Pipeline no llama enrich (cae al
    trigger DB). Verifica throughput + ausencia de errores."""
    pool, conn, expected_ids = _mock_pool_with_unique_ids(50)
    clasif = ClassificationResult(
        tipo_caso="QUEJA", prioridad="ALTA", plazo_dias=15,
        cedula=None, nombre_cliente=None, es_juzgado=False,
        confianza=0.85, borrador=None,
    )

    from app.services import pipeline as pl
    t0 = time.time()
    for i in range(50):
        await pl.process_classified_event(clasif, _event(i), TENANT, conn, pool)
    elapsed = time.time() - t0

    assert conn.fetchval.await_count >= 50  # 50 INSERTs
    assert elapsed < 10, f"burst 50 PQRS tomó {elapsed:.1f}s"
