import uuid
from typing import Dict, Any, Optional

import asyncpg
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.core.db import get_db_connection
from app.services.ai_engine import analizar_pqr_documento, redactar_borrador_legal
from app.core.security import get_current_user, UserInToken


class DraftRequest(BaseModel):
    save: Optional[bool] = False

router = APIRouter()

@router.get("/extract/{caso_id}")
async def extraer_entidades(
    caso_id: str,
    current_user: UserInToken = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    """Ruta para que la IA extraiga información puntual de un caso existente."""
    caso = await db.fetchrow("SELECT cuerpo, asunto FROM pqrs_casos WHERE id = $1", uuid.UUID(caso_id))
    if not caso:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    info_extraida = await analizar_pqr_documento(caso['asunto'], caso['cuerpo'])
    return {"status": "success", "data": info_extraida}

@router.post("/draft/{caso_id}")
async def generar_draft(
    caso_id: str,
    body: DraftRequest = DraftRequest(),
    current_user: UserInToken = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    caso = await db.fetchrow("SELECT * FROM pqrs_casos WHERE id = $1", uuid.UUID(caso_id))
    if not caso:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    draft = await redactar_borrador_legal(dict(caso))
    if body.save:
        await db.execute(
            "UPDATE pqrs_casos SET borrador_respuesta = $1, borrador_estado = 'PENDIENTE' WHERE id = $2",
            draft, uuid.UUID(caso_id),
        )
    return {"status": "success", "draft": draft}
