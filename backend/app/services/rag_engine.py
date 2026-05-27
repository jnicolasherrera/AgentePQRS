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
    #
    # bug_004 (review remoto): `tipo_caso = $5` excluye filas con
    # tipo_caso=NULL por la semántica UNKNOWN de SQL. Las plantillas se
    # ingestan con tipo_caso=NULL (kb_backfill._recoger_plantillas) porque
    # plantillas_respuesta no tiene esa columna. Sin OR IS NULL toda
    # plantilla DB queda invisible al retrieval. Aceptamos NULL como
    # wildcard ("aplica a cualquier tipo_caso").
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
    tipo_filter = "AND (tipo_caso = $5 OR tipo_caso IS NULL)" if tipo_caso else ""
    sql = sql.format(tipo_filter=tipo_filter)

    args: list[Any] = [str(query_vec), tenant_id, threshold, top_k]
    if tipo_caso:
        args.append(tipo_caso)

    # bug_010 (review remoto): HNSW + WHERE pre-LIMIT pierde recall a escala
    # multi-tenant. Con ef_search=40 default, los 40 vecinos globales se
    # filtran después por cliente_id+tipo_caso y muchos buenos matches se
    # eliminan silenciosamente. Mitigación pgvector 0.8+: iterative_scan
    # = relaxed_order itera hasta llenar el LIMIT respetando los filtros.
    # SET LOCAL requiere transacción.
    try:
        async with conn.transaction():
            await conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
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


async def aprender_de_envio(
    conn: asyncpg.Connection,
    caso_id: str,
    tenant_id: str,
    asunto: str,
    texto_enviado: str,
    tipo_caso: str | None = None,
    problematica: str | None = None,
) -> bool:
    """Indexa al KB la respuesta final que se envió al cliente.

    Sprint FF cierre-de-loop 2026-05-27 ("el modelo aprende"):
    cada respuesta enviada se vuelve `caso_enviado` en respuestas_kb
    para que futuros casos similares la retrieven como few-shot.

    UPSERT por (cliente_id, source_type='caso_enviado', source_id=caso_id):
    si el mismo caso se re-envía después de una edición, se actualiza el
    embedding. El KB siempre refleja la última versión que se mandó.

    Best-effort: si Voyage falla o la DB rechaza, devuelve False con log
    warn (NUNCA rompe el flow del envío).

    Returns:
        True si se indexó, False si falló o se skipeó.
    """
    if not texto_enviado or len(texto_enviado) < 50:
        # Borradores muy cortos no aportan al KB.
        return False
    try:
        from app.services.embedding_engine import EmbeddingEngine
        engine = EmbeddingEngine()
        contenido = f"ASUNTO: {asunto or ''}\n\nRESPUESTA:\n{texto_enviado}"
        result = await engine.embed_texts([contenido], input_type="document")
        if not result.vectors:
            logger.warning("aprender_de_envio: embedding vacío para %s", caso_id)
            return False
        vec = result.vectors[0]
        await conn.execute(
            """INSERT INTO respuestas_kb
                  (cliente_id, source_type, source_id, problematica, tipo_caso,
                   contenido, embedding, embedding_model, metadata)
               VALUES ($1::uuid, 'caso_enviado', $2, $3, $4, $5, $6::vector, $7, $8::jsonb)
               ON CONFLICT (cliente_id, source_type, source_id) DO UPDATE SET
                 contenido       = EXCLUDED.contenido,
                 embedding       = EXCLUDED.embedding,
                 embedding_model = EXCLUDED.embedding_model,
                 problematica    = EXCLUDED.problematica,
                 tipo_caso       = EXCLUDED.tipo_caso,
                 metadata        = EXCLUDED.metadata,
                 updated_at      = CURRENT_TIMESTAMP""",
            tenant_id, str(caso_id), problematica, tipo_caso, contenido,
            str(vec), result.model,
            '{"learned_from_envio": true}',
        )
        logger.info(
            "aprender_de_envio: caso=%s tokens=%d → KB updated",
            str(caso_id)[:8], result.total_tokens,
        )
        return True
    except Exception as e:
        logger.warning("aprender_de_envio falló para %s: %s", caso_id, e)
        return False


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
