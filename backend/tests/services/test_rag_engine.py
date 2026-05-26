"""Tests del rag_engine (retrieval del KB para Fase 3).

Mockean EmbeddingEngine y asyncpg.Connection — no tocan API ni DB reales.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.embedding_engine import EmbeddingAuthError, EmbeddingResult
from app.services.rag_engine import (
    DEFAULT_THRESHOLD,
    DEFAULT_TOP_K,
    _construir_query,
    buscar_docs_similares,
    formatear_contexto_para_prompt,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

TENANT = "11111111-1111-1111-1111-111111111111"


def _fake_engine(vectors):
    """EmbeddingEngine mock que devuelve vectors fijos."""
    e = MagicMock()
    e.embed_texts = AsyncMock(return_value=EmbeddingResult(
        vectors=vectors, total_tokens=10, model="voyage-multilingual-2",
    ))
    return e


def _fake_engine_falla(exc):
    e = MagicMock()
    e.embed_texts = AsyncMock(side_effect=exc)
    return e


def _fake_conn(rows):
    """asyncpg.Connection mock que devuelve rows fijos al fetch.

    Mockea también el async context manager `conn.transaction()` y
    `conn.execute()`, que rag_engine usa para `SET LOCAL
    hnsw.iterative_scan = relaxed_order` (bug_010).
    """
    c = MagicMock()
    c.fetch = AsyncMock(return_value=rows)
    c.execute = AsyncMock(return_value="SET")
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=False)
    c.transaction = MagicMock(return_value=tx)
    return c


def _row(source_type, source_id, sim, tipo_caso="PETICION", problematica=None, contenido="..."):
    """Fake asyncpg.Record que se convierte a dict."""
    return {
        "source_type": source_type,
        "source_id": source_id,
        "contenido": contenido,
        "tipo_caso": tipo_caso,
        "problematica": problematica,
        "sim_score": sim,
    }


# --------------------------------------------------------------------------- #
# _construir_query
# --------------------------------------------------------------------------- #

class TestConstruirQuery:
    def test_asunto_y_cuerpo(self):
        q = _construir_query("Solicitud de paz y salvo", "Buen día, requiero...")
        assert q == "Solicitud de paz y salvo\n\nBuen día, requiero..."

    def test_solo_asunto(self):
        assert _construir_query("Tutela urgente", "") == "Tutela urgente"

    def test_solo_cuerpo(self):
        assert _construir_query("", "Cuerpo del email") == "Cuerpo del email"

    def test_ambos_vacios(self):
        assert _construir_query("", "") == ""

    def test_truncar_cuerpo_largo(self):
        cuerpo = "x" * 5000
        q = _construir_query("a", cuerpo)
        # asunto + 2 newlines + 800 chars del cuerpo
        assert len(q) == 1 + 2 + 800


# --------------------------------------------------------------------------- #
# buscar_docs_similares — happy paths
# --------------------------------------------------------------------------- #

class TestBuscarDocsSimilares:
    @pytest.mark.asyncio
    async def test_retorna_docs_ordenados_por_sim(self):
        engine = _fake_engine([[0.1] * 1024])
        conn = _fake_conn([
            _row("normativa", "decreto-2591", 0.85),
            _row("normativa", "ley-1755",     0.62),
            _row("normativa", "circular-sfc", 0.41),
        ])
        docs = await buscar_docs_similares(conn, TENANT, "Tutela", "urgente", engine=engine)
        assert len(docs) == 3
        assert docs[0]["source_id"] == "decreto-2591"
        assert docs[0]["sim_score"] == 0.85

    @pytest.mark.asyncio
    async def test_filtro_por_tipo_caso_se_propaga_al_sql(self):
        engine = _fake_engine([[0.1] * 1024])
        conn = _fake_conn([])
        await buscar_docs_similares(
            conn, TENANT, "Asunto", "Cuerpo", tipo_caso="TUTELA", engine=engine,
        )
        # 5 args = vector, tenant, threshold, top_k, tipo_caso
        args = conn.fetch.call_args.args
        assert len(args) == 6  # SQL + 5 params
        assert args[5] == "TUTELA"
        # bug_004: el filtro debe ACEPTAR NULL como wildcard
        assert "tipo_caso = $5 OR tipo_caso IS NULL" in args[0]

    @pytest.mark.asyncio
    async def test_bug_004_set_local_iterative_scan(self):
        """bug_010: rag_engine debe abrir transacción y setear iterative_scan."""
        engine = _fake_engine([[0.1] * 1024])
        conn = _fake_conn([])
        await buscar_docs_similares(conn, TENANT, "a", "b", engine=engine)
        # abrió 1 transacción
        conn.transaction.assert_called_once()
        # ejecutó el SET LOCAL antes del fetch
        conn.execute.assert_awaited_once()
        set_sql = conn.execute.call_args.args[0]
        assert "hnsw.iterative_scan" in set_sql
        assert "relaxed_order" in set_sql

    @pytest.mark.asyncio
    async def test_sin_tipo_caso_no_inyecta_filtro(self):
        engine = _fake_engine([[0.1] * 1024])
        conn = _fake_conn([])
        await buscar_docs_similares(conn, TENANT, "a", "b", engine=engine)
        args = conn.fetch.call_args.args
        assert len(args) == 5  # SQL + 4 params (sin tipo)
        # 'tipo_caso' aparece en el SELECT, pero el WHERE no debe filtrar por él
        assert "tipo_caso = $5" not in args[0]
        assert "AND tipo_caso" not in args[0]

    @pytest.mark.asyncio
    async def test_threshold_default_se_aplica(self):
        engine = _fake_engine([[0.1] * 1024])
        conn = _fake_conn([])
        await buscar_docs_similares(conn, TENANT, "a", "b", engine=engine)
        args = conn.fetch.call_args.args
        assert args[3] == DEFAULT_THRESHOLD  # 3er param (después de SQL, vec, tenant)

    @pytest.mark.asyncio
    async def test_top_k_default_se_aplica(self):
        engine = _fake_engine([[0.1] * 1024])
        conn = _fake_conn([])
        await buscar_docs_similares(conn, TENANT, "a", "b", engine=engine)
        args = conn.fetch.call_args.args
        assert args[4] == DEFAULT_TOP_K


# --------------------------------------------------------------------------- #
# Degradación elegante
# --------------------------------------------------------------------------- #

class TestDegradacionElegante:
    @pytest.mark.asyncio
    async def test_query_vacia_devuelve_lista_vacia_sin_llamar_engine(self):
        engine = _fake_engine([[0.1] * 1024])
        conn = MagicMock()
        conn.fetch = AsyncMock()
        docs = await buscar_docs_similares(conn, TENANT, "", "", engine=engine)
        assert docs == []
        engine.embed_texts.assert_not_called()
        conn.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_embed_falla_devuelve_lista_vacia(self):
        engine = _fake_engine_falla(EmbeddingAuthError("bad key"))
        conn = MagicMock()
        conn.fetch = AsyncMock()
        docs = await buscar_docs_similares(conn, TENANT, "a", "b", engine=engine)
        assert docs == []
        conn.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_embed_error_generico_tambien_degrada(self):
        engine = _fake_engine_falla(RuntimeError("conn reset"))
        conn = MagicMock()
        conn.fetch = AsyncMock()
        docs = await buscar_docs_similares(conn, TENANT, "a", "b", engine=engine)
        assert docs == []

    @pytest.mark.asyncio
    async def test_db_query_falla_devuelve_lista_vacia(self):
        engine = _fake_engine([[0.1] * 1024])
        conn = MagicMock()
        conn.fetch = AsyncMock(side_effect=RuntimeError("pg down"))
        docs = await buscar_docs_similares(conn, TENANT, "a", "b", engine=engine)
        assert docs == []

    @pytest.mark.asyncio
    async def test_zero_docs_sobre_threshold_devuelve_vacio(self):
        engine = _fake_engine([[0.1] * 1024])
        conn = _fake_conn([])  # DB devuelve 0 rows
        docs = await buscar_docs_similares(conn, TENANT, "a", "b", engine=engine)
        assert docs == []


# --------------------------------------------------------------------------- #
# formatear_contexto_para_prompt
# --------------------------------------------------------------------------- #

class TestFormatearContexto:
    def test_vacio_devuelve_string_vacio(self):
        assert formatear_contexto_para_prompt([]) == ""

    def test_agrupa_por_source_type(self):
        docs = [
            _row("normativa", "n1", 0.8, contenido="Texto normativa 1"),
            _row("plantilla", "p1", 0.7, contenido="Texto plantilla 1"),
            _row("normativa", "n2", 0.6, contenido="Texto normativa 2"),
            _row("caso_enviado", "c1", 0.55, contenido="Texto caso 1"),
        ]
        texto = formatear_contexto_para_prompt(docs)
        # 3 secciones, en orden normativa → plantilla → caso_enviado
        assert "## NORMATIVA APLICABLE" in texto
        assert "## PLANTILLAS DE REFERENCIA" in texto
        assert "## CASOS RESUELTOS PREVIAMENTE" in texto
        # ambos docs de normativa están
        assert "Texto normativa 1" in texto
        assert "Texto normativa 2" in texto

    def test_incluye_score_de_similitud(self):
        docs = [_row("normativa", "n1", 0.8567, contenido="X")]
        texto = formatear_contexto_para_prompt(docs)
        assert "[similitud 0.86]" in texto

    def test_solo_un_tipo(self):
        docs = [_row("plantilla", "p1", 0.7, contenido="Plantilla única")]
        texto = formatear_contexto_para_prompt(docs)
        assert "## PLANTILLAS DE REFERENCIA" in texto
        assert "## NORMATIVA APLICABLE" not in texto
