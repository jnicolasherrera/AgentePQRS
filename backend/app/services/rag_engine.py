"""
Retrieval del Knowledge Base RAG (Fase 3).

Función única: ``buscar_docs_similares`` — embedea una query (asunto + cuerpo
del email entrante) y recupera los top-k documentos más cercanos del KB
filtrando por tenant.

Pensado para invocarse desde ``plantilla_engine.generar_borrador_con_ia`` antes
de la llamada a Claude. Si Voyage falla, devuelve [] (el caller degrada sin RAG).
"""

from __future__ import annotations

import logging
from typing import Any

import asyncpg

from app.services.embedding_engine import (
    EmbeddingEngine,
    EmbeddingError,
)

logger = logging.getLogger(__name__)

# Cantidad de chars del cuerpo a usar como query. El cuerpo completo puede
# exceder 1500 tokens y desperdicia presupuesto; las primeras líneas suelen
# concentrar el intent.
QUERY_BODY_MAX_CHARS = 800

DEFAULT_TOP_K = 3
DEFAULT_THRESHOLD = 0.40  # ajustable, propuesto en SPRINT_RAG_FASE1


async def buscar_docs_similares(
    conn: asyncpg.Connection,
    tenant_id: str,
    asunto: str,
    cuerpo: str,
    *,
    tipo_caso: str | None = None,
    top_k: int = DEFAULT_TOP_K,
    threshold: float = DEFAULT_THRESHOLD,
    engine: EmbeddingEngine | None = None,
) -> list[dict[str, Any]]:
    """Devuelve los top-k docs del KB más similares al email entrante.

    Filtros:
    - ``cliente_id = $tenant_id`` (defensa explícita, además de RLS).
    - ``tipo_caso = $tipo_caso`` si se provee (acota normativa/casos al tipo).
    - similitud coseno ≥ ``threshold`` (excluye docs irrelevantes).

    Devuelve lista de dicts en orden de similitud (más alto primero):
        [{source_type, source_id, contenido, tipo_caso, problematica, sim_score}, ...]

    Si Voyage falla, logea warning y devuelve [] — el caller degrada sin RAG.
    Si no hay docs sobre el threshold, devuelve [].
    """
    query_text = _construir_query(asunto, cuerpo)
    if not query_text.strip():
        return []

    try:
        eng = engine or EmbeddingEngine()
        result = await eng.embed_texts([query_text], input_type="query")
    except EmbeddingError as exc:
        logger.warning("rag_engine: embed query falló — sigo sin RAG (%s)", exc)
        return []
    except Exception as exc:  # noqa: BLE001 — degradación elegante por diseño
        logger.warning("rag_engine: error inesperado embeddeando — sigo sin RAG (%s)", exc)
        return []

    if not result.vectors:
        return []

    query_vec = result.vectors[0]

    # SQL parameterizado. El operador <=> de pgvector es distancia coseno,
    # similitud = 1 - distancia. Filtramos por threshold en la WHERE para que
    # el LIMIT no nos devuelva basura cuando no hay nada cercano.
    sql = """
        SELECT source_type,
               source_id,
               contenido,
               tipo_caso,
               problematica,
               (1 - (embedding <=> $1::vector))::float AS sim_score
        FROM respuestas_kb
        WHERE cliente_id = $2::uuid
          AND (1 - (embedding <=> $1::vector)) >= $3
          {tipo_filter}
        ORDER BY embedding <=> $1::vector
        LIMIT $4
    """
    tipo_filter = "AND tipo_caso = $5" if tipo_caso else ""
    sql = sql.format(tipo_filter=tipo_filter)

    args: list[Any] = [str(query_vec), tenant_id, threshold, top_k]
    if tipo_caso:
        args.append(tipo_caso)

    try:
        rows = await conn.fetch(sql, *args)
    except Exception as exc:  # noqa: BLE001 — degradar también ante errores DB
        logger.warning("rag_engine: query KB falló — sigo sin RAG (%s)", exc)
        return []

    docs = [dict(r) for r in rows]
    if docs:
        logger.info(
            "rag_engine: %d docs recuperados para tenant=%s (top sim=%.3f)",
            len(docs), tenant_id[:8], docs[0]["sim_score"],
        )
    else:
        logger.info(
            "rag_engine: 0 docs sobre threshold %.2f para tenant=%s",
            threshold, tenant_id[:8],
        )
    return docs


def _construir_query(asunto: str, cuerpo: str) -> str:
    """Combina asunto + cuerpo para la query. El asunto suele tener señal alta."""
    a = (asunto or "").strip()
    c = (cuerpo or "").strip()[:QUERY_BODY_MAX_CHARS]
    if a and c:
        return f"{a}\n\n{c}"
    return a or c


def formatear_contexto_para_prompt(docs: list[dict[str, Any]]) -> str:
    """Convierte los docs recuperados en un bloque legible para inyectar al
    user prompt de Claude. Separa por origen para que el modelo entienda qué
    es normativa y qué es respuesta-modelo."""
    if not docs:
        return ""

    por_tipo: dict[str, list[dict[str, Any]]] = {}
    for d in docs:
        por_tipo.setdefault(d["source_type"], []).append(d)

    bloques: list[str] = []

    if "normativa" in por_tipo:
        bloques.append("## NORMATIVA APLICABLE\n")
        for d in por_tipo["normativa"]:
            bloques.append(f"[similitud {d['sim_score']:.2f}] {d['contenido']}\n")

    if "plantilla" in por_tipo:
        bloques.append("## PLANTILLAS DE REFERENCIA (respuestas-modelo previas)\n")
        for d in por_tipo["plantilla"]:
            bloques.append(f"[similitud {d['sim_score']:.2f}] {d['contenido']}\n")

    if "caso_enviado" in por_tipo:
        bloques.append("## CASOS RESUELTOS PREVIAMENTE (respuestas que ya enviamos a casos similares)\n")
        for d in por_tipo["caso_enviado"]:
            bloques.append(f"[similitud {d['sim_score']:.2f}] {d['contenido']}\n")

    return "\n".join(bloques)
