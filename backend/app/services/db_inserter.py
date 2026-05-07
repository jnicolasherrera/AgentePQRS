"""
db_inserter.py — Sprint 2: El Cerebro
Persiste el resultado de clasificación en pqrs_casos usando asyncpg
con el rol aequitas_worker (BYPASSRLS). No usa JWT ni get_db_connection de FastAPI.
El trigger fn_set_fecha_vencimiento() calcula SLA automáticamente en el INSERT.
El trigger fn_audit_pqrs_casos() registra en logs_auditoria automáticamente.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg

from app.services.ai_classifier import ClassificationResult

logger = logging.getLogger("DB_INSERTER")


async def insert_pqrs_caso(
    event: dict,
    result: ClassificationResult,
    pool: asyncpg.Pool,
    *,
    metadata_especifica: Optional[dict[str, Any]] = None,
    fecha_vencimiento: Optional[datetime] = None,
) -> uuid.UUID:
    """
    Inserta un nuevo caso PQRS en PostgreSQL.
    - Ejecuta round-robin para asignar al analista con menor carga activa en el tenant
    - Preserva correlation_id del evento Kafka (trazabilidad end-to-end)
    - Popula fecha_recibido para activar el trigger fn_set_fecha_vencimiento (SLA)
    - Retorna el UUID del caso insertado para que el consumer notifique a Redis

    Kwargs opcionales agregados en sprint Tutelas (retrocompat 100%):
    - metadata_especifica: dict JSON para `pqrs_casos.metadata_especifica`.
      Si es None, se omite del INSERT y la DB aplica el default '{}'::jsonb.
    - fecha_vencimiento: datetime para `pqrs_casos.fecha_vencimiento`.
      Si es None, se omite y el trigger `fn_set_fecha_vencimiento` lo calcula.
      Si el caller lo setea para tipo_caso != TUTELA, se loguea WARN (el pipeline
      de tutelas es el único que debería precalcular fecha en Python; los PQRS
      convencionales deben dejar el cálculo al trigger/SP sectorial).

    Campos derivados del event/metadata, propagados al INSERT (sprint Tutelas
    smoke-fix 2026-04-27):
    - external_msg_id: lee event["external_msg_id"] / "message_id" / "id". Habilita
      dedup vía idx_casos_external_msg (UNIQUE parcial sobre cliente_id+ext).
    - documento_peticionante_hash: lee
      metadata_especifica["accionante"]["documento_hash"] (lo hashea enrich_tutela
      con el salt del tenant). Llenarlo en columna física habilita la query
      indexada de vinculacion.vincular_con_pqrs_previo (idx_casos_doc_hash).
    """
    tenant_id = uuid.UUID(event["tenant_id"])
    correlation_id = uuid.UUID(event["correlation_id"])

    if fecha_vencimiento is not None and result.tipo_caso != "TUTELA":
        logger.warning(
            "fecha_vencimiento precalculada para tipo_caso=%s (no-TUTELA); el trigger usualmente se encarga",
            result.tipo_caso,
        )

    asunto = event.get("subject", event.get("asunto", "Sin asunto"))[:500]
    cuerpo = (event.get("body", event.get("cuerpo", "")))[:10000]
    email_origen = event.get("sender", event.get("email_origen", ""))[:255]

    # Usar fecha del evento si viene, sino NOW() en UTC
    fecha_recibido: datetime = _parse_fecha(event.get("date") or event.get("fecha_recibido"))

    # external_msg_id: identificador del proveedor de email (Outlook Message-Id /
    # Gmail Message-Id / Kafka external id). Permite dedup vía idx_casos_external_msg
    # (UNIQUE parcial). NULL si el evento no lo trae.
    external_msg_id: Optional[str] = (
        event.get("external_msg_id") or event.get("message_id") or event.get("id") or None
    )
    if isinstance(external_msg_id, str):
        external_msg_id = external_msg_id.strip() or None

    # documento_peticionante_hash: extraído de metadata_especifica.accionante.documento_hash
    # (lo pone enrich_tutela tras hashear con salt del tenant). Llenarlo en columna física
    # habilita la query indexada de vinculacion.py (idx_casos_doc_hash).
    documento_hash: Optional[str] = None
    accionante = (metadata_especifica or {}).get("accionante")
    if isinstance(accionante, dict):
        candidato = accionante.get("documento_hash")
        if isinstance(candidato, str) and candidato:
            documento_hash = candidato

    async with pool.acquire() as conn:
        analista_id: Optional[uuid.UUID] = await _round_robin_analista(conn, tenant_id)

        borrador_estado = "PENDIENTE" if result.borrador else "SIN_PLANTILLA"

        # metadata_especifica: None → usamos {} para respetar semántica del default.
        # fecha_vencimiento: None → NULL explícito para que el trigger calcule.
        metadata_payload = json.dumps(metadata_especifica or {})

        caso_id: uuid.UUID = await conn.fetchval(
            """
            INSERT INTO pqrs_casos (
                cliente_id,
                correlation_id,
                tipo_caso,
                asunto,
                cuerpo,
                email_origen,
                estado,
                nivel_prioridad,
                asignado_a,
                borrador_respuesta,
                borrador_estado,
                fecha_recibido,
                metadata_especifica,
                fecha_vencimiento,
                external_msg_id,
                documento_peticionante_hash
            ) VALUES (
                $1, $2, $3, $4, $5, $6,
                'ABIERTO', $7, $8, $9, $10, $11,
                $12::jsonb, $13, $14, $15
            ) RETURNING id
            """,
            tenant_id,
            correlation_id,
            result.tipo_caso,
            asunto,
            cuerpo,
            email_origen,
            result.prioridad,
            analista_id,
            result.borrador,
            borrador_estado,
            fecha_recibido,
            metadata_payload,
            fecha_vencimiento,
            external_msg_id,
            documento_hash,
        )

    logger.info(
        "Caso insertado — id=%s tipo=%s prioridad=%s analista=%s correlation_id=%s",
        caso_id, result.tipo_caso, result.prioridad, analista_id, correlation_id,
    )
    return caso_id


async def _round_robin_analista(
    conn: asyncpg.Connection,
    tenant_id: uuid.UUID,
) -> Optional[uuid.UUID]:
    """
    Selecciona el analista activo del tenant con menor número de casos ABIERTOS.
    ORDER BY COUNT garantiza distribución equitativa sin estado externo (Redis).
    Retorna None si el tenant no tiene analistas activos.
    """
    row = await conn.fetchrow(
        """
        SELECT u.id
        FROM usuarios u
        WHERE u.cliente_id = $1
          AND u.rol IN ('analista', 'abogado')
          AND u.is_active = TRUE
        ORDER BY (
            SELECT COUNT(*)
            FROM pqrs_casos p
            WHERE p.asignado_a = u.id
              AND p.estado = 'ABIERTO'
        ) ASC,
        u.created_at ASC
        LIMIT 1
        """,
        tenant_id,
    )
    return row["id"] if row else None


def _parse_fecha(raw) -> datetime:
    """Convierte la fecha del evento a datetime timezone-aware (UTC)."""
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if isinstance(raw, str):
        # Primary: ISO 8601 via stdlib. Maneja "Z" y offsets.
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
        # Fallback: pandas si está instalado (formatos raros: RFC 822, etc.).
        try:
            import pandas as pd
            dt = pd.to_datetime(raw).to_pydatetime()
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)
