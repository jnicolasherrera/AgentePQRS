"""
vinculacion.py — Vinculación automática tutela → PQRS previo.

Dada una tutela nueva con `documento_peticionante_hash`, busca PQRS anteriores
del mismo tenant con el mismo hash en una ventana de N días y determina el
motivo de vinculación (PQRS previo sin respuesta, respuesta insatisfactoria,
múltiples matches).

El resultado se persiste en `pqrs_casos.metadata_especifica.vinculacion` como
JSONB (mezclado con el existente via jsonb concat `||`).

Cross-tenant SAFE: la query filtra por cliente_id, así un tenant jamás ve PQRS
de otro tenant (además la policy RLS sobre pqrs_casos lo garantiza a nivel DB).

Devuelve None si no hay matches; en ese caso no se persiste nada.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg

logger = logging.getLogger("VINCULACION")


async def vincular_con_pqrs_previo(
    caso_id: uuid.UUID,
    cliente_id: uuid.UUID,
    doc_hash: str,
    conn: asyncpg.Connection,
    ventana_dias: int = 30,
) -> Optional[dict[str, Any]]:
    """
    Busca hasta 5 PQRS anteriores del mismo tenant con el mismo `doc_hash`
    en la ventana de `ventana_dias`. Excluye el caso actual y excluye tutelas
    previas (solo matchea contra PQRS "normales").

    Motivos posibles:
    - 'PQRS_NO_CONTESTADO': el primer match no tiene fecha de respuesta (enviado_at IS NULL).
    - 'RESPUESTA_INSATISFACTORIA': el primer match ya tiene respuesta pero vino una tutela.
    - 'MULTIPLE_MATCHES': hay >1 match.
    - None: no hay matches → no se persiste vinculación.

    Retorna dict con {matches, motivo, data} o None.
    """
    rows = await conn.fetch(
        """
        SELECT id, numero_radicado, tipo_caso, estado, fecha_recibido, enviado_at
        FROM pqrs_casos
        WHERE cliente_id = $1
          AND documento_peticionante_hash = $2
          AND tipo_caso != 'TUTELA'
          AND id != $3
          AND fecha_recibido >= NOW() - ($4 || ' days')::interval
        ORDER BY fecha_recibido DESC
        LIMIT 5
        """,
        cliente_id, doc_hash, caso_id, str(ventana_dias),
    )

    if not rows:
        return None

    matches: list[dict[str, Any]] = []
    for r in rows:
        matches.append({
            "id": str(r["id"]),
            "numero_radicado": r["numero_radicado"],
            "tipo_caso": r["tipo_caso"],
            "estado": r["estado"],
            "fecha_recibido": r["fecha_recibido"].isoformat() if r["fecha_recibido"] else None,
            "enviado_at": r["enviado_at"].isoformat() if r["enviado_at"] else None,
        })

    # Determinar motivo.
    if len(matches) > 1:
        motivo = "MULTIPLE_MATCHES"
    elif matches[0]["enviado_at"] is None:
        motivo = "PQRS_NO_CONTESTADO"
    else:
        motivo = "RESPUESTA_INSATISFACTORIA"

    vinculacion_data = {
        "ventana_dias": ventana_dias,
        "encontrado_at": datetime.now(timezone.utc).isoformat(),
        "motivo": motivo,
        "matches_ids": [m["id"] for m in matches],
    }

    # Persistir en metadata_especifica.vinculacion (merge JSONB).
    try:
        await conn.execute(
            """
            UPDATE pqrs_casos
            SET metadata_especifica = COALESCE(metadata_especifica, '{}'::jsonb)
                || jsonb_build_object('vinculacion', $1::jsonb)
            WHERE id = $2
            """,
            json.dumps(vinculacion_data),
            caso_id,
        )
        logger.info(
            "Vinculación persistida — caso=%s motivo=%s matches=%d",
            caso_id, motivo, len(matches),
        )
    except Exception:
        logger.exception(
            "UPDATE de vinculacion falló para caso %s; sigue sin persistir", caso_id,
        )

    return {"matches": matches, "motivo": motivo, "data": vinculacion_data}
