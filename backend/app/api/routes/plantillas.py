"""Endpoints de plantillas de respuesta (sprint FlexFintech 2026-05-27 — bloque 7).

Lista plantillas activas del tenant filtradas por workflow para que el frontend
muestre el selector en la vista detalle del caso (típico: Atención al Cliente
de FlexFintech con sus 49 plantillas).
"""

import uuid
import logging
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException

from app.core.db import get_db_connection
from app.core.security import get_current_user, UserInToken

logger = logging.getLogger("PLANTILLAS_ROUTER")

router = APIRouter()


@router.get("")
async def listar_plantillas(
    workflow: Optional[str] = None,  # PQRS | ATENCION_CLIENTE | None=ambos
    cliente_id: Optional[str] = None,  # solo lo respeta super_admin
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
) -> List[Dict[str, Any]]:
    """Lista plantillas activas del tenant del user (o las del `cliente_id`
    para super_admin), opcionalmente filtradas por `workflow`.

    Respuesta: array de plantillas listas para mostrar en el selector del
    detalle del caso. `cuerpo` viene completo (puede ser largo); el frontend
    decide si mostrarlo en preview o full.
    """
    if workflow is not None and workflow not in ("PQRS", "ATENCION_CLIENTE"):
        raise HTTPException(status_code=400, detail="workflow debe ser PQRS o ATENCION_CLIENTE")

    es_super = current_user.role == "super_admin"

    filtros = ["is_active = TRUE"]
    params: list = []
    idx = 1

    if es_super and cliente_id:
        filtros.append(f"cliente_id = ${idx}::uuid")
        params.append(uuid.UUID(cliente_id))
        idx += 1
    elif not es_super:
        filtros.append(f"cliente_id = ${idx}::uuid")
        params.append(uuid.UUID(current_user.tenant_uuid))
        idx += 1
    # super_admin sin cliente_id => ve todas (no es el caso común; default
    # frontend admin de tenant manda su cliente_id implícito por JWT).

    if workflow:
        filtros.append(f"tipo_workflow = ${idx}")
        params.append(workflow)
        idx += 1

    where = " AND ".join(filtros)
    rows = await conn.fetch(
        f"""SELECT id, cliente_id, problematica, contexto, cuerpo, keywords,
                   tipo_workflow, created_at
            FROM plantillas_respuesta
            WHERE {where}
            ORDER BY tipo_workflow, problematica""",
        *params,
    )

    return [
        {
            "id": str(r["id"]),
            "cliente_id": str(r["cliente_id"]),
            "problematica": r["problematica"],
            "contexto": r["contexto"],
            "cuerpo": r["cuerpo"],
            "keywords": list(r["keywords"]) if r["keywords"] else [],
            "tipo_workflow": r["tipo_workflow"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
