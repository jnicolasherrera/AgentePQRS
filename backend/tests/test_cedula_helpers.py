"""Tests de helpers de cedula del worker (sprint FF fix bug_020A ultrareview #11)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import sys
sys.path.insert(0, "/app")
from master_worker_outlook import _lookup_cedula_historica, _extraer_cedula_del_cuerpo


TENANT = "f7e8d9c0-b1a2-3456-7890-123456abcdef"


class TestExtraerCedula:
    @pytest.mark.parametrize("body,expected", [
        ("Mi cédula es 1.007.403.296 reclamo paz y salvo",       "1007403296"),
        ("CC 95.771.348 solicito paz",                            "95771348"),
        ("Documento: 12345678 atte juan",                         "12345678"),
        ("Soy cliente Juan, sin documentos acá",                  None),  # nada
        ("Pin 12345",                                             None),  # solo 5 dígitos
        ("",                                                       None),
        (None,                                                     None),
        ("Mi número de teléfono es 3001234567",                  "3001234567"),  # matchea (pasa filtro 6-12)
    ])
    def test_extraer(self, body, expected):
        assert _extraer_cedula_del_cuerpo(body) == expected


class TestLookupCedulaHistorica:
    @pytest.mark.asyncio
    async def test_match_devuelve_cedula(self):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"cedula": "1007403296"})
        result = await _lookup_cedula_historica(conn, TENANT, "juan@gmail.com")
        assert result == "1007403296"

    @pytest.mark.asyncio
    async def test_no_match_devuelve_none(self):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        result = await _lookup_cedula_historica(conn, TENANT, "desconocido@x.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_sender_vacio_devuelve_none_sin_query(self):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"cedula": "x"})
        result = await _lookup_cedula_historica(conn, TENANT, "")
        assert result is None
        conn.fetchrow.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_falla_devuelve_none(self):
        """Si la DB falla, no propaga — devuelve None y el caller usa fallback regex."""
        conn = MagicMock()
        conn.fetchrow = AsyncMock(side_effect=RuntimeError("db down"))
        result = await _lookup_cedula_historica(conn, TENANT, "juan@x.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_case_insensitive(self):
        """La query SQL debe usar lower() — confirmamos que pasa el sender con mayúsculas."""
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"cedula": "12345678"})
        result = await _lookup_cedula_historica(conn, TENANT, "JUAN@GMAIL.COM")
        assert result == "12345678"
        # Verificar que el SQL llamado usa lower()
        sql = conn.fetchrow.call_args.args[0]
        assert "lower(email)" in sql
        assert "lower($2)" in sql
