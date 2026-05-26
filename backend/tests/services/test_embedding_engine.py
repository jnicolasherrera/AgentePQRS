"""Tests del embedding_engine (Voyage AI wrapper).

Sin tocar la API real: mockean voyageai.AsyncClient.embed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.embedding_engine import (
    DEFAULT_MODEL,
    EmbeddingAuthError,
    EmbeddingEngine,
    EmbeddingError,
    EmbeddingRateLimitError,
    EmbeddingResult,
    EmbeddingTransientError,
    _classify_exception,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _fake_response(vectors: list[list[float]], tokens: int):
    """Mimics voyageai.AsyncClient.embed() result object."""
    obj = MagicMock()
    obj.embeddings = vectors
    obj.total_tokens = tokens
    return obj


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    return EmbeddingEngine()


# --------------------------------------------------------------------------- #
# Setup / init
# --------------------------------------------------------------------------- #

class TestInit:
    def test_sin_api_key_levanta_auth_error(self, monkeypatch):
        monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
        with pytest.raises(EmbeddingAuthError, match="VOYAGE_API_KEY"):
            EmbeddingEngine()

    def test_api_key_explicita(self):
        e = EmbeddingEngine(api_key="explicit-key")
        assert e.model == DEFAULT_MODEL

    def test_modelo_default_es_multilingual_v2(self, engine):
        assert engine.model == "voyage-multilingual-2"


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #

class TestEmbedTextsHappyPath:
    @pytest.mark.asyncio
    async def test_un_texto(self, engine):
        with patch.object(engine._client, "embed",
                          new=AsyncMock(return_value=_fake_response([[0.1] * 1024], tokens=4))):
            res = await engine.embed_texts(["hola"])
        assert isinstance(res, EmbeddingResult)
        assert len(res.vectors) == 1
        assert len(res.vectors[0]) == 1024
        assert res.total_tokens == 4
        assert res.model == "voyage-multilingual-2"

    @pytest.mark.asyncio
    async def test_lista_vacia_no_llama_api(self, engine):
        with patch.object(engine._client, "embed", new=AsyncMock()) as m:
            res = await engine.embed_texts([])
        assert res.vectors == []
        assert res.total_tokens == 0
        m.assert_not_called()

    @pytest.mark.asyncio
    async def test_input_type_query_se_propaga(self, engine):
        mock = AsyncMock(return_value=_fake_response([[0.1] * 1024], tokens=3))
        with patch.object(engine._client, "embed", new=mock):
            await engine.embed_texts(["query test"], input_type="query")
        kwargs = mock.call_args.kwargs
        assert kwargs["input_type"] == "query"
        assert kwargs["model"] == "voyage-multilingual-2"

    @pytest.mark.asyncio
    async def test_input_type_document_es_default(self, engine):
        mock = AsyncMock(return_value=_fake_response([[0.1] * 1024], tokens=3))
        with patch.object(engine._client, "embed", new=mock):
            await engine.embed_texts(["doc"])
        assert mock.call_args.kwargs["input_type"] == "document"


# --------------------------------------------------------------------------- #
# Batching: cuando hay > MAX_BATCH_SIZE chunkear y sumar tokens.
# --------------------------------------------------------------------------- #

class TestBatching:
    @pytest.mark.asyncio
    async def test_chunkea_cuando_excede_batch(self, engine):
        # 130 textos → 2 batches (128 + 2)
        textos = [f"t{i}" for i in range(130)]
        responses = [
            _fake_response([[0.1] * 1024] * 128, tokens=128),
            _fake_response([[0.2] * 1024] * 2,   tokens=2),
        ]
        with patch.object(engine._client, "embed",
                          new=AsyncMock(side_effect=responses)) as m:
            res = await engine.embed_texts(textos)
        assert m.call_count == 2
        assert len(res.vectors) == 130
        assert res.total_tokens == 130
        # primer batch tuvo 128 textos, segundo 2
        assert len(m.call_args_list[0].kwargs["texts"]) == 128
        assert len(m.call_args_list[1].kwargs["texts"]) == 2


# --------------------------------------------------------------------------- #
# Errores
# --------------------------------------------------------------------------- #

class TestErrores:
    @pytest.mark.asyncio
    async def test_textos_vacios_rechazados(self, engine):
        with pytest.raises(EmbeddingError, match="Textos vacíos"):
            await engine.embed_texts(["valido", "", "  "])

    @pytest.mark.asyncio
    async def test_auth_error_no_reintenta(self, engine):
        mock = AsyncMock(side_effect=Exception("401 Unauthorized: invalid api key"))
        with patch.object(engine._client, "embed", new=mock):
            with pytest.raises(EmbeddingAuthError):
                await engine.embed_texts(["x"])
        assert mock.call_count == 1  # NO reintentó

    @pytest.mark.asyncio
    async def test_rate_limit_reintenta_y_luego_levanta(self, engine, monkeypatch):
        # Acelerar el sleep para que el test no tarde 47s.
        async def _no_sleep(_):
            return None
        monkeypatch.setattr("app.services.embedding_engine.asyncio.sleep", _no_sleep)

        mock = AsyncMock(side_effect=Exception("429 rate limit exceeded"))
        with patch.object(engine._client, "embed", new=mock):
            with pytest.raises(EmbeddingRateLimitError, match="5 reintentos"):
                await engine.embed_texts(["x"])
        assert mock.call_count == 5  # MAX_RETRIES

    @pytest.mark.asyncio
    async def test_transient_recupera_en_2do_intento(self, engine, monkeypatch):
        async def _no_sleep(_):
            return None
        monkeypatch.setattr("app.services.embedding_engine.asyncio.sleep", _no_sleep)

        mock = AsyncMock(side_effect=[
            Exception("503 service unavailable"),
            _fake_response([[0.5] * 1024], tokens=3),
        ])
        with patch.object(engine._client, "embed", new=mock):
            res = await engine.embed_texts(["x"])
        assert mock.call_count == 2
        assert res.total_tokens == 3


# --------------------------------------------------------------------------- #
# Clasificación de excepciones
# --------------------------------------------------------------------------- #

class TestClassifyException:
    @pytest.mark.parametrize("msg,expected", [
        ("401 Unauthorized",            "auth"),
        ("invalid api key",             "auth"),
        ("403 Forbidden",               "auth"),
        ("429 rate limit exceeded",     "rate_limit"),
        ("Rate limit reached",          "rate_limit"),
        ("Too many requests, retry later", "rate_limit"),
        ("503 service unavailable",     "transient"),
        ("Connection reset by peer",    "transient"),
        # bug_005: estos antes se clasificaban mal como rate_limit por "limit"
        ("token limit exceeded for input", "transient"),
        ("context length limit reached",   "transient"),
        ("max input length is 32000",      "transient"),
        ("batch size limit is 1000",       "transient"),
    ])
    def test_clasifica_msg(self, msg, expected):
        assert _classify_exception(Exception(msg)) == expected

    def test_none_es_unknown(self):
        assert _classify_exception(None) == "unknown"
