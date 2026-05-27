"""
Backfill del Knowledge Base RAG (Fase 2).

Levanta documentos elegibles de la BD + plantillas hardcodeadas + normativa
colombiana, los embedea con Voyage AI, y los inserta en `respuestas_kb`.

Idempotente: usa UPSERT por (cliente_id, source_type, source_id). Si vuelves
a correrlo re-embedea sin duplicar.

Uso (dentro del container backend):
    python -m scripts.kb_backfill                     # todo, todos los tenants
    python -m scripts.kb_backfill --tenant <UUID>     # un solo tenant
    python -m scripts.kb_backfill --source plantilla  # solo plantillas
    python -m scripts.kb_backfill --dry-run           # no llama API, no escribe
    python -m scripts.kb_backfill --limit 5           # top 5 por source (para tests)

Requiere:
    - VOYAGE_API_KEY en el entorno (vía docker-compose)
    - DATABASE_URL en el entorno
    - pgvector extension + tabla respuestas_kb (migración 16)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from typing import Any, Iterable

import asyncpg

# add /app al path para que `from app.services...` funcione cuando se invoca
# como módulo (`python -m scripts.kb_backfill`).
sys.path.insert(0, "/app")
from app.services.embedding_engine import (  # noqa: E402
    EmbeddingEngine,
    EmbeddingError,
    EmbeddingResult,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kb_backfill")


# --------------------------------------------------------------------------- #
# Plantillas hardcodeadas de Recovery (ai_engine.py:64-91)
# Las traemos al KB para que el retrieval las vea como respuestas-modelo.
# Cuando el item de deuda "mover plantillas Recovery de código a DB" se cierre,
# este bloque se elimina y se levantan automáticamente vía la query de plantilla.
# --------------------------------------------------------------------------- #
TENANT_RECOVERY = "effca814-b0b5-4329-96be-186c0333ad4b"

PLANTILLAS_HARDCODED_RECOVERY = [
    {
        "id": "rec-hc-debitos-automaticos",
        "problematica": "DEBITOS_AUTOMATICOS",
        "tipo_caso": "RECLAMO",
        "contenido": (
            "Buenas tardes Sr (a), agradecemos su comunicación. Respecto al "
            "reclamo por débitos automáticos no autorizados, le informamos "
            "que hemos iniciado la verificación correspondiente con el área "
            "operativa. La normativa aplicable es la Circular Básica Jurídica "
            "de la Superintendencia Financiera (8 días hábiles para respuesta "
            "definitiva). Le notificaremos el resultado en cuanto se complete "
            "la trazabilidad de las operaciones cuestionadas."
        ),
    },
    {
        "id": "rec-hc-paz-y-salvo-rapicredit",
        "problematica": "PAZ_Y_SALVO_RAPICREDIT",
        "tipo_caso": "PETICION",
        "contenido": (
            "Cordial saludo. Hemos recibido su solicitud de paz y salvo "
            "relacionada con la obligación gestionada por Rapicredit. "
            "Verificada la información en nuestros sistemas, su obligación "
            "se encuentra al día / cancelada y procedemos a emitir el "
            "documento de paz y salvo correspondiente, el cual será remitido "
            "al correo registrado en un plazo no mayor a 5 días hábiles. "
            "Fundamento: Art. 23 de la Constitución Política, Ley 1755/2015."
        ),
    },
    {
        "id": "rec-hc-suplantacion-identidad",
        "problematica": "SUPLANTACION_RAPICREDIT",
        "tipo_caso": "QUEJA",
        "contenido": (
            "Estimado(a), reconocemos la gravedad de su denuncia por "
            "suplantación de identidad en la plataforma. Hemos remitido el "
            "caso al área de prevención de fraude para investigación inmediata "
            "y suspendido cualquier obligación derivada del proceso "
            "cuestionado hasta esclarecer los hechos. Solicitamos copia de la "
            "denuncia ante la URI/CTI para soporte del expediente."
        ),
    },
    {
        "id": "rec-hc-eliminar-datos",
        "problematica": "ELIMINACION_DATOS_PERSONALES",
        "tipo_caso": "PETICION",
        "contenido": (
            "Cordial saludo. Su solicitud de eliminación de datos personales "
            "ha sido recibida y será procesada conforme a la Ley 1581 de 2012 "
            "(Hábeas Data) y el Decreto 1377 de 2013. Le informamos que la "
            "eliminación procederá únicamente cuando no existan obligaciones "
            "contractuales o legales vigentes que requieran la conservación "
            "del dato. Le confirmaremos el resultado dentro del plazo de "
            "respuesta de 15 días hábiles."
        ),
    },
    {
        "id": "rec-hc-novedad-reporte-centrales",
        "problematica": "NOVEDAD_REPORTE_CENTRALES",
        "tipo_caso": "RECLAMO",
        "contenido": (
            "Buenas tardes. En atención a su reclamo respecto al reporte ante "
            "centrales de riesgo, le informamos que ya iniciamos el proceso "
            "de validación. Si se confirma la inconsistencia, procederemos a "
            "solicitar la corrección/eliminación correspondiente ante "
            "DataCrédito y/o TransUnion dentro del plazo de Ley 1266/2008. "
            "El resultado de la verificación le será notificado en máximo 8 "
            "días hábiles."
        ),
    },
]


# --------------------------------------------------------------------------- #
# Recolectores por source_type
# --------------------------------------------------------------------------- #

async def _recoger_casos_enviados(
    conn: asyncpg.Connection,
    tenant_filter: str | None,
    limit: int | None,
    skip_existing: bool = False,
) -> list[dict[str, Any]]:
    """Casos cerrados y enviados con borrador útil (>100 chars).

    skip_existing=True excluye los ya indexados en respuestas_kb (no
    re-embedea — evita gastar tokens Voyage en idempotencia).
    """
    skip_clause = (
        "AND NOT EXISTS (SELECT 1 FROM respuestas_kb kb "
        "WHERE kb.cliente_id = pqrs_casos.cliente_id "
        "AND kb.source_type='caso_enviado' "
        "AND kb.source_id = pqrs_casos.id::text)"
        if skip_existing else ""
    )
    q = """
        SELECT id::text AS source_id, cliente_id::text, asunto, borrador_respuesta,
               problematica_detectada, tipo_caso, enviado_at
        FROM pqrs_casos
        WHERE estado = 'CERRADO'
          AND borrador_estado = 'ENVIADO'
          AND borrador_respuesta IS NOT NULL
          AND length(borrador_respuesta) > 100
          {tenant_where}
          {skip_clause}
        ORDER BY enviado_at DESC
        {limit_clause}
    """.format(
        tenant_where=("AND cliente_id = $1::uuid" if tenant_filter else ""),
        skip_clause=skip_clause,
        limit_clause=(f"LIMIT {int(limit)}" if limit else ""),
    )
    rows = await (conn.fetch(q, tenant_filter) if tenant_filter else conn.fetch(q))

    return [
        {
            "cliente_id": r["cliente_id"],
            "source_type": "caso_enviado",
            "source_id": r["source_id"],
            "problematica": r["problematica_detectada"],
            "tipo_caso": r["tipo_caso"],
            # Contexto del caso para retrieval (asunto + borrador final).
            "contenido": f"ASUNTO: {r['asunto']}\n\nRESPUESTA:\n{r['borrador_respuesta']}",
            "metadata": {"enviado_at": r["enviado_at"].isoformat() if r["enviado_at"] else None},
        }
        for r in rows
    ]


async def _recoger_plantillas(
    conn: asyncpg.Connection,
    tenant_filter: str | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    """Plantillas activas en plantillas_respuesta + las hardcodeadas de Recovery."""
    q = """
        SELECT id::text AS source_id, cliente_id::text, problematica,
               contexto, cuerpo
        FROM plantillas_respuesta
        WHERE is_active = TRUE
          {tenant_where}
        ORDER BY created_at DESC
        {limit_clause}
    """.format(
        tenant_where=("AND cliente_id = $1::uuid" if tenant_filter else ""),
        limit_clause=(f"LIMIT {int(limit)}" if limit else ""),
    )
    rows = await (conn.fetch(q, tenant_filter) if tenant_filter else conn.fetch(q))

    docs = [
        {
            "cliente_id": r["cliente_id"],
            "source_type": "plantilla",
            "source_id": r["source_id"],
            "problematica": r["problematica"],
            "tipo_caso": None,
            "contenido": (
                f"PROBLEMÁTICA: {r['problematica']}\n\n"
                + (f"CONTEXTO: {r['contexto']}\n\n" if r["contexto"] else "")
                + f"PLANTILLA:\n{r['cuerpo']}"
            ),
            "metadata": {"origen": "plantillas_respuesta"},
        }
        for r in rows
    ]

    # Agregar hardcodeadas de Recovery si aplica.
    incluir_hc = (tenant_filter is None) or (tenant_filter == TENANT_RECOVERY)
    if incluir_hc:
        for p in PLANTILLAS_HARDCODED_RECOVERY:
            docs.append({
                "cliente_id": TENANT_RECOVERY,
                "source_type": "plantilla",
                "source_id": p["id"],
                "problematica": p["problematica"],
                "tipo_caso": p["tipo_caso"],
                "contenido": (
                    f"PROBLEMÁTICA: {p['problematica']}\n"
                    f"TIPO: {p['tipo_caso']}\n\n"
                    f"PLANTILLA:\n{p['contenido']}"
                ),
                "metadata": {"origen": "hardcoded_ai_engine"},
            })
    return docs


async def _recoger_normativa(
    tenant_filter: str | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    """Normativa colombiana. Multi-tenant: TODOS los tenants tienen acceso al
    mismo cuerpo normativo. La duplicamos por tenant para que el filtro RLS
    funcione sin sortijas.

    Por ahora: stubs mínimos hardcodeados. Cuando se agregue ingestion real
    de PDFs (Fase 2.1), se levantan de un directorio o de un endpoint."""
    artículos = [
        {
            "source_id": "decreto-2591-91-art-1",
            "tipo_caso": "TUTELA",
            "contenido": (
                "DECRETO 2591 DE 1991 — Art. 1. Toda persona tendrá acción de "
                "tutela para reclamar ante los jueces, en todo momento y "
                "lugar, mediante un procedimiento preferente y sumario, por "
                "sí misma o por quien actúe a su nombre, la protección "
                "inmediata de sus derechos constitucionales fundamentales, "
                "cuando quiera que estos resulten vulnerados o amenazados por "
                "la acción o la omisión de cualquier autoridad pública o de "
                "los particulares en los casos que señala este Decreto. "
                "Plazo de respuesta: 48 horas."
            ),
        },
        {
            "source_id": "ley-1755-2015-art-14",
            "tipo_caso": "PETICION",
            "contenido": (
                "LEY 1755 DE 2015 — Art. 14. Términos para resolver las "
                "distintas modalidades de peticiones. Salvo norma legal "
                "especial y so pena de sanción disciplinaria, toda petición "
                "deberá resolverse dentro de los quince (15) días siguientes "
                "a su recepción. Estará sometida a término especial la "
                "resolución de las siguientes peticiones: (1) petición de "
                "documentos: 10 días; (2) consulta a las autoridades en "
                "relación con las materias a su cargo: 30 días."
            ),
        },
        {
            "source_id": "ley-1266-2008-art-16",
            "tipo_caso": "RECLAMO",
            "contenido": (
                "LEY 1266 DE 2008 (Hábeas Data Financiero) — Art. 16. Petición "
                "de consultas y reclamos. El titular de la información o sus "
                "causahabientes podrán consultar la información personal del "
                "titular que repose en cualquier banco de datos. Reclamos: las "
                "fuentes y operadores de información tienen 15 días hábiles "
                "para resolver. Si requiere mayor estudio, máximo 8 días "
                "adicionales (notificando al peticionario)."
            ),
        },
        {
            "source_id": "constitucion-art-23",
            "tipo_caso": "PETICION",
            "contenido": (
                "CONSTITUCIÓN POLÍTICA DE COLOMBIA — Art. 23. Toda persona "
                "tiene derecho a presentar peticiones respetuosas a las "
                "autoridades por motivos de interés general o particular y a "
                "obtener pronta resolución. El legislador podrá reglamentar "
                "su ejercicio ante organizaciones privadas para garantizar "
                "los derechos fundamentales."
            ),
        },
        {
            "source_id": "circular-basica-juridica-sfc-quejas",
            "tipo_caso": "QUEJA",
            "contenido": (
                "CIRCULAR BÁSICA JURÍDICA DE LA SUPERINTENDENCIA FINANCIERA DE "
                "COLOMBIA — Atención al consumidor financiero. Las quejas y "
                "reclamos presentados ante entidades vigiladas deben ser "
                "resueltos dentro de los 15 días hábiles siguientes a su "
                "recepción, prorrogables por 8 días hábiles adicionales "
                "previa notificación al consumidor. Plazo común aplicable: "
                "8 días hábiles."
            ),
        },
    ]

    # Decidir a qué tenants asignar la normativa (todos, o solo el filtrado).
    if tenant_filter:
        tenants = [tenant_filter]
    else:
        # Levantar todos los tenants activos. Sin conn acá, pasamos lista vacía
        # y el caller lo completará. (Hack pragmático para evitar dos firmas.)
        tenants = []  # → resuelve en main()

    if limit:
        artículos = artículos[:limit]

    docs = []
    for tid in tenants:
        for art in artículos:
            docs.append({
                "cliente_id": tid,
                "source_type": "normativa",
                "source_id": art["source_id"],
                "problematica": None,
                "tipo_caso": art["tipo_caso"],
                "contenido": art["contenido"],
                "metadata": {"fuente": "normativa_co_v1"},
            })
    return docs


# --------------------------------------------------------------------------- #
# Persistencia
# --------------------------------------------------------------------------- #

async def _upsert_doc(
    conn: asyncpg.Connection,
    doc: dict[str, Any],
    vector: list[float],
    model: str,
) -> None:
    await conn.execute(
        """
        INSERT INTO respuestas_kb
          (cliente_id, source_type, source_id, problematica, tipo_caso,
           contenido, embedding, embedding_model, metadata)
        VALUES ($1::uuid, $2, $3, $4, $5, $6, $7::vector, $8, $9::jsonb)
        ON CONFLICT (cliente_id, source_type, source_id)
        DO UPDATE SET
          problematica   = EXCLUDED.problematica,
          tipo_caso      = EXCLUDED.tipo_caso,
          contenido      = EXCLUDED.contenido,
          embedding      = EXCLUDED.embedding,
          embedding_model= EXCLUDED.embedding_model,
          metadata       = EXCLUDED.metadata,
          updated_at     = CURRENT_TIMESTAMP
        """,
        doc["cliente_id"],
        doc["source_type"],
        doc["source_id"],
        doc.get("problematica"),
        doc.get("tipo_caso"),
        doc["contenido"],
        str(vector),
        model,
        __import__("json").dumps(doc.get("metadata") or {}),
    )


async def _log_ingestion(
    conn: asyncpg.Connection,
    tenant: str | None,
    source_type: str,
    documentos: int,
    tokens_in: int,
    model: str,
    status: str,
    error_msg: str | None,
    duracion_ms: int,
) -> None:
    await conn.execute(
        """
        INSERT INTO kb_ingestion_log
          (cliente_id, source_type, documentos, tokens_in, embedding_model,
           status, error_msg, duracion_ms)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        tenant,
        source_type,
        documentos,
        tokens_in,
        model,
        status,
        error_msg,
        duracion_ms,
    )


# --------------------------------------------------------------------------- #
# Pipeline por source_type
# --------------------------------------------------------------------------- #

SOURCES = ("caso_enviado", "plantilla", "normativa")


async def _backfill_source(
    conn: asyncpg.Connection,
    engine: EmbeddingEngine,
    source: str,
    tenant_filter: str | None,
    limit: int | None,
    dry_run: bool,
    skip_existing: bool = False,
) -> None:
    t0 = time.time()
    logger.info("─── source=%s tenant=%s limit=%s skip_existing=%s ───",
                source, tenant_filter, limit, skip_existing)

    if source == "caso_enviado":
        docs = await _recoger_casos_enviados(conn, tenant_filter, limit, skip_existing)
    elif source == "plantilla":
        docs = await _recoger_plantillas(conn, tenant_filter, limit)
    elif source == "normativa":
        # Necesita lista de tenants — la resolvemos acá.
        if tenant_filter is None:
            rows = await conn.fetch("SELECT id::text FROM clientes_tenant WHERE is_active = TRUE")
            tenants = [r["id"] for r in rows]
        else:
            tenants = [tenant_filter]
        docs = []
        for tid in tenants:
            docs.extend(await _recoger_normativa(tid, limit))
    else:
        raise ValueError(f"source desconocido: {source}")

    if not docs:
        logger.info("  sin documentos elegibles")
        return

    logger.info("  → %d documentos a procesar", len(docs))
    if dry_run:
        for d in docs[:5]:
            logger.info("    DRY [tnt=%s] %s/%s — %d chars",
                        d["cliente_id"][:8], d["source_type"], d["source_id"], len(d["contenido"]))
        if len(docs) > 5:
            logger.info("    ... y %d más", len(docs) - 5)
        return

    # Embedear en un solo batch (el engine chunkea automáticamente).
    textos = [d["contenido"] for d in docs]
    try:
        result: EmbeddingResult = await engine.embed_texts(textos, input_type="document")
    except EmbeddingError as exc:
        await _log_ingestion(
            conn, tenant_filter, source, len(docs), 0, engine.model,
            "error", str(exc), int((time.time() - t0) * 1000),
        )
        logger.error("  ✗ embedding falló: %s", exc)
        raise

    # Persistir (uno por uno — el volumen es chico, vale más la atomicidad).
    insertados = 0
    for doc, vec in zip(docs, result.vectors):
        try:
            await _upsert_doc(conn, doc, vec, result.model)
            insertados += 1
        except Exception as exc:
            logger.error("  ✗ upsert falló para %s/%s: %s",
                         doc["source_type"], doc["source_id"], exc)

    status = "ok" if insertados == len(docs) else "partial"
    duracion = int((time.time() - t0) * 1000)
    await _log_ingestion(
        conn, tenant_filter, source, insertados, result.total_tokens,
        engine.model, status, None, duracion,
    )
    logger.info("  ✓ %d/%d upserts, %d tokens, %dms",
                insertados, len(docs), result.total_tokens, duracion)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

async def main_async(args: argparse.Namespace) -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL no está configurada")
        return 2

    # Conectamos como admin (super) para ver todos los tenants — esto es un
    # backfill operativo, no un request de usuario.
    conn = await asyncpg.connect(db_url)
    try:
        # Habilitar super context para que RLS no nos filtre.
        await conn.execute("SET app.is_superuser = 'true'")

        engine = None
        if not args.dry_run:
            engine = EmbeddingEngine()
            logger.info("Engine listo (modelo=%s)", engine.model)

        sources_a_correr = [args.source] if args.source else SOURCES
        for src in sources_a_correr:
            await _backfill_source(
                conn=conn,
                engine=engine,  # ignorado en dry-run
                source=src,
                tenant_filter=args.tenant,
                limit=args.limit,
                dry_run=args.dry_run,
                skip_existing=args.skip_existing,
            )
    finally:
        await conn.close()

    logger.info("backfill terminado")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tenant", help="UUID del tenant; default: todos")
    p.add_argument("--source", choices=SOURCES, help="source_type; default: todos")
    p.add_argument("--limit", type=int, help="top N por source (para tests)")
    p.add_argument("--dry-run", action="store_true",
                   help="No llama API ni inserta; sólo lista qué haría")
    p.add_argument("--skip-existing", action="store_true",
                   help="Solo procesa source_id que NO están ya en respuestas_kb "
                        "(idempotencia eficiente — no re-embedea).")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async(parse_args())))
