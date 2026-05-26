"""Tests del ab_test_engine (Fase 4 A/B shadow mode).

Mockean Claude (no toca API real) y la conexión asyncpg.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ab_test_engine import (
    generar_borrador_sin_rag,
    persistir_variant,
    registrar_shadow_para_caso,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

TENANT = "11111111-1111-1111-1111-111111111111"
CASO   = "22222222-2222-2222-2222-222222222222"


def _fake_anthropic_response(texto: str, tokens_in: int = 100, tokens_out: int = 150):
    resp = MagicMock()
    resp.content = [MagicMock(text=texto)]
    resp.usage = MagicMock(input_tokens=tokens_in, output_tokens=tokens_out)
    return resp


def _fake_conn():
    c = MagicMock()
    c.execute = AsyncMock(return_value="OK")
    return c


# --------------------------------------------------------------------------- #
# generar_borrador_sin_rag (baseline)
# --------------------------------------------------------------------------- #

class TestBaselineGenerator:
    @pytest.mark.asyncio
    async def test_happy_path(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        fake_create = AsyncMock(return_value=_fake_anthropic_response("Borrador baseline."))
        fake_cls = MagicMock()
        fake_cls.return_value.messages.create = fake_create
        with patch("anthropic.AsyncAnthropic", fake_cls):
            texto, meta = await generar_borrador_sin_rag(
                "Asunto tutela", "Cuerpo del caso.", "TUTELA", "Juan",
            )
        assert texto == "Borrador baseline."
        assert meta["modelo"] == "claude-haiku-4-5-20251001"
        assert meta["tokens_in"] == 100
        assert meta["tokens_out"] == 150
        assert meta["latencia_ms"] >= 0

    @pytest.mark.asyncio
    async def test_sin_api_key_devuelve_none(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        texto, meta = await generar_borrador_sin_rag("a", "b", "TUTELA", None)
        assert texto is None
        assert meta == {"error": "no_anthropic_key"}

    @pytest.mark.asyncio
    async def test_anthropic_falla_degrada(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
        fake_create = AsyncMock(side_effect=RuntimeError("api down"))
        fake_cls = MagicMock()
        fake_cls.return_value.messages.create = fake_create
        with patch("anthropic.AsyncAnthropic", fake_cls):
            texto, meta = await generar_borrador_sin_rag("a", "b", "TUTELA", None)
        assert texto is None
        assert "api down" in meta["error"]
        assert meta["latencia_ms"] >= 0

    @pytest.mark.asyncio
    async def test_tipo_caso_desconocido_usa_solicitud(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
        fake_create = AsyncMock(return_value=_fake_anthropic_response("x"))
        fake_cls = MagicMock()
        fake_cls.return_value.messages.create = fake_create
        with patch("anthropic.AsyncAnthropic", fake_cls):
            await generar_borrador_sin_rag("a", "b", "TIPO_INEXISTENTE", None)
        # system prompt usado debe ser el de SOLICITUD
        system = fake_create.call_args.kwargs["system"]
        assert "solicitud" in system.lower() or "cordial" in system.lower()


# --------------------------------------------------------------------------- #
# persistir_variant
# --------------------------------------------------------------------------- #

class TestPersistirVariant:
    @pytest.mark.asyncio
    async def test_persiste_with_rag(self):
        conn = _fake_conn()
        await persistir_variant(
            conn, CASO, TENANT, "with_rag", "Contenido oficial",
            rag_docs=[{"source_type": "normativa", "source_id": "x", "sim_score": 0.6}],
            tipo_caso="TUTELA", modelo="claude-haiku-4-5", tokens_in=120, tokens_out=400,
            latencia_ms=3500,
        )
        sql = conn.execute.call_args.args[0]
        args = conn.execute.call_args.args[1:]
        assert "INSERT INTO ab_test_borradores" in sql
        assert "ON CONFLICT (caso_id, variant)" in sql
        assert args[2] == "with_rag"
        assert args[3] == "Contenido oficial"
        # rag_docs serialized as JSON string
        assert "normativa" in args[4] and "0.6" in args[4]

    @pytest.mark.asyncio
    async def test_persiste_no_rag(self):
        conn = _fake_conn()
        await persistir_variant(conn, CASO, TENANT, "no_rag", "Baseline", tipo_caso="QUEJA")
        assert conn.execute.call_args.args[3] == "no_rag"

    @pytest.mark.asyncio
    async def test_variant_invalida_rechazada(self):
        conn = _fake_conn()
        with pytest.raises(ValueError, match="variant inválida"):
            await persistir_variant(conn, CASO, TENANT, "control", "x")
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_contenido_vacio_no_persiste(self):
        conn = _fake_conn()
        await persistir_variant(conn, CASO, TENANT, "with_rag", "")
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_falla_no_propaga(self):
        """A/B nunca debe romper el flow productivo del worker."""
        conn = MagicMock()
        conn.execute = AsyncMock(side_effect=RuntimeError("pg down"))
        # No debe levantar
        await persistir_variant(conn, CASO, TENANT, "with_rag", "x")


# --------------------------------------------------------------------------- #
# registrar_shadow_para_caso
# --------------------------------------------------------------------------- #

class TestRegistrarShadowParaCaso:
    @pytest.mark.asyncio
    async def test_happy_path(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
        fake_create = AsyncMock(return_value=_fake_anthropic_response("Shadow.", 80, 200))
        fake_cls = MagicMock()
        fake_cls.return_value.messages.create = fake_create
        conn = _fake_conn()
        with patch("anthropic.AsyncAnthropic", fake_cls):
            await registrar_shadow_para_caso(
                conn, CASO, TENANT,
                "Asunto", "Cuerpo", "TUTELA", "Juan",
            )
        # debe haber persistido la variant no_rag
        assert conn.execute.call_count == 1
        args = conn.execute.call_args.args[1:]
        assert args[2] == "no_rag"
        assert args[3] == "Shadow."
        assert args[7] == 80    # tokens_in
        assert args[8] == 200   # tokens_out

    @pytest.mark.asyncio
    async def test_anthropic_falla_no_persiste_no_propaga(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
        fake_create = AsyncMock(side_effect=RuntimeError("down"))
        fake_cls = MagicMock()
        fake_cls.return_value.messages.create = fake_create
        conn = _fake_conn()
        with patch("anthropic.AsyncAnthropic", fake_cls):
            await registrar_shadow_para_caso(conn, CASO, TENANT, "a", "b", "TUTELA", None)
        # no debe haber insertado nada — texto vino None
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_sin_anthropic_key_no_persiste(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        conn = _fake_conn()
        await registrar_shadow_para_caso(conn, CASO, TENANT, "a", "b", "TUTELA", None)
        conn.execute.assert_not_called()
