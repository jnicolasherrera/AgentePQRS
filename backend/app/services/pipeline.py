"""
pipeline.py — Unificador post-clasificación.

Invocado por los 3 workers (worker_ai_consumer, master_worker_outlook, worker_outlook_cliente2)
después de clasificar un evento. Orquesta:
    1. enrich_by_tipo (Agente 3 - enrichers/) para extraer metadata_especifica.
    2. Cálculo de SLA en Python solo para TUTELA con metadata completa; para el
       resto se delega al trigger DB (fallback natural).
    3. INSERT via db_inserter.insert_pqrs_caso con metadata + fecha_vencimiento opcionales.
    4. Vinculación best-effort (solo TUTELA con doc_hash) — errores solo loguean, no
       cascadean ni rompen el pipeline.

Ningún worker debe duplicar esta lógica.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

import asyncpg

from app.services import db_inserter
from app.services.ai_classifier import ClassificationResult

logger = logging.getLogger("PIPELINE")


async def process_classified_event(
    clasificacion: ClassificationResult,
    event: dict,
    cliente_id: uuid.UUID,
    conn: Optional[asyncpg.Connection],
    pool: Optional[asyncpg.Pool] = None,
) -> uuid.UUID:
    """
    Procesa un evento clasificado: enrich + SLA tutela Python + insert + vinculación.

    Requiere `pool` para db_inserter (mantiene la firma legacy); `conn` se usa
    para las funciones que trabajan sobre una conexión específica (extractor,
    vinculación, sla_engine).

    Retorna el UUID del caso insertado.
    """
    tipo_caso = clasificacion.tipo_caso

    # ── 1. Enrich polimórfico por tipo ───────────────────────────────
    metadata_especifica: dict = {}
    try:
        from app.services.enrichers import enrich_by_tipo  # import diferido (enrichers es paquete de Agente 3)
        metadata_especifica = await enrich_by_tipo(tipo_caso, event, clasificacion)
    except ImportError:
        # Agente 3 aún no instaló los enrichers → metadata vacía, pipeline sigue.
        logger.debug("enrichers/ no disponible aún — metadata_especifica={}")
    except Exception:
        logger.exception("enrich_by_tipo lanzó excepción; se continúa con metadata vacía")
        metadata_especifica = {"_enrichment_failed": True}

    # ── 2. SLA Python solo para TUTELA con metadata utilizable ──────
    fecha_vencimiento = None
    if (
        tipo_caso == "TUTELA"
        and metadata_especifica
        and not metadata_especifica.get("_extraction_failed")
        and not metadata_especifica.get("_enrichment_failed")
    ):
        try:
            from app.services.sla_engine import calcular_vencimiento_tutela
            fecha_recibido = _extract_fecha_recibido(event)
            fecha_vencimiento = await calcular_vencimiento_tutela(
                fecha_recibido, metadata_especifica, cliente_id, conn,
            )
        except Exception:
            logger.exception(
                "calcular_vencimiento_tutela falló para caso %s; fallback al trigger",
                clasificacion,
            )
            fecha_vencimiento = None

    # ── 3. INSERT ────────────────────────────────────────────────────
    if pool is None:
        raise ValueError("pipeline.process_classified_event requiere pool asyncpg")

    caso_id = await db_inserter.insert_pqrs_caso(
        event,
        clasificacion,
        pool,
        metadata_especifica=metadata_especifica or None,
        fecha_vencimiento=fecha_vencimiento,
    )

    # ── 4. Vinculación best-effort (solo TUTELA con doc_hash) ───────
    if tipo_caso == "TUTELA":
        accionante = (metadata_especifica or {}).get("accionante")
        doc_hash = accionante.get("documento_hash") if isinstance(accionante, dict) else None
        if doc_hash and conn is not None:
            try:
                from app.services.vinculacion import vincular_con_pqrs_previo
                await vincular_con_pqrs_previo(
                    caso_id=caso_id,
                    cliente_id=cliente_id,
                    doc_hash=doc_hash,
                    conn=conn,
                )
            except ImportError:
                logger.debug("vinculacion no disponible aún (Agente 3)")
            except Exception:
                logger.exception("vinculación falló para caso %s; pipeline continúa", caso_id)

    return caso_id


def _extract_fecha_recibido(event: dict):
    """Extrae fecha_recibido del evento Kafka en formato datetime UTC."""
    from app.services.db_inserter import _parse_fecha
    return _parse_fecha(event.get("date") or event.get("fecha_recibido"))
