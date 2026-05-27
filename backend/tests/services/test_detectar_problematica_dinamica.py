"""Tests del detector dinámico (sprint FF fix bug_016 ultrareview #11)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.plantilla_engine import detectar_problematica_dinamica


TENANT = "f7e8d9c0-b1a2-3456-7890-123456abcdef"


def _conn(rows):
    c = MagicMock()
    c.fetch = AsyncMock(return_value=rows)
    return c


class TestDetectarDinamica:
    @pytest.mark.asyncio
    async def test_hardcoded_gana_antes_de_db(self):
        """Si una regla _DETECTION_RULES matchea, se usa esa (no consulta DB)."""
        conn = _conn([])
        # 'paz y salvo' + 'rapicredit' matchea PAZ_Y_SALVO_RAPICREDIT (hardcoded)
        result = await detectar_problematica_dinamica(
            conn, TENANT,
            asunto="paz y salvo rapicredit",
            cuerpo="",
            tipo_workflow="ATENCION_CLIENTE",
        )
        assert result == "PAZ_Y_SALVO_RAPICREDIT"
        conn.fetch.assert_not_called()  # short-circuit, no DB query

    @pytest.mark.asyncio
    async def test_db_match_cuando_hardcoded_no_matchea(self):
        """Si hardcoded no matchea, query DB y devuelve slug DB."""
        conn = _conn([
            {"problematica": "PEDIDO_PAZ_Y_SALVO",
             "keywords": ["paz y salvo", "certificado de cancelación"]},
            {"problematica": "COMPROBANTE_RECIBIDO",
             "keywords": ["comprobante de pago", "adjunto comprobante"]},
        ])
        result = await detectar_problematica_dinamica(
            conn, TENANT,
            asunto="Adjunto comprobante de pago",
            cuerpo="Para que actualicen",
            tipo_workflow="ATENCION_CLIENTE",
        )
        assert result == "COMPROBANTE_RECIBIDO"
        # SQL incluye filtro tipo_workflow
        sql = conn.fetch.call_args.args[0]
        assert "tipo_workflow = $2" in sql
        assert "is_active = TRUE" in sql

    @pytest.mark.asyncio
    async def test_sin_match_devuelve_none(self):
        conn = _conn([
            {"problematica": "PEDIDO_PAZ_Y_SALVO", "keywords": ["paz y salvo"]},
        ])
        result = await detectar_problematica_dinamica(
            conn, TENANT,
            asunto="Hola gente",
            cuerpo="Solo saludar",
            tipo_workflow="ATENCION_CLIENTE",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_query_db_falla_devuelve_none(self):
        """Si la query DB falla, no propaga — devuelve None."""
        conn = MagicMock()
        conn.fetch = AsyncMock(side_effect=RuntimeError("pg down"))
        result = await detectar_problematica_dinamica(
            conn, TENANT,
            asunto="x", cuerpo="y", tipo_workflow="ATENCION_CLIENTE",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_keywords_vacia_o_none_no_explota(self):
        conn = _conn([
            {"problematica": "X", "keywords": None},
            {"problematica": "Y", "keywords": []},
            {"problematica": "Z", "keywords": ["match"]},
        ])
        result = await detectar_problematica_dinamica(
            conn, TENANT,
            asunto="esto tiene un match", cuerpo="",
            tipo_workflow="ATENCION_CLIENTE",
        )
        assert result == "Z"

    @pytest.mark.asyncio
    async def test_case_insensitive(self):
        conn = _conn([
            {"problematica": "X", "keywords": ["PAZ Y SALVO"]},  # uppercase
        ])
        result = await detectar_problematica_dinamica(
            conn, TENANT,
            asunto="solicito paz y salvo",  # lowercase
            cuerpo="",
            tipo_workflow="ATENCION_CLIENTE",
        )
        assert result == "X"
