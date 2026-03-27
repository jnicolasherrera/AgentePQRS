import base64
import uuid
import json
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.db import get_db_connection
from app.core.security import get_current_user, UserInToken, verify_password
from app.services.storage_engine import get_download_url, upload_file, download_file, client as minio_client, BUCKET_NAME
from app.services.zoho_engine import ZohoServiceV2


def _md_to_html(text: str) -> str:
    import re
    text = re.sub(r'^### (.+)$', r'<h4 style="margin:12px 0 4px">\1</h4>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$',  r'<h3 style="margin:14px 0 6px">\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$',   r'<h2 style="margin:16px 0 8px">\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__',     r'<strong>\1</strong>', text)
    text = re.sub(r'\*([^*\n]+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_([^_\n]+?)_',   r'<em>\1</em>', text)
    text = text.replace("\n", "<br>")
    return text


def _firma_html() -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "..", "static", "firma_correo.jpeg")
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<br><img src="data:image/jpeg;base64,{b64}" style="max-width:560px;display:block;" alt="Firma" />'
    except Exception:
        return ""


def _send_via_gmail(to_email: str, subject: str, body: str) -> bool:
    """Fallback SMTP para tenants sin Zoho configurado (demo)."""
    gmail_user = os.environ.get("DEMO_GMAIL_USER", "")
    gmail_pass = os.environ.get("DEMO_GMAIL_PASSWORD", "")
    if not gmail_user or not gmail_pass:
        return False
    try:
        firma = _firma_html()
        html_body = (
            "<div style='font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.6'>"
            + _md_to_html(body)
            + firma
            + "</div>"
        )
        msg = MIMEMultipart("alternative")
        msg["From"]    = f"FlexPQR <{gmail_user}>"
        msg["To"]      = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, to_email, msg.as_string())
        return True
    except Exception as e:
        logging.getLogger("CASOS_ROUTER").error(f"Gmail SMTP fallback error: {e}")
        return False

logger = logging.getLogger("CASOS_ROUTER")


def _text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    from difflib import SequenceMatcher
    return round(SequenceMatcher(None, a[:2000], b[:2000]).ratio(), 4)


router = APIRouter()



@router.get("/borrador/pendientes")
async def listar_pendientes(
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
) -> List[Dict[str, Any]]:
    rows = await conn.fetch(
        """SELECT id, email_origen, asunto, tipo_caso, nivel_prioridad,
                  fecha_recibido, borrador_respuesta, problematica_detectada
           FROM pqrs_casos WHERE borrador_estado = 'PENDIENTE'
           ORDER BY fecha_recibido ASC LIMIT 100""",
    )
    return [
        {
            "id": str(r["id"]),
            "email_origen": r["email_origen"],
            "asunto": r["asunto"],
            "tipo": r["tipo_caso"],
            "prioridad": r["nivel_prioridad"],
            "fecha": r["fecha_recibido"].isoformat() if r["fecha_recibido"] else None,
            "borrador_respuesta": r["borrador_respuesta"],
            "problematica": r["problematica_detectada"],
        }
        for r in rows
    ]


@router.get("/enviados/historial")
async def historial_enviados(
    cliente_id: Optional[str] = None,
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
) -> List[Dict[str, Any]]:
    if current_user.role not in ["admin", "super_admin", "analista"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    es_super = current_user.role == "super_admin"

    if current_user.role == "analista":
        rows = await conn.fetch(
            """SELECT a.id, a.caso_id, a.lote_id, a.created_at,
                      u.nombre AS abogado_nombre,
                      c.email_origen, c.asunto, c.tipo_caso, c.nivel_prioridad
               FROM audit_log_respuestas a
               JOIN usuarios u ON u.id = a.usuario_id
               JOIN pqrs_casos c ON c.id = a.caso_id
               WHERE a.accion = 'ENVIADO_LOTE' AND a.usuario_id = $1
               ORDER BY a.created_at DESC LIMIT 500""",
            uuid.UUID(current_user.usuario_id),
        )
    elif es_super and not cliente_id:
        rows = await conn.fetch(
            """SELECT a.id, a.caso_id, a.lote_id, a.created_at,
                      u.nombre AS abogado_nombre,
                      c.email_origen, c.asunto, c.tipo_caso, c.nivel_prioridad
               FROM audit_log_respuestas a
               JOIN usuarios u ON u.id = a.usuario_id
               JOIN pqrs_casos c ON c.id = a.caso_id
               WHERE a.accion = 'ENVIADO_LOTE'
               ORDER BY a.created_at DESC LIMIT 500""",
        )
    else:
        tid = uuid.UUID(cliente_id) if (es_super and cliente_id) else uuid.UUID(current_user.tenant_uuid)
        rows = await conn.fetch(
            """SELECT a.id, a.caso_id, a.lote_id, a.created_at,
                      u.nombre AS abogado_nombre,
                      c.email_origen, c.asunto, c.tipo_caso, c.nivel_prioridad
               FROM audit_log_respuestas a
               JOIN usuarios u ON u.id = a.usuario_id
               JOIN pqrs_casos c ON c.id = a.caso_id
               WHERE a.accion = 'ENVIADO_LOTE' AND c.cliente_id = $1
               ORDER BY a.created_at DESC LIMIT 500""",
            tid,
        )
    return [
        {
            "id": str(r["id"]),
            "caso_id": str(r["caso_id"]),
            "lote_id": str(r["lote_id"]) if r["lote_id"] else None,
            "fecha_envio": r["created_at"].isoformat(),
            "abogado": r["abogado_nombre"],
            "email_destino": r["email_origen"],
            "asunto": r["asunto"],
            "tipo": r["tipo_caso"],
            "prioridad": r["nivel_prioridad"],
        }
        for r in rows
    ]


@router.get("/metricas/respuestas")
async def metricas_respuestas(
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
    cliente_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Solo administradores")
    if current_user.role == "super_admin" and cliente_id:
        tid = uuid.UUID(cliente_id)
    else:
        tid = uuid.UUID(current_user.tenant_uuid)
    respondidos_hoy = await conn.fetchval(
        """SELECT COUNT(*) FROM audit_log_respuestas a JOIN pqrs_casos c ON c.id=a.caso_id
           WHERE a.accion='ENVIADO_LOTE' AND c.cliente_id=$1 AND a.created_at >= NOW()-INTERVAL '24 hours'""", tid)
    respondidos_semana = await conn.fetchval(
        """SELECT COUNT(*) FROM audit_log_respuestas a JOIN pqrs_casos c ON c.id=a.caso_id
           WHERE a.accion='ENVIADO_LOTE' AND c.cliente_id=$1 AND a.created_at >= NOW()-INTERVAL '7 days'""", tid)
    tiempo_promedio = await conn.fetchval(
        """SELECT AVG(EXTRACT(EPOCH FROM (enviado_at - fecha_recibido))/3600)
           FROM pqrs_casos WHERE cliente_id=$1 AND borrador_estado='ENVIADO' AND enviado_at IS NOT NULL""", tid)
    total = await conn.fetchval("SELECT COUNT(*) FROM pqrs_casos WHERE cliente_id=$1", tid)
    con_plantilla = await conn.fetchval(
        "SELECT COUNT(*) FROM pqrs_casos WHERE cliente_id=$1 AND plantilla_id IS NOT NULL", tid)
    por_abogado_rows = await conn.fetch(
        """SELECT u.nombre, COUNT(*) AS enviados FROM audit_log_respuestas a
           JOIN pqrs_casos c ON c.id=a.caso_id JOIN usuarios u ON u.id=a.usuario_id
           WHERE a.accion='ENVIADO_LOTE' AND c.cliente_id=$1 AND a.created_at >= NOW()-INTERVAL '7 days'
           GROUP BY u.nombre ORDER BY enviados DESC""", tid)
    return {
        "respondidos_hoy": respondidos_hoy or 0,
        "respondidos_semana": respondidos_semana or 0,
        "tiempo_promedio_horas": round(float(tiempo_promedio), 1) if tiempo_promedio else 0.0,
        "tasa_cobertura_plantilla": round((con_plantilla / total * 100) if total else 0, 1),
        "por_abogado": [{"nombre": r["nombre"], "enviados": r["enviados"]} for r in por_abogado_rows],
    }


@router.get("/{caso_id}")
async def get_caso_detalle(
    caso_id: str,
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
) -> Dict[str, Any]:
    caso = await conn.fetchrow(
        """SELECT c.id, c.cliente_id, c.email_origen, c.asunto, c.cuerpo, c.estado, c.nivel_prioridad,
                  c.fecha_recibido, c.tipo_caso, c.fecha_vencimiento,
                  c.borrador_respuesta, c.borrador_estado, c.problematica_detectada,
                  c.asignado_a, u.nombre AS asignado_nombre
           FROM pqrs_casos c
           LEFT JOIN usuarios u ON u.id = c.asignado_a
           WHERE c.id = $1""",
        uuid.UUID(caso_id),
    )
    if not caso:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    comentarios_rows = await conn.fetch(
        """SELECT id, comentario, tipo_evento, created_at
           FROM pqrs_comentarios WHERE caso_id = $1 ORDER BY created_at ASC""",
        uuid.UUID(caso_id),
    )
    adjuntos_rows = await conn.fetch(
        "SELECT id, nombre_archivo, storage_path, content_type, tamano_bytes FROM pqrs_adjuntos WHERE caso_id = $1",
        uuid.UUID(caso_id),
    )
    comentarios = [
        {
            "id": str(r["id"]),
            "texto": r["comentario"],
            "autor": "Sistema AI" if r["tipo_evento"] != "COMENTARIO" else "Usuario",
            "fecha": r["created_at"].isoformat(),
            "es_sistema": r["tipo_evento"] != "COMENTARIO",
        }
        for r in comentarios_rows
    ] or [{"id": "init", "texto": "Caso ingresado y clasificado en Triaje automático.",
            "autor": "Sistema AI", "fecha": caso["fecha_recibido"].isoformat(), "es_sistema": True}]
    return {
        "id": str(caso["id"]),
        "email_origen": caso["email_origen"],
        "asunto": caso["asunto"],
        "cuerpo": caso["cuerpo"] or "Sin contenido",
        "estado": caso["estado"],
        "prioridad": caso["nivel_prioridad"],
        "tipo": caso["tipo_caso"],
        "fecha": caso["fecha_recibido"].isoformat() if caso["fecha_recibido"] else None,
        "fecha_vencimiento": caso["fecha_vencimiento"].isoformat() if caso["fecha_vencimiento"] else None,
        "canal": "EMAIL",
        "borrador_respuesta": caso["borrador_respuesta"],
        "borrador_estado": caso["borrador_estado"],
        "problematica_detectada": caso["problematica_detectada"],
        "asignado_a": str(caso["asignado_a"]) if caso["asignado_a"] else None,
        "asignado_nombre": caso["asignado_nombre"],
        "comentarios": comentarios,
        "archivos": [
            {
                "id": str(r["id"]),
                "nombre": r["nombre_archivo"],
                "tamano": r["tamano_bytes"],
                "type": r["content_type"],
                "url": f"/api/v2/casos/{caso_id}/adjuntos/{r['id']}/download",
            }
            for r in adjuntos_rows
        ],
    }


@router.get("/{caso_id}/adjuntos/{adjunto_id}/download")
async def download_adjunto(
    caso_id: str,
    adjunto_id: str,
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
):
    row = await conn.fetchrow(
        "SELECT nombre_archivo, storage_path, content_type FROM pqrs_adjuntos WHERE id = $1 AND caso_id = $2",
        uuid.UUID(adjunto_id), uuid.UUID(caso_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Adjunto no encontrado")

    try:
        obj = minio_client.get_object(BUCKET_NAME, row["storage_path"])
        content_type = row["content_type"] or "application/octet-stream"
        filename = row["nombre_archivo"]
        return StreamingResponse(
            obj,
            media_type=content_type,
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
    except Exception as e:
        logger.error(f"Error descargando adjunto {adjunto_id}: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener el archivo")


@router.patch("/{caso_id}")
async def update_caso(
    caso_id: str, payload: dict,
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
):
    updates, values = [], []
    if "estado" in payload:
        updates.append(f"estado = ${len(values)+1}"); values.append(payload["estado"])
    if "prioridad" in payload:
        updates.append(f"nivel_prioridad = ${len(values)+1}"); values.append(payload["prioridad"])
    if "asignado_a" in payload:
        usuario_destino = await conn.fetchrow(
            """SELECT id FROM usuarios
               WHERE id = $1 AND cliente_id = $2 AND is_active = TRUE""",
            uuid.UUID(payload["asignado_a"]),
            uuid.UUID(current_user.tenant_uuid),
        )
        if not usuario_destino:
            raise HTTPException(status_code=400, detail="Usuario destino no válido")
        updates.append(f"asignado_a = ${len(values)+1}")
        values.append(uuid.UUID(payload["asignado_a"]))
    if not updates:
        return {"status": "ok", "message": "No changes"}
    updates.append(f"updated_at = NOW()")
    values.append(uuid.UUID(caso_id))
    updated_id = await conn.fetchval(
        f"UPDATE pqrs_casos SET {', '.join(updates)} WHERE id = ${len(values)} RETURNING id", *values)
    if not updated_id:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    if "asignado_a" in payload:
        await conn.execute(
            """INSERT INTO audit_log_respuestas
               (caso_id, usuario_id, accion, metadata)
               VALUES ($1, $2, 'REASIGNADO', $3)""",
            uuid.UUID(caso_id),
            uuid.UUID(current_user.usuario_id),
            json.dumps({"asignado_a": payload["asignado_a"]}),
        )
    return {"status": "ok", "id": str(updated_id)}


class BorradorUpdateRequest(BaseModel):
    texto: str

@router.put("/{caso_id}/borrador")
async def editar_borrador(
    caso_id: str, body: BorradorUpdateRequest,
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
):
    caso = await conn.fetchrow(
        "SELECT id, cliente_id, tipo_caso, borrador_respuesta FROM pqrs_casos WHERE id = $1",
        uuid.UUID(caso_id),
    )
    if not caso:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    original_ai = caso["borrador_respuesta"] or ""

    await conn.execute(
        "UPDATE pqrs_casos SET borrador_respuesta = $1 WHERE id = $2",
        body.texto, caso["id"],
    )
    await conn.execute(
        "INSERT INTO audit_log_respuestas (caso_id, usuario_id, accion, metadata) VALUES ($1,$2,'BORRADOR_EDITADO',$3)",
        caso["id"], uuid.UUID(current_user.usuario_id), json.dumps({"chars": len(body.texto)}),
    )

    if original_ai and body.texto != original_ai:
        similarity = _text_similarity(original_ai, body.texto)
        try:
            await conn.execute(
                """INSERT INTO borrador_feedback
                   (caso_id, cliente_id, tipo_caso, original_ai, editado_usuario, similarity_score)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                caso["id"], caso["cliente_id"], caso["tipo_caso"],
                original_ai[:2000], body.texto[:2000], similarity,
            )
        except Exception as e:
            logger.debug(f"Feedback log skipped: {e}")

    return {"ok": True}


@router.post("/{caso_id}/rechazar-borrador")
async def rechazar_borrador(
    caso_id: str,
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
):
    await conn.execute(
        "UPDATE pqrs_casos SET borrador_estado = 'RECHAZADO' WHERE id = $1", uuid.UUID(caso_id))
    await conn.execute(
        "INSERT INTO audit_log_respuestas (caso_id, usuario_id, accion) VALUES ($1,$2,'RECHAZADO')",
        uuid.UUID(caso_id), uuid.UUID(current_user.usuario_id),
    )
    return {"ok": True}


@router.post("/{caso_id}/reply-adjuntos")
async def upload_reply_adjunto(
    caso_id: str,
    file: UploadFile = File(...),
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection),
):
    caso = await conn.fetchrow(
        "SELECT id, cliente_id FROM pqrs_casos WHERE id = $1::uuid", uuid.UUID(caso_id))
    if not caso:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo demasiado grande (máx 10MB)")

    adj_id = uuid.uuid4()
    safe_name = f"{adj_id}_{file.filename}"
    storage_path = await upload_file(content, safe_name, folder=f"reply/{caso_id}")
    if not storage_path:
        raise HTTPException(status_code=500, detail="Error al subir archivo")

    await conn.execute(
        """INSERT INTO pqrs_adjuntos
           (id, caso_id, cliente_id, nombre_archivo, storage_path, content_type, tamano_bytes, es_reply)
           VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE)""",
        adj_id, caso["id"], caso["cliente_id"],
        file.filename, storage_path,
        file.content_type or "application/octet-stream", len(content),
    )
    return {"adjunto_id": str(adj_id), "nombre": file.filename,
            "content_type": file.content_type, "tamano": len(content)}


@router.delete("/{caso_id}/reply-adjuntos/{adjunto_id}")
async def delete_reply_adjunto(
    caso_id: str,
    adjunto_id: str,
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection),
):
    await conn.execute(
        "DELETE FROM pqrs_adjuntos WHERE id = $1::uuid AND caso_id = $2::uuid AND es_reply = TRUE",
        uuid.UUID(adjunto_id), uuid.UUID(caso_id),
    )
    return {"ok": True}


class AprobarloteRequest(BaseModel):
    caso_ids: List[str]
    password: str

@router.post("/aprobar-lote")
async def aprobar_lote(
    body: AprobarloteRequest, request: Request,
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
):
    if len(body.caso_ids) > 10:
        raise HTTPException(status_code=400, detail="Máximo 10 casos por lote")
    if not body.caso_ids:
        raise HTTPException(status_code=400, detail="Se requiere al menos un caso")

    user_row = await conn.fetchrow(
        "SELECT password_hash FROM usuarios WHERE id = $1", uuid.UUID(current_user.usuario_id))
    if not user_row or not verify_password(body.password, user_row["password_hash"]):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    buzon = await conn.fetchrow(
        """SELECT email_buzon, azure_client_id, azure_client_secret, zoho_refresh_token, zoho_account_id
           FROM config_buzones WHERE cliente_id=$1 AND proveedor='ZOHO' AND is_active=TRUE LIMIT 1""",
        uuid.UUID(current_user.tenant_uuid),
    )
    zoho = ZohoServiceV2(
        buzon["azure_client_id"], buzon["azure_client_secret"],
        buzon["zoho_refresh_token"], buzon["zoho_account_id"]
    ) if buzon else None

    lote_id = uuid.uuid4()
    now     = datetime.now(timezone.utc)
    ip      = request.client.host if request.client else None
    enviados, errores = [], []

    for cid in body.caso_ids:
        try:
            caso = await conn.fetchrow(
                "SELECT id, email_origen, asunto, borrador_respuesta FROM pqrs_casos WHERE id = $1",
                uuid.UUID(cid),
            )
            if not caso or not caso["borrador_respuesta"]:
                errores.append({"caso_id": cid, "motivo": "Sin borrador o no encontrado"}); continue

            # Cargar adjuntos de reply desde MinIO
            adj_rows = await conn.fetch(
                "SELECT storage_path, nombre_archivo, content_type FROM pqrs_adjuntos WHERE caso_id=$1 AND es_reply=TRUE",
                caso["id"],
            )
            adjuntos_data = []
            for ar in adj_rows:
                file_bytes = download_file(ar["storage_path"])
                if file_bytes:
                    adjuntos_data.append({
                        "nombre": ar["nombre_archivo"],
                        "content": file_bytes,
                        "content_type": ar["content_type"] or "application/octet-stream",
                    })

            subject = f"Re: {caso['asunto']}"
            if zoho:
                ok = zoho.send_reply(caso["email_origen"], subject, caso["borrador_respuesta"],
                                     buzon["email_buzon"], adjuntos=adjuntos_data or None)
            else:
                ok = _send_via_gmail(caso["email_origen"], subject, caso["borrador_respuesta"])
            if ok:
                await conn.execute(
                    """UPDATE pqrs_casos SET borrador_estado='ENVIADO', estado='CERRADO',
                       aprobado_por=$1, aprobado_at=$2, enviado_at=$2 WHERE id=$3""",
                    uuid.UUID(current_user.usuario_id), now, caso["id"],
                )
                await conn.execute(
                    """INSERT INTO audit_log_respuestas
                           (caso_id, usuario_id, accion, lote_id, ip_origen, metadata)
                       VALUES ($1,$2,'ENVIADO_LOTE',$3,$4,$5)""",
                    caso["id"], uuid.UUID(current_user.usuario_id), lote_id, ip,
                    json.dumps({"email_destino": caso["email_origen"], "asunto": subject,
                                "lote_size": len(body.caso_ids)}),
                )
                enviados.append(cid)
            else:
                errores.append({"caso_id": cid, "motivo": "Error Zoho al enviar"})
        except Exception as e:
            logger.error(f"Error lote caso {cid}: {e}")
            errores.append({"caso_id": cid, "motivo": str(e)})

    return {"enviados": len(enviados), "lote_id": str(lote_id), "errores": errores}
