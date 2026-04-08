import uuid
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.core.db import get_db_connection
from app.core.security import get_current_user, UserInToken, verify_password, get_password_hash
from app.services.zoho_engine import ZohoServiceV2

router = APIRouter()


class UpdateNombreRequest(BaseModel):
    nombre: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class FeedbackRequest(BaseModel):
    es_pqrs: bool
    clasificacion_correcta: Optional[str] = None


@router.put("/me/nombre")
async def update_nombre(
    body: UpdateNombreRequest,
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection)
):
    await conn.execute(
        "UPDATE usuarios SET nombre = $1 WHERE id = $2",
        body.nombre.strip(), current_user.usuario_id
    )
    return {"ok": True, "nombre": body.nombre.strip()}


@router.post("/me/password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection)
):
    row = await conn.fetchrow(
        "SELECT password_hash FROM usuarios WHERE id = $1", current_user.usuario_id
    )
    if not row or not verify_password(body.current_password, row["password_hash"]):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe tener al menos 8 caracteres")
    new_hash = get_password_hash(body.new_password)
    await conn.execute(
        "UPDATE usuarios SET password_hash = $1 WHERE id = $2",
        new_hash, current_user.usuario_id
    )
    return {"ok": True}


@router.get("/team")
async def get_team(
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection)
) -> List[Dict[str, Any]]:
    if current_user.role not in ['admin', 'super_admin', 'coordinador']:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    rows = await conn.fetch(
        """SELECT id, nombre, email, rol, is_active, created_at
           FROM usuarios WHERE cliente_id = $1 AND is_active = TRUE
             AND rol IN ('analista', 'abogado', 'coordinador', 'admin')
           ORDER BY nombre ASC""",
        current_user.tenant_uuid
    )
    return [
        {
            "id": str(r["id"]),
            "nombre": r["nombre"],
            "email": r["email"],
            "rol": r["rol"],
            "is_active": r["is_active"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


@router.get("/config/buzones")
async def get_buzones(
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection)
) -> List[Dict[str, Any]]:
    if current_user.role not in ['admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Solo administradores")
    rows = await conn.fetch(
        """SELECT email_buzon, proveedor, is_active
           FROM config_buzones WHERE cliente_id = $1 ORDER BY email_buzon ASC""",
        current_user.tenant_uuid
    )
    return [
        {
            "email": r["email_buzon"],
            "proveedor": r["proveedor"],
            "is_active": r["is_active"],
        }
        for r in rows
    ]


@router.get("/casos")
async def listar_casos_admin(
    page: int = 1,
    page_size: int = 50,
    tipo: Optional[str] = None,
    estado: Optional[str] = None,
    asignado_a: Optional[str] = None,
    es_pqrs: Optional[bool] = None,
    q: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: Optional[str] = None,
    cliente_id: Optional[str] = None,
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection),
) -> Dict[str, Any]:
    if current_user.role not in ['admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Solo administradores")

    es_super = current_user.role == 'super_admin'
    filtros = ["1=1"]
    params: list = []
    idx = 1

    if es_super and cliente_id:
        filtros.append(f"c.cliente_id = ${idx}::uuid")
        params.append(uuid.UUID(cliente_id))
        idx += 1
    elif not es_super:
        filtros.append(f"c.cliente_id = ${idx}::uuid")
        params.append(uuid.UUID(current_user.tenant_uuid))
        idx += 1

    if tipo:
        filtros.append(f"c.tipo_caso = ${idx}")
        params.append(tipo.upper())
        idx += 1
    if estado:
        filtros.append(f"c.estado = ${idx}")
        params.append(estado.upper())
        idx += 1
    if asignado_a:
        filtros.append(f"c.asignado_a = ${idx}::uuid")
        params.append(uuid.UUID(asignado_a))
        idx += 1
    if es_pqrs is not None:
        filtros.append(f"c.es_pqrs = ${idx}")
        params.append(es_pqrs)
        idx += 1
    if q:
        filtros.append(f"(c.asunto ILIKE ${idx} OR c.email_origen ILIKE ${idx})")
        params.append(f"%{q}%")
        idx += 1

    where = " AND ".join(filtros)
    offset = (page - 1) * page_size
    _SORT_MAP = {"radicado": "c.numero_radicado", "asunto": "c.asunto", "tipo": "c.tipo_caso", "estado": "c.estado", "prioridad": "c.nivel_prioridad", "recibido": "c.fecha_recibido", "vencimiento": "c.fecha_vencimiento", "asignado": "u.nombre"}
    sort_col = _SORT_MAP.get(sort_by or "", "c.fecha_recibido")
    sort_direction = "ASC" if sort_dir == "asc" else "DESC"

    total = await conn.fetchval(
        f"SELECT COUNT(*) FROM pqrs_casos c WHERE {where}", *params
    )
    rows = await conn.fetch(
        f"""SELECT c.id, c.numero_radicado, c.asunto, c.email_origen, c.tipo_caso,
               c.estado, c.nivel_prioridad, c.fecha_recibido, c.fecha_vencimiento,
               c.es_pqrs, c.acuse_enviado,
               u.nombre AS asignado_nombre, u.email AS asignado_email
            FROM pqrs_casos c
            LEFT JOIN usuarios u ON u.id = c.asignado_a
            WHERE {where}
            ORDER BY {sort_col} {sort_direction} NULLS LAST
            LIMIT {page_size} OFFSET {offset}""",
        *params,
    )

    items = [
        {
            "id": str(r["id"]),
            "numero_radicado": r["numero_radicado"],
            "asunto": r["asunto"],
            "email_origen": r["email_origen"],
            "tipo_caso": r["tipo_caso"],
            "estado": r["estado"],
            "nivel_prioridad": r["nivel_prioridad"],
            "fecha_recibido": r["fecha_recibido"].isoformat() if r["fecha_recibido"] else None,
            "fecha_vencimiento": r["fecha_vencimiento"].isoformat() if r["fecha_vencimiento"] else None,
            "es_pqrs": r["es_pqrs"],
            "acuse_enviado": r["acuse_enviado"],
            "asignado_nombre": r["asignado_nombre"],
            "asignado_email": r["asignado_email"],
        }
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/casos/{caso_id}/feedback")
async def marcar_feedback(
    caso_id: str,
    body: FeedbackRequest,
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection),
) -> Dict[str, Any]:
    if current_user.role not in ['admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Solo administradores")

    es_super = current_user.role == 'super_admin'
    row = await conn.fetchrow(
        "SELECT id, tipo_caso, cliente_id FROM pqrs_casos WHERE id = $1::uuid" +
        ("" if es_super else " AND cliente_id = $2::uuid"),
        *([uuid.UUID(caso_id)] if es_super else [uuid.UUID(caso_id), uuid.UUID(current_user.tenant_uuid)])
    )
    if not row:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    await conn.execute(
        "UPDATE pqrs_casos SET es_pqrs = $1 WHERE id = $2::uuid",
        body.es_pqrs, uuid.UUID(caso_id)
    )
    await conn.execute(
        """INSERT INTO pqrs_clasificacion_feedback
           (caso_id, cliente_id, clasificacion_original, clasificacion_correcta, es_pqrs, marcado_por)
           VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::uuid)""",
        uuid.UUID(caso_id), row["cliente_id"],
        row["tipo_caso"], body.clasificacion_correcta,
        body.es_pqrs, uuid.UUID(current_user.usuario_id)
    )

    # Contar correcciones acumuladas para este tenant y ajustar boost en Redis si >5
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM pqrs_clasificacion_feedback WHERE cliente_id = $1::uuid AND es_pqrs = FALSE",
        row["cliente_id"]
    )

    return {"ok": True, "feedback_count": count}


@router.delete("/casos/{caso_id}/no-pqrs")
async def eliminar_caso_no_pqrs(
    caso_id: str,
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection),
) -> Dict[str, Any]:
    if current_user.role not in ['admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Solo administradores")

    es_super = current_user.role == 'super_admin'
    row = await conn.fetchrow(
        "SELECT id, es_pqrs, cliente_id FROM pqrs_casos WHERE id = $1::uuid" +
        ("" if es_super else " AND cliente_id = $2::uuid"),
        *([uuid.UUID(caso_id)] if es_super else [uuid.UUID(caso_id), uuid.UUID(current_user.tenant_uuid)])
    )
    if not row:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    if row["es_pqrs"] is not False:
        raise HTTPException(status_code=400, detail="Solo se pueden eliminar casos marcados como No PQRS")

    caso_uuid = uuid.UUID(caso_id)
    await conn.execute("DELETE FROM pqrs_adjuntos WHERE caso_id = $1::uuid", caso_uuid)
    await conn.execute("DELETE FROM pqrs_comentarios WHERE caso_id = $1::uuid", caso_uuid)
    await conn.execute("DELETE FROM audit_log_respuestas WHERE caso_id = $1::uuid", caso_uuid)
    await conn.execute("DELETE FROM pqrs_clasificacion_feedback WHERE caso_id = $1::uuid", caso_uuid)
    await conn.execute("DELETE FROM pqrs_casos WHERE id = $1::uuid", caso_uuid)
    return {"ok": True, "deleted": caso_id}


class DeleteNoPqrsLoteRequest(BaseModel):
    caso_ids: List[str]


@router.delete("/casos/no-pqrs/lote")
async def eliminar_no_pqrs_lote(
    body: DeleteNoPqrsLoteRequest,
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection),
) -> Dict[str, Any]:
    if current_user.role not in ['admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Solo administradores")
    if not body.caso_ids:
        raise HTTPException(status_code=400, detail="Debe enviar al menos un caso_id")

    es_super = current_user.role == 'super_admin'
    uuids = [uuid.UUID(cid) for cid in body.caso_ids]

    tenant_filter = "" if es_super else " AND cliente_id = $2::uuid"
    tenant_params = [] if es_super else [uuid.UUID(current_user.tenant_uuid)]

    rows = await conn.fetch(
        f"SELECT id, es_pqrs FROM pqrs_casos WHERE id = ANY($1::uuid[]){tenant_filter}",
        uuids, *tenant_params
    )

    found_ids = {r["id"] for r in rows}
    not_found = [str(uid) for uid in uuids if uid not in found_ids]
    not_no_pqrs = [str(r["id"]) for r in rows if r["es_pqrs"] is not False]

    if not_found:
        raise HTTPException(status_code=404, detail=f"Casos no encontrados: {', '.join(not_found)}")
    if not_no_pqrs:
        raise HTTPException(status_code=400, detail=f"Casos no marcados como No PQRS: {', '.join(not_no_pqrs)}")

    await conn.execute(f"DELETE FROM pqrs_adjuntos WHERE caso_id = ANY($1::uuid[])", uuids)
    await conn.execute(f"DELETE FROM pqrs_comentarios WHERE caso_id = ANY($1::uuid[])", uuids)
    await conn.execute(f"DELETE FROM audit_log_respuestas WHERE caso_id = ANY($1::uuid[])", uuids)
    await conn.execute(f"DELETE FROM pqrs_clasificacion_feedback WHERE caso_id = ANY($1::uuid[])", uuids)
    await conn.execute(
        f"DELETE FROM pqrs_casos WHERE id = ANY($1::uuid[]){tenant_filter}",
        uuids, *tenant_params
    )

    return {"ok": True, "deleted_count": len(uuids), "deleted_ids": body.caso_ids}


class DeleteCasosLoteRequest(BaseModel):
    caso_ids: List[str]


@router.delete("/casos/lote")
async def eliminar_casos_lote(
    body: DeleteCasosLoteRequest,
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection),
) -> Dict[str, Any]:
    if current_user.role not in ['admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Solo administradores")
    if not body.caso_ids:
        raise HTTPException(status_code=400, detail="Debe enviar al menos un caso_id")

    es_super = current_user.role == 'super_admin'
    uuids = [uuid.UUID(cid) for cid in body.caso_ids]

    tenant_filter = "" if es_super else " AND cliente_id = $2::uuid"
    tenant_params = [] if es_super else [uuid.UUID(current_user.tenant_uuid)]

    rows = await conn.fetch(
        f"SELECT id FROM pqrs_casos WHERE id = ANY($1::uuid[]){tenant_filter}",
        uuids, *tenant_params
    )

    found_ids = {r["id"] for r in rows}
    not_found = [str(uid) for uid in uuids if uid not in found_ids]

    if not_found:
        raise HTTPException(status_code=404, detail=f"Casos no encontrados: {', '.join(not_found)}")

    await conn.execute("DELETE FROM pqrs_adjuntos WHERE caso_id = ANY($1::uuid[])", uuids)
    await conn.execute("DELETE FROM pqrs_comentarios WHERE caso_id = ANY($1::uuid[])", uuids)
    await conn.execute("DELETE FROM audit_log_respuestas WHERE caso_id = ANY($1::uuid[])", uuids)
    await conn.execute("DELETE FROM pqrs_clasificacion_feedback WHERE caso_id = ANY($1::uuid[])", uuids)
    await conn.execute(
        f"DELETE FROM pqrs_casos WHERE id = ANY($1::uuid[]){tenant_filter}",
        uuids, *tenant_params
    )

    return {"ok": True, "deleted_count": len(uuids), "deleted_ids": body.caso_ids}


@router.get("/clientes")
async def listar_clientes(
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection)
) -> List[Dict[str, Any]]:
    """
    Lista todos los clientes (Tenants) registrados.
    Solo accesible para usuarios con rol 'admin' o 'super_admin'.
    """
    if current_user.role not in ['admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="No tiene permisos para ver esta lista")

    # super_admin ve todos (conexion via aequitas_worker con BYPASSRLS); admin solo su tenant
    if current_user.role == 'super_admin':
        query = "SELECT id, nombre, dominio, is_active FROM clientes_tenant ORDER BY nombre ASC"
        rows = await conn.fetch(query)
    else:
        rows = await conn.fetch(
            "SELECT id, nombre, dominio, is_active FROM clientes_tenant WHERE id = $1",
            uuid.UUID(current_user.tenant_uuid)
        )

    return [
        {
            "id": str(r["id"]),
            "nombre": r["nombre"],
            "dominio": r["dominio"],
            "is_active": r["is_active"]
        } for r in rows
    ]


@router.get("/zoho/health")
async def zoho_health_check(
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
):
    if current_user.role not in ("admin", "super_admin", "coordinador"):
        raise HTTPException(status_code=403, detail="Sin permisos")
    buzon = await conn.fetchrow(
        """SELECT email_buzon, azure_client_id, azure_client_secret,
                  zoho_refresh_token, zoho_account_id
           FROM config_buzones
           WHERE cliente_id=$1 AND proveedor='ZOHO' AND is_active=TRUE LIMIT 1""",
        uuid.UUID(current_user.tenant_uuid),
    )
    if not buzon:
        return {"status": "sin_configuracion", "puede_enviar": False,
                "mensaje": "No hay buzon Zoho configurado para este tenant"}
    try:
        zoho = ZohoServiceV2(
            buzon["azure_client_id"], buzon["azure_client_secret"],
            buzon["zoho_refresh_token"], buzon["zoho_account_id"],
        )
        token = zoho._get_access_token()
        if token:
            return {"status": "operativo", "email_buzon": buzon["email_buzon"],
                    "puede_enviar": True, "mensaje": "Zoho responde correctamente"}
        return {"status": "error_auth", "email_buzon": buzon["email_buzon"],
                "puede_enviar": False, "mensaje": "No se pudo obtener access token"}
    except Exception as e:
        return {"status": "error", "email_buzon": buzon["email_buzon"],
                "puede_enviar": False, "mensaje": str(e)}
