"""
A/B shadow mode del RAG — Fase 4.

Diseño:
- En el camino B de generar_borrador_para_caso (sin plantilla → Claude
  genérico), se generan AMBAS variants: la oficial con_rag (Fase 3) y
  una shadow no_rag que replica el comportamiento pre-RAG.
- Ambas se persisten en `ab_test_borradores` con UPSERT idempotente.
- El abogado solo ve la oficial (no cambia el flow). Cuando envía, un
  script batch (scripts/ab_test_evaluate.py) compara el texto final
  con cada variant para llenar `similarity_to_edited`.

Pensado para correrse desde el worker, igual que plantilla_engine.
La función `generar_borrador_sin_rag` replica exactamente el código
pre-Fase 3 (Claude Haiku, max 600 tokens, prompt fijo) para ser
baseline limpio.

Toda función toma try/except defensivos: si el shadow falla, el flow
productivo NO se rompe — solo se pierde una observación A/B.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

# Mismo system prompt fijo por tipo que tenía plantilla_engine pre-Fase 3.
# Lo replicamos acá para que el baseline no_rag sea idéntico al
# comportamiento anterior — sin contaminación cruzada de imports.
_BASELINE_PROMPTS_TIPO = {
    "TUTELA": (
        "Eres un abogado colombiano experto en acciones de tutela. "
        "Redacta una respuesta formal a la tutela descrita, en nombre de la entidad demandada. "
        "Cita el Decreto 2591 de 1991 y recuerda que el plazo legal para responder es de 48 horas. "
        "Sé conciso, formal y técnico. Usa lenguaje jurídico colombiano."
    ),
    "PETICION": (
        "Eres un abogado colombiano experto en derechos de petición. "
        "Redacta una respuesta formal al derecho de petición descrito, citando el artículo 23 "
        "de la Constitución Política y la Ley 1755 de 2015. "
        "El plazo legal es de 15 días hábiles. Usa lenguaje formal y respetuoso."
    ),
    "QUEJA": (
        "Eres un abogado colombiano especialista en protección al consumidor financiero. "
        "Redacta una respuesta formal a la queja descrita, en cumplimiento de la normativa "
        "de la Superintendencia Financiera de Colombia. "
        "El plazo es de 8 días hábiles según la SFC. Sé empático pero formal."
    ),
    "RECLAMO": (
        "Eres un abogado colombiano especialista en protección al consumidor financiero. "
        "Redacta una respuesta formal al reclamo descrito, cumpliendo la normativa de la "
        "Superintendencia Financiera de Colombia (Circular Básica Jurídica). "
        "El plazo es de 8 días hábiles. Sé formal, empático y propositivo."
    ),
    "SOLICITUD": (
        "Eres un abogado colombiano. Redacta una respuesta formal y cordial a la solicitud "
        "descrita, indicando que fue radicada y será atendida dentro de los 15 días hábiles. "
        "Usa lenguaje formal colombiano."
    ),
}

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS_OUT = 600


async def generar_borrador_sin_rag(
    asunto: str,
    cuerpo: str,
    tipo_caso: str,
    nombre_cliente: Optional[str],
) -> tuple[Optional[str], dict]:
    """Genera el borrador BASELINE (sin RAG, replica pre-Fase 3).

    Devuelve (texto, metadata). Metadata trae tokens_in/out, latencia_ms,
    modelo. Si Claude falla, devuelve (None, {error: ...}) y el caller
    decide qué hacer.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None, {"error": "no_anthropic_key"}

    t0 = time.time()
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        saludo = f"dirigida a {nombre_cliente}" if nombre_cliente else ""
        system = _BASELINE_PROMPTS_TIPO.get(tipo_caso, _BASELINE_PROMPTS_TIPO["SOLICITUD"])
        user_msg = (
            f"Redacta la respuesta {saludo} al siguiente caso:\n\n"
            f"Asunto: {asunto}\n\n"
            f"Contenido del correo:\n{cuerpo[:1500]}\n\n"
            "La respuesta debe tener: saludo formal, reconocimiento del caso, "
            "fundamento legal aplicable, plazo de respuesta definitiva y despedida. "
            "Máximo 300 palabras."
        )
        resp = await client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS_OUT,
            messages=[{"role": "user", "content": user_msg}],
            system=system,
        )
        texto = resp.content[0].text.strip()
        meta = {
            "modelo": _MODEL,
            "tokens_in": getattr(resp.usage, "input_tokens", None),
            "tokens_out": getattr(resp.usage, "output_tokens", None),
            "latencia_ms": int((time.time() - t0) * 1000),
        }
        return texto, meta
    except Exception as e:  # noqa: BLE001 — shadow nunca debe propagar
        logger.warning("ab_test_engine: shadow no_rag falló: %s", e)
        return None, {"error": str(e), "latencia_ms": int((time.time() - t0) * 1000)}


async def persistir_variant(
    conn: asyncpg.Connection,
    caso_id: str,
    tenant_id: str,
    variant: str,                      # 'with_rag' | 'no_rag'
    contenido: str,
    *,
    rag_docs: Optional[list[dict]] = None,
    tipo_caso: Optional[str] = None,
    modelo: Optional[str] = None,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
    latencia_ms: Optional[int] = None,
) -> None:
    """UPSERT idempotente por (caso_id, variant)."""
    if variant not in ("with_rag", "no_rag"):
        raise ValueError(f"variant inválida: {variant}")
    if not contenido:
        # No persistir variant vacía — la dejamos sin registro y el
        # evaluador la ignora.
        return

    try:
        await conn.execute(
            """
            INSERT INTO ab_test_borradores
              (caso_id, cliente_id, variant, contenido, rag_docs,
               tipo_caso, modelo, tokens_in, tokens_out, latencia_ms)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb, $6, $7, $8, $9, $10)
            ON CONFLICT (caso_id, variant) DO UPDATE SET
              contenido    = EXCLUDED.contenido,
              rag_docs     = EXCLUDED.rag_docs,
              tipo_caso    = EXCLUDED.tipo_caso,
              modelo       = EXCLUDED.modelo,
              tokens_in    = EXCLUDED.tokens_in,
              tokens_out   = EXCLUDED.tokens_out,
              latencia_ms  = EXCLUDED.latencia_ms,
              -- conservamos edited_text/similarity/evaluated_at si ya estaban
              -- (no los toca este UPSERT)
              created_at   = ab_test_borradores.created_at
            """,
            uuid.UUID(caso_id),
            uuid.UUID(tenant_id),
            variant,
            contenido,
            json.dumps(rag_docs or []),
            tipo_caso,
            modelo,
            tokens_in,
            tokens_out,
            latencia_ms,
        )
    except Exception as e:  # noqa: BLE001 — A/B no debe romper el flow
        logger.warning(
            "ab_test_engine: persistir variant=%s caso=%s falló: %s",
            variant, caso_id, e,
        )


async def registrar_shadow_para_caso(
    conn: asyncpg.Connection,
    caso_id: str,
    tenant_id: str,
    asunto: str,
    cuerpo: str,
    tipo_caso: str,
    nombre_cliente: Optional[str],
) -> None:
    """Genera y persiste la variant no_rag (shadow). Llama a Claude UNA vez
    extra (~3-5s) y se autocontiene: cualquier error queda en log y no se
    propaga."""
    try:
        texto, meta = await generar_borrador_sin_rag(asunto, cuerpo, tipo_caso, nombre_cliente)
        if not texto:
            return
        await persistir_variant(
            conn, caso_id, tenant_id, "no_rag", texto,
            rag_docs=[],
            tipo_caso=tipo_caso,
            modelo=meta.get("modelo"),
            tokens_in=meta.get("tokens_in"),
            tokens_out=meta.get("tokens_out"),
            latencia_ms=meta.get("latencia_ms"),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("ab_test_engine: registrar_shadow_para_caso falló: %s", e)
