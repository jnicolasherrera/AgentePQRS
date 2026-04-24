"""Tests unitarios de tutela_extractor (mocks 100% de AsyncAnthropic)."""
from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.enrichers import ENRICHERS, enrich_by_tipo
from app.services.enrichers.tutela_extractor import (
    _hash_documento,
    enrich_tutela,
)


TENANT = uuid.UUID("00000000-0001-0001-0001-000000000001")
FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "tutelas")


def _load_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return f.read()


def _mock_response(tool_input: dict) -> MagicMock:
    """Construye un mock de respuesta Claude con un solo bloque tool_use."""
    block = MagicMock()
    block.type = "tool_use"
    block.input = tool_input
    response = MagicMock()
    response.content = [block]
    return response


def _event(fixture_text: str) -> dict:
    return {
        "tenant_id": str(TENANT),
        "correlation_id": "00000000-0000-0000-0000-000000000001",
        "subject": "Asunto tutela test",
        "body": fixture_text,
        "sender": "juzgado01@fixture.invalid",
        "date": "2026-04-23T10:00:00+00:00",
    }


# ── Auto-registro ────────────────────────────────────────────────────

def test_tutela_enricher_autoregistrado():
    assert "TUTELA" in ENRICHERS
    assert ENRICHERS["TUTELA"] is enrich_tutela


# ── Fixture 01 — AUTO_ADMISORIO con plazo HABILES estándar ──────────

@pytest.mark.asyncio
async def test_fixture_01_plazo_habiles_standard():
    fixture_text = _load_fixture("01_auto_admisorio_simple.txt")
    tool_input = {
        "numero_expediente": "11001-3103-001-2026-00123-00",
        "despacho": {"nombre": "Juzgado Tres Penal Municipal", "ciudad": "Bogotá D.C."},
        "tipo_actuacion": "AUTO_ADMISORIO",
        "fecha_auto": "2026-04-22",
        "plazo_informe_horas": 16,
        "plazo_tipo": "HABILES",
        "derechos_invocados": ["derecho de petición", "debido proceso"],
        "_confidence": {
            "plazo_informe_horas": 0.95,
            "numero_expediente": 0.92,
            "tipo_actuacion": 0.98,
        },
    }

    with patch("anthropic.AsyncAnthropic") as mock_cls, \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
        mock_inst = mock_cls.return_value
        mock_inst.messages.create = AsyncMock(return_value=_mock_response(tool_input))

        result = await enrich_tutela(_event(fixture_text), clasificacion=None)

    assert result["tipo_actuacion"] == "AUTO_ADMISORIO"
    assert result["plazo_informe_horas"] == 16
    assert result["plazo_tipo"] == "HABILES"
    # Confidence alto → NO debe requerir revisión humana.
    assert not result.get("_requiere_revision_humana")
    assert result["_synthetic_fixture"] == "SYNTHETIC_FIXTURE_V1"


# ── Fixture 02 — plazo ambiguo + medida provisional ─────────────────

@pytest.mark.asyncio
async def test_fixture_02_plazo_ambiguo_flag_revision():
    fixture_text = _load_fixture("02_auto_con_medida_provisional.txt")
    tool_input = {
        "numero_expediente": "05001-4003-005-2026-00047-00",
        "despacho": {"nombre": "Juzgado Cinco Civil Municipal", "ciudad": "Medellín"},
        "tipo_actuacion": "AUTO_ADMISORIO",
        "fecha_auto": "2026-04-23",
        "plazo_informe_horas": 48,  # default porque era ambiguo
        "plazo_tipo": "HABILES",
        "medidas_provisionales": [
            {
                "descripcion": "Entrega de medicamentos de alto costo",
                "plazo_horas": 24,
                "plazo_tipo": "CALENDARIO",
                "fecha_auto": "2026-04-23",
            }
        ],
        "_confidence": {
            "plazo_informe_horas": 0.45,  # BAJO porque el plazo era ambiguo
            "tipo_actuacion": 0.90,
        },
    }

    with patch("anthropic.AsyncAnthropic") as mock_cls, \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
        mock_inst = mock_cls.return_value
        mock_inst.messages.create = AsyncMock(return_value=_mock_response(tool_input))

        result = await enrich_tutela(_event(fixture_text), clasificacion=None)

    # Confidence bajo → flag de revisión humana debe estar true.
    assert result.get("_requiere_revision_humana") is True
    # Medida provisional preservada.
    assert result["medidas_provisionales"][0]["plazo_horas"] == 24
    assert result["medidas_provisionales"][0]["plazo_tipo"] == "CALENDARIO"


# ── Fixture 03 — FALLO_PRIMERA sin plazo de informe ─────────────────

@pytest.mark.asyncio
async def test_fixture_03_fallo_primera_tolera_ausencia_plazo():
    fixture_text = _load_fixture("03_fallo_primera_instancia.txt")
    tool_input = {
        "numero_expediente": "76001-3105-007-2026-00089-00",
        "despacho": {"nombre": "Juzgado Siete Laboral del Circuito", "ciudad": "Cali"},
        "tipo_actuacion": "FALLO_PRIMERA",
        "fecha_auto": "2026-04-24",
        "plazo_informe_horas": 48,  # default; este fallo no tiene plazo de informe
        "plazo_tipo": "HABILES",
        "sentido_fallo": "CONCEDIDA",
        "_confidence": {"plazo_informe_horas": 0.30, "tipo_actuacion": 0.95},
    }

    with patch("anthropic.AsyncAnthropic") as mock_cls, \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
        mock_inst = mock_cls.return_value
        mock_inst.messages.create = AsyncMock(return_value=_mock_response(tool_input))

        result = await enrich_tutela(_event(fixture_text), clasificacion=None)

    assert result["tipo_actuacion"] == "FALLO_PRIMERA"
    assert result.get("sentido_fallo") == "CONCEDIDA"
    # Plazo confidence bajo → flag revisión humana.
    assert result.get("_requiere_revision_humana") is True


# ── documento_raw → hash + borrado ───────────────────────────────────

@pytest.mark.asyncio
async def test_documento_raw_hasheado_y_borrado():
    tool_input = {
        "tipo_actuacion": "AUTO_ADMISORIO",
        "plazo_informe_horas": 16,
        "plazo_tipo": "HABILES",
        "accionante": {"documento_raw": "1012345678", "tipo_documento": "CC"},
        "_confidence": {"plazo_informe_horas": 0.9},
    }

    with patch("anthropic.AsyncAnthropic") as mock_cls, \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
        mock_inst = mock_cls.return_value
        mock_inst.messages.create = AsyncMock(return_value=_mock_response(tool_input))

        result = await enrich_tutela(_event("body sin marker"), clasificacion=None)

    accionante = result["accionante"]
    # Raw borrado.
    assert "documento_raw" not in accionante
    # Hash presente (SHA-256 hex = 64 chars).
    assert "documento_hash" in accionante
    assert len(accionante["documento_hash"]) == 64


def test_hash_determinstico_y_salt_sensitive():
    h1 = _hash_documento("1012345678", "salt_A")
    h2 = _hash_documento("1012345678", "salt_A")
    h3 = _hash_documento("1012345678", "salt_B")
    assert h1 == h2
    assert h1 != h3


# ── Excepción del cliente Anthropic → fallback ──────────────────────

@pytest.mark.asyncio
async def test_excepcion_anthropic_fallback():
    with patch("anthropic.AsyncAnthropic") as mock_cls, \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
        mock_inst = mock_cls.return_value
        mock_inst.messages.create = AsyncMock(side_effect=RuntimeError("boom"))

        result = await enrich_tutela(_event("body"), clasificacion=None)

    assert result["_extraction_failed"] is True
    assert "boom" in result["_error"]
    assert result["_requiere_revision_humana"] is True
    assert result["plazo_informe_horas"] == 48
    assert result["plazo_tipo"] == "HABILES"


# ── Sin API key → fallback sin llamar al cliente ────────────────────

@pytest.mark.asyncio
async def test_sin_api_key_fallback():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
        result = await enrich_tutela(_event("body"), clasificacion=None)
    assert result["_extraction_failed"] is True
    assert result["_error"] == "no_api_key"


# ── dispatcher enrich_by_tipo ────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatcher_tipo_sin_enricher_retorna_vacio():
    result = await enrich_by_tipo("PETICION", {}, None)
    assert result == {}


@pytest.mark.asyncio
async def test_dispatcher_enricher_lanza_retorna_failed():
    # Enricher sintético que falla para cualquier tipo_caso "FAIL_TEST".
    async def fails(event, clasificacion):
        raise ValueError("forced")

    ENRICHERS["FAIL_TEST"] = fails
    try:
        result = await enrich_by_tipo("FAIL_TEST", {}, None)
        assert result["_enrichment_failed"] is True
        assert "forced" in result["_error"]
    finally:
        ENRICHERS.pop("FAIL_TEST", None)
