"""
Evaluador batch del A/B shadow mode (Fase 4 sprint RAG real).

Para cada caso que tiene ambas variants en `ab_test_borradores` y que ya
fue enviado al destinatario (borrador_estado='ENVIADO'), compara el texto
final del abogado contra cada variant con `SequenceMatcher` y persiste el
`similarity_to_edited`.

Cuando termina, imprime un reporte agregado: avg similarity por variant +
diff %. Si `with_rag` gana, el RAG ayuda.

Uso (dentro del container backend):
    python -m scripts.ab_test_evaluate
    python -m scripts.ab_test_evaluate --tenant <UUID>
    python -m scripts.ab_test_evaluate --since-hours 24
    python -m scripts.ab_test_evaluate --dry-run

Idempotente: solo evalúa filas con `evaluated_at IS NULL`. Volver a
correrlo no re-evalúa lo ya hecho.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from difflib import SequenceMatcher
from typing import Optional

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ab_test_evaluate")


# --------------------------------------------------------------------------- #
# Recolección
# --------------------------------------------------------------------------- #

async def _casos_pendientes(
    conn: asyncpg.Connection,
    tenant: Optional[str],
    since_hours: int,
) -> list[dict]:
    """Casos con:
    - borrador_estado='ENVIADO' (el abogado ya envió)
    - enviado_at en las últimas N horas
    - al menos una variant en ab_test_borradores sin evaluar
    """
    q = """
        SELECT DISTINCT pc.id::text AS caso_id,
               pc.cliente_id::text AS tenant,
               pc.borrador_respuesta AS final_text
        FROM pqrs_casos pc
        JOIN ab_test_borradores ab ON ab.caso_id = pc.id
        WHERE pc.borrador_estado = 'ENVIADO'
          AND pc.enviado_at IS NOT NULL
          AND pc.enviado_at >= NOW() - make_interval(hours => $1)
          AND ab.evaluated_at IS NULL
          {tenant_where}
        ORDER BY pc.enviado_at DESC
    """.format(tenant_where=("AND pc.cliente_id = $2::uuid" if tenant else ""))
    rows = await (conn.fetch(q, since_hours, tenant) if tenant else conn.fetch(q, since_hours))
    return [dict(r) for r in rows]


async def _variants_del_caso(
    conn: asyncpg.Connection,
    caso_id: str,
) -> list[dict]:
    rows = await conn.fetch(
        """SELECT id::text, variant, contenido
           FROM ab_test_borradores
           WHERE caso_id = $1::uuid AND evaluated_at IS NULL""",
        caso_id,
    )
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# Cálculo de similaridad
# --------------------------------------------------------------------------- #

def similarity(a: str, b: str) -> float:
    """Idéntico al usado por borrador_feedback (SequenceMatcher) — comparable."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #

async def evaluar(
    conn: asyncpg.Connection,
    tenant: Optional[str],
    since_hours: int,
    dry_run: bool,
) -> dict[str, int]:
    casos = await _casos_pendientes(conn, tenant, since_hours)
    logger.info("Casos pendientes de evaluar: %d", len(casos))
    if not casos:
        return {}

    contadores = {"casos_evaluados": 0, "variants_actualizadas": 0}

    for caso in casos:
        variants = await _variants_del_caso(conn, caso["caso_id"])
        if not variants:
            continue

        final_text = caso["final_text"] or ""
        for v in variants:
            sim = similarity(v["contenido"], final_text)
            logger.info(
                "  caso=%s variant=%s sim=%.3f",
                caso["caso_id"][:8], v["variant"], sim,
            )
            if dry_run:
                continue
            await conn.execute(
                """UPDATE ab_test_borradores
                   SET edited_text          = $2,
                       similarity_to_edited = $3,
                       evaluated_at         = NOW()
                   WHERE id = $1::uuid""",
                v["id"], final_text, sim,
            )
            contadores["variants_actualizadas"] += 1

        contadores["casos_evaluados"] += 1

    return contadores


async def reporte_agregado(
    conn: asyncpg.Connection,
    tenant: Optional[str],
) -> None:
    """Avg similarity por variant + diff. Si with_rag > no_rag, RAG ayuda."""
    q = """
        SELECT variant,
               COUNT(*) AS n,
               ROUND(AVG(similarity_to_edited)::numeric, 4) AS avg_sim,
               ROUND(STDDEV(similarity_to_edited)::numeric, 4) AS std_sim,
               ROUND(AVG(latencia_ms)::numeric, 0) AS avg_latency_ms,
               SUM(tokens_out)::int AS total_tokens_out
        FROM ab_test_borradores
        WHERE similarity_to_edited IS NOT NULL
          {tenant_where}
        GROUP BY variant
        ORDER BY variant
    """.format(tenant_where=("AND cliente_id = $1::uuid" if tenant else ""))
    rows = await (conn.fetch(q, tenant) if tenant else conn.fetch(q))

    if not rows:
        logger.info("Reporte: sin datos evaluados todavía.")
        return

    logger.info("─── REPORTE A/B (acumulado) ───")
    by_v = {r["variant"]: dict(r) for r in rows}
    for v in ("no_rag", "with_rag"):
        d = by_v.get(v)
        if not d:
            logger.info("  %s: sin datos", v)
            continue
        logger.info(
            "  %-9s n=%3d  avg_sim=%.3f  ±%.3f  latency≈%.0fms  tokens_out=%d",
            v, d["n"], float(d["avg_sim"]), float(d["std_sim"] or 0),
            float(d["avg_latency_ms"] or 0), d["total_tokens_out"] or 0,
        )

    if "with_rag" in by_v and "no_rag" in by_v:
        diff = float(by_v["with_rag"]["avg_sim"]) - float(by_v["no_rag"]["avg_sim"])
        pct = diff * 100
        verdict = "✓ RAG mejora similaridad" if diff > 0 else "✗ RAG NO mejora" if diff < 0 else "= empate"
        logger.info("─── Δ avg_sim = %+.4f (%+.2f puntos) — %s", diff, pct, verdict)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

async def main_async(args: argparse.Namespace) -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL no configurada")
        return 2

    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute("SET app.is_superuser = 'true'")
        contadores = await evaluar(conn, args.tenant, args.since_hours, args.dry_run)
        logger.info(
            "Hecho. casos_evaluados=%d variants_actualizadas=%d (dry_run=%s)",
            contadores.get("casos_evaluados", 0),
            contadores.get("variants_actualizadas", 0),
            args.dry_run,
        )
        await reporte_agregado(conn, args.tenant)
    finally:
        await conn.close()
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tenant", help="UUID del tenant; default: todos")
    p.add_argument("--since-hours", type=int, default=168,
                   help="evaluar casos enviados en las últimas N horas (default 168 = 7 días)")
    p.add_argument("--dry-run", action="store_true",
                   help="no escribe; solo lista qué evaluaría")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async(parse_args())))
