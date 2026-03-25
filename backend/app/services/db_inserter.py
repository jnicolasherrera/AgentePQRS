"""
db_inserter.py — Sprint 2: El Cerebro
Persiste el resultado de clasificación en pqrs_casos usando asyncpg
con el rol aequitas_worker (BYPASSRLS). No usa JWT ni get_db_connection de FastAPI.
El trigger fn_set_fecha_vencimiento() calcula SLA automáticamente en el INSERT.
El trigger fn_audit_pqrs_casos() registra en logs_auditoria automáticamente.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from app.services.ai_classifier import ClassificationResult

logger = logging.getLogger("DB_INSERTER")


async def insert_pqrs_caso(
    event: dict,
    result: ClassificationResult,
    pool: asyncpg.Pool,
) -> uuid.UUID:
    """
    Inserta un nuevo caso PQRS en PostgreSQL.
    - Ejecuta round-robin para asignar al analista con menor carga activa en el tenant
    - Preserva correlation_id del evento Kafka (trazabilidad end-to-end)
    - Popula fecha_recibido para activar el trigger fn_set_fecha_vencimiento (SLA)
    - Retorna el UUID del caso insertado para que el consumer notifique a Redis
    """
    tenant_id = uuid.UUID(event["tenant_id"])
    correlation_id = uuid.UUID(event["correlation_id"])

    asunto = event.get("subject", event.get("asunto", "Sin asunto"))[:500]
    cuerpo = (event.get("body", event.get("cuerpo", "")))[:10000]
    email_origen = event.get("sender", event.get("email_origen", ""))[:255]

    # Usar fecha del evento si viene, sino NOW() en UTC
    fecha_recibido: datetime = _parse_fecha(event.get("date") or event.get("fecha_recibido"))

    async with pool.acquire() as conn:
        analista_id: Optional[uuid.UUID] = await _round_robin_analista(conn, tenant_id)

        borrador_estado = "PENDIENTE" if result.borrador else "SIN_PLANTILLA"

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
                fecha_recibido
            ) VALUES (
                $1, $2, $3, $4, $5, $6,
                'ABIERTO', $7, $8, $9, $10, $11
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
          AND u.rol = 'analista'
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
        try:
            import pandas as pd
            dt = pd.to_datetime(raw).to_pydatetime()
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)
