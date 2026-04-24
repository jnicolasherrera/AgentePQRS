"""Tests del pipeline unificador post-clasificación (sprint Tutelas)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_classifier import ClassificationResult


TENANT_ID = uuid.UUID("00000000-0001-0001-0001-000000000001")
CORR_ID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")


def _event(extra=None) -> dict:
    base = {
        "tenant_id": str(TENANT_ID),
        "correlation_id": str(CORR_ID),
        "subject": "Asunto test",
        "body": "Cuerpo test",
        "sender": "a@b.co",
        "date": "2026-04-23T10:00:00+00:00",
    }
    if extra:
        base.update(extra)
    return base


def _clasif(tipo: str = "PETICION", borrador=None) -> ClassificationResult:
    return ClassificationResult(
        tipo_caso=tipo,
        prioridad="MEDIA",
        plazo_dias=15,
        cedula=None,
        nombre_cliente=None,
        es_juzgado=False,
        confianza=0.9,
        borrador=borrador,
    )


# ── 1. PQRS sin metadata, enrich vacío, no hay vinculación ──────────

@pytest.mark.asyncio
async def test_pipeline_pqrs_sin_metadata_ni_vinculacion():
    pool = MagicMock()
    caso_id = uuid.uuid4()

    with patch("app.services.pipeline.db_inserter.insert_pqrs_caso",
               new=AsyncMock(return_value=caso_id)) as mock_insert:
        from app.services import pipeline as pl
        result = await pl.process_classified_event(
            _clasif("PETICION"),
            _event(),
            cliente_id=TENANT_ID,
            conn=AsyncMock(),
            pool=pool,
        )

    assert result == caso_id
    # Insert fue invocado con metadata_especifica=None o dict vacío, fecha_vencimiento=None.
    kwargs = mock_insert.await_args.kwargs
    assert kwargs["fecha_vencimiento"] is None


# ── 2. TUTELA con metadata CALENDARIO calcula fecha + no vincula si sin doc_hash ──

@pytest.mark.asyncio
async def test_pipeline_tutela_calendario_calcula_fecha_vencimiento():
    pool = MagicMock()
    caso_id = uuid.uuid4()
    metadata = {"plazo_informe_horas": 24, "plazo_tipo": "CALENDARIO"}

    async def mock_enrich(tipo, event, clasif):
        assert tipo == "TUTELA"
        return metadata

    with patch("app.services.pipeline.db_inserter.insert_pqrs_caso",
               new=AsyncMock(return_value=caso_id)) as mock_insert, \
         patch.dict("sys.modules", {"app.services.enrichers": MagicMock(enrich_by_tipo=mock_enrich)}):
        from app.services import pipeline as pl
        result = await pl.process_classified_event(
            _clasif("TUTELA"),
            _event(),
            cliente_id=TENANT_ID,
            conn=AsyncMock(),
            pool=pool,
        )

    assert result == caso_id
    kwargs = mock_insert.await_args.kwargs
    # Fecha calendario: 2026-04-23 10:00 + 24h = 2026-04-24 10:00.
    assert kwargs["fecha_vencimiento"] == datetime(2026, 4, 24, 10, 0, tzinfo=timezone.utc)
    assert kwargs["metadata_especifica"] == metadata


# ── 3. Extracción falla → el trigger se encarga (fecha None) ────────

@pytest.mark.asyncio
async def test_pipeline_extraccion_falla_no_calcula_fecha():
    pool = MagicMock()
    caso_id = uuid.uuid4()

    async def mock_enrich(tipo, event, clasif):
        return {"_extraction_failed": True, "_error": "timeout"}

    with patch("app.services.pipeline.db_inserter.insert_pqrs_caso",
               new=AsyncMock(return_value=caso_id)) as mock_insert, \
         patch.dict("sys.modules", {"app.services.enrichers": MagicMock(enrich_by_tipo=mock_enrich)}):
        from app.services import pipeline as pl
        result = await pl.process_classified_event(
            _clasif("TUTELA"),
            _event(),
            cliente_id=TENANT_ID,
            conn=AsyncMock(),
            pool=pool,
        )

    assert result == caso_id
    kwargs = mock_insert.await_args.kwargs
    # Con _extraction_failed, sla_engine no corre, fecha queda None (trigger la calcula).
    assert kwargs["fecha_vencimiento"] is None


# ── 4. Vinculación con doc_hash tira pero no crashea el pipeline ────

@pytest.mark.asyncio
async def test_pipeline_vinculacion_falla_pipeline_no_crashea():
    pool = MagicMock()
    caso_id = uuid.uuid4()
    metadata = {
        "plazo_informe_horas": 48,
        "plazo_tipo": "HABILES",
        "accionante": {"documento_hash": "a" * 64},
    }

    async def mock_enrich(tipo, event, clasif):
        return metadata

    async def mock_vincular(**kwargs):
        raise RuntimeError("DB unavailable")

    with patch("app.services.pipeline.db_inserter.insert_pqrs_caso",
               new=AsyncMock(return_value=caso_id)) as mock_insert, \
         patch.dict("sys.modules", {
             "app.services.enrichers": MagicMock(enrich_by_tipo=mock_enrich),
             "app.services.vinculacion": MagicMock(vincular_con_pqrs_previo=mock_vincular),
         }):
        from app.services import pipeline as pl
        # No debe propagar la excepción de vinculación.
        result = await pl.process_classified_event(
            _clasif("TUTELA"),
            _event(),
            cliente_id=TENANT_ID,
            conn=AsyncMock(),
            pool=pool,
        )

    assert result == caso_id  # pipeline completó OK.


# ── 5. enrichers no disponible (import fail) → pipeline sigue ────────

@pytest.mark.asyncio
async def test_pipeline_enrichers_import_fail_no_rompe():
    pool = MagicMock()
    caso_id = uuid.uuid4()

    # No mockeamos enrichers → ImportError dentro del try.
    with patch("app.services.pipeline.db_inserter.insert_pqrs_caso",
               new=AsyncMock(return_value=caso_id)) as mock_insert, \
         patch.dict("sys.modules", {"app.services.enrichers": None}):
        # patch.dict sys.modules con None fuerza ImportError.
        from app.services import pipeline as pl
        result = await pl.process_classified_event(
            _clasif("PETICION"),
            _event(),
            cliente_id=TENANT_ID,
            conn=AsyncMock(),
            pool=pool,
        )

    assert result == caso_id


# ── 6. pipeline sin pool falla explícitamente ────────────────────────

@pytest.mark.asyncio
async def test_pipeline_sin_pool_falla():
    from app.services import pipeline as pl
    with pytest.raises(ValueError, match="pool"):
        await pl.process_classified_event(
            _clasif("PETICION"),
            _event(),
            cliente_id=TENANT_ID,
            conn=AsyncMock(),
            pool=None,
        )
