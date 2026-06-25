import base64
import uuid
import json
import logging
import os
import re
import smtplib
from datetime import datetime, timezone
from email.mime.image import MIMEImage
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
from app.services.outlook_send_engine import OutlookSenderV2
from app.services.email_utils import md_to_html as _md_to_html


_FIRMA_CID = "firma_arc"


def _firma_path() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "..", "static", "firma_correo.jpeg")


def _firma_bytes() -> Optional[bytes]:
    try:
        with open(_firma_path(), "rb") as f:
            return f.read()
    except Exception:
        return None


def _firma_html() -> str:
    """HTML reference vía CID. Requiere que el caller adjunte la imagen como
    parte inline con Content-ID matching (_FIRMA_CID)."""
    if _firma_bytes() is None:
        return ""
    return f'<br><img src="cid:{_FIRMA_CID}" style="max-width:560px;display:block;" alt="Firma" />'


def _render_mail_html(asunto: str, cuerpo: str, sender: str, fecha) -> str:
    """Render del mail original del cliente como HTML para archivado SP.

    Sprint FlexFintech 2026-05-27 bloque 6 — decisión D5 (HTML, no .eml).
    Usado por enviar-lote post-envío para archivar en SharePoint.
    """
    import html as _h
    fecha_s = fecha.strftime("%Y-%m-%d %H:%M") if hasattr(fecha, "strftime") else str(fecha or "")
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>Mail original</title>"
        "<style>body{font-family:Arial,sans-serif;max-width:780px;margin:20px auto;color:#222}"
        "table{border-collapse:collapse;width:100%;margin-bottom:1em}"
        "th,td{text-align:left;padding:6px 10px;border:1px solid #ddd;font-size:13px}"
        "th{background:#f4f4f4;width:120px}"
        ".cuerpo{white-space:pre-wrap;border:1px solid #ddd;padding:12px;background:#fafafa}"
        "</style></head><body>"
        "<h2>Mail original</h2>"
        f"<table><tr><th>De</th><td>{_h.escape(sender or '')}</td></tr>"
        f"<tr><th>Fecha</th><td>{_h.escape(fecha_s)}</td></tr>"
        f"<tr><th>Asunto</th><td>{_h.escape(asunto or '')}</td></tr></table>"
        f"<div class='cuerpo'>{_h.escape(cuerpo or '')}</div>"
        "</body></html>"
    )


def _render_respuesta_html(subject: str, destinatario: str, cuerpo: str, fecha) -> str:
    """Render de la respuesta enviada como HTML para archivado SP."""
    import html as _h
    fecha_s = fecha.strftime("%Y-%m-%d %H:%M") if hasattr(fecha, "strftime") else str(fecha or "")
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>Respuesta enviada</title>"
        "<style>body{font-family:Arial,sans-serif;max-width:780px;margin:20px auto;color:#222}"
        "table{border-collapse:collapse;width:100%;margin-bottom:1em}"
        "th,td{text-align:left;padding:6px 10px;border:1px solid #ddd;font-size:13px}"
        "th{background:#f4f4f4;width:120px}"
        ".cuerpo{border:1px solid #ddd;padding:12px;background:#fafafa;line-height:1.5}"
        "</style></head><body>"
        "<h2>Respuesta enviada</h2>"
        f"<table><tr><th>Para</th><td>{_h.escape(destinatario or '')}</td></tr>"
        f"<tr><th>Fecha</th><td>{_h.escape(fecha_s)}</td></tr>"
        f"<tr><th>Asunto</th><td>{_h.escape(subject or '')}</td></tr></table>"
        f"<div class='cuerpo'>{_md_to_html(cuerpo or '')}</div>"
        "</body></html>"
    )


def _send_via_smtp_fallback(to_email: str, subject: str, body: str,
                            from_address: str | None = None) -> bool:
    """Fallback SMTP cuando el envío primario (Graph/Zoho) falla.

    from_address: buzón de origen del tenant (ej. clientes@flexfintech.com). Se
    usa como cabecera From para NO filtrar desde la cuenta Gmail demo. Si el
    servidor SMTP no permite ese From (Gmail rechaza dominios ajenos), hay que
    configurar SMTP_FALLBACK_USER/PASS con credenciales del propio buzón.

    Construye MIME multipart/related con firma inline (CID) para que Outlook
    y otros clientes que bloquean data: URIs rendericen la imagen.
    """
    smtp_host = os.environ.get("SMTP_FALLBACK_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_FALLBACK_PORT", "465"))
    smtp_user = os.environ.get("SMTP_FALLBACK_USER", os.environ.get("DEMO_GMAIL_USER", ""))
    smtp_pass = os.environ.get("SMTP_FALLBACK_PASS", os.environ.get("DEMO_GMAIL_PASSWORD", ""))
    if not smtp_user or not smtp_pass:
        logger.error("SMTP fallback no configurado — envío perdido para: " + to_email)
        return False
    # El From visible es el buzón del tenant si se pasó; si no, el user SMTP.
    mail_from = from_address or smtp_user
    try:
        # firma-por-tenant 2026-06-25: FF → texto (sin imagen); resto → imagen CID.
        from app.services.firma_engine import firma_html_cid, firma_bytes as _firma_tenant_bytes, usa_imagen as _usa_img
        usa_img = _usa_img(email_buzon=from_address)
        firma_data = _firma_tenant_bytes() if usa_img else None
        firma_ref = firma_html_cid(email_buzon=from_address)
        html_body = (
            "<div style='font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.6'>"
            + _md_to_html(body) + firma_ref + "</div>"
        )
        root = MIMEMultipart("related") if firma_data else MIMEMultipart("alternative")
        root["From"] = f"FlexPQR <{mail_from}>"
        root["To"] = to_email
        root["Subject"] = subject

        if firma_data:
            alt = MIMEMultipart("alternative")
            alt.attach(MIMEText(body, "plain", "utf-8"))
            alt.attach(MIMEText(html_body, "html", "utf-8"))
            root.attach(alt)

            img = MIMEImage(firma_data, _subtype="jpeg")
            img.add_header("Content-ID", f"<{_FIRMA_CID}>")
            img.add_header("Content-Disposition", "inline", filename="firma.jpg")
            root.attach(img)
        else:
            root.attach(MIMEText(body, "plain", "utf-8"))
            root.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to_email, root.as_string())
        logger.warning(f"Email enviado via SMTP fallback → {to_email}")
        return True
    except Exception as e:
        logger.error(f"SMTP fallback también falló: {e}")
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
    workflow: Optional[str] = None,  # PQRS | ATENCION_CLIENTE | None=ambos (sprint FF bloque 7)
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
) -> List[Dict[str, Any]]:
    if workflow is not None and workflow not in ("PQRS", "ATENCION_CLIENTE"):
        raise HTTPException(status_code=400, detail="workflow inválido")

    # SEC-2026-05-21: scope por tenant (super_admin ve todos). Antes devolvía
    # borradores pendientes de TODOS los tenants (leak C1).
    filtros = ["borrador_estado = 'PENDIENTE'"]
    params: list = []
    idx = 1
    if current_user.role != "super_admin":
        filtros.append(f"cliente_id = ${idx}::uuid")
        params.append(uuid.UUID(current_user.tenant_uuid))
        idx += 1
    if workflow:
        filtros.append(f"tipo_workflow = ${idx}")
        params.append(workflow)
        idx += 1

    rows = await conn.fetch(
        f"""SELECT id, email_origen, asunto, tipo_caso, nivel_prioridad,
                   fecha_recibido, borrador_respuesta, problematica_detectada,
                   tipo_workflow
            FROM pqrs_casos WHERE {" AND ".join(filtros)}
            ORDER BY fecha_recibido ASC LIMIT 100""",
        *params,
    )
    return [
        {
            "id": str(r["id"]),
            "email_origen": r["email_origen"],
            "asunto": r["asunto"],
            "tipo": r["tipo_caso"],
            "tipo_workflow": r["tipo_workflow"],
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
    workflow: Optional[str] = None,  # PQRS | ATENCION_CLIENTE | None=ambos (sprint FF bloque 7)
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
) -> List[Dict[str, Any]]:
    ROLES_PERMITIDOS = {"admin", "super_admin", "analista", "coordinador", "auditor", "abogado"}
    # Modelo "cada abogado ve lo suyo": abogado/analista ven solo SUS envíos.
    # admin/coordinador/super/auditor ven el Enviados completo del tenant.
    ROLES_VEN_TODO = {"admin", "coordinador", "super_admin", "auditor"}

    if current_user.role not in ROLES_PERMITIDOS:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    if workflow is not None and workflow not in ("PQRS", "ATENCION_CLIENTE"):
        raise HTTPException(status_code=400, detail="workflow inválido")

    es_super = current_user.role == "super_admin"

    # Query unificada con filtros dinámicos (refactor sprint FF bloque 7)
    filtros = ["a.accion = 'ENVIADO_LOTE'"]
    params: list = []
    idx = 1

    if not (es_super and not cliente_id):
        tid = uuid.UUID(cliente_id) if (es_super and cliente_id) else uuid.UUID(current_user.tenant_uuid)
        filtros.append(f"c.cliente_id = ${idx}::uuid")
        params.append(tid)
        idx += 1
        if current_user.role not in ROLES_VEN_TODO:
            filtros.append(f"a.usuario_id = ${idx}::uuid")
            params.append(uuid.UUID(current_user.usuario_id))
            idx += 1
    if workflow:
        filtros.append(f"c.tipo_workflow = ${idx}")
        params.append(workflow)
        idx += 1

    rows = await conn.fetch(
        f"""SELECT a.id, a.caso_id, a.lote_id, a.created_at,
                   u.nombre AS abogado_nombre,
                   c.email_origen, c.asunto, c.tipo_caso, c.nivel_prioridad,
                   c.tipo_workflow
            FROM audit_log_respuestas a
            JOIN usuarios u ON u.id = a.usuario_id
            JOIN pqrs_casos c ON c.id = a.caso_id
            WHERE {" AND ".join(filtros)}
            ORDER BY a.created_at DESC LIMIT 500""",
        *params,
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
            "tipo_workflow": r["tipo_workflow"],
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
                  c.asignado_a, u.nombre AS asignado_nombre, c.pqr_origenes,
                  c.tipo_workflow, c.email_respuesta_override, c.documento_peticionante,
                  c.metadata_especifica
           FROM pqrs_casos c
           LEFT JOIN usuarios u ON u.id = c.asignado_a
           WHERE c.id = $1 AND ($2 OR c.cliente_id = $3)""",
        uuid.UUID(caso_id),
        current_user.role == "super_admin",
        uuid.UUID(current_user.tenant_uuid),
    )
    if not caso:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    # PQRs vinculados (origenes): solo para tipo TUTELA, hidratamos detalles.
    pqr_origenes_data = []
    origenes = caso["pqr_origenes"] or []
    if caso["tipo_caso"] == "TUTELA" and origenes:
        rows_orig = await conn.fetch(
            """SELECT id, numero_radicado, asunto, tipo_caso, estado, fecha_recibido, email_origen
               FROM pqrs_casos
               WHERE id = ANY($1::uuid[]) AND cliente_id = $2""",
            origenes, caso["cliente_id"],
        )
        pqr_origenes_data = [
            {
                "id": str(r["id"]),
                "numero_radicado": r["numero_radicado"],
                "asunto": r["asunto"],
                "tipo_caso": r["tipo_caso"],
                "estado": r["estado"],
                "fecha_recibido": r["fecha_recibido"].isoformat() if r["fecha_recibido"] else None,
                "email_origen": r["email_origen"],
            }
            for r in rows_orig
        ]
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

    # Sprint FF bloque 7: último cambio de destinatario (si lo hubo) para badge en UI.
    destinatario_audit_row = await conn.fetchrow(
        """SELECT a.created_at, a.metadata, u.nombre AS usuario_nombre
           FROM audit_log_respuestas a
           LEFT JOIN usuarios u ON u.id = a.usuario_id
           WHERE a.caso_id = $1 AND a.accion = 'DESTINATARIO_EDITADO'
           ORDER BY a.created_at DESC LIMIT 1""",
        uuid.UUID(caso_id),
    )
    destinatario_audit = None
    if destinatario_audit_row:
        meta = destinatario_audit_row["metadata"] or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (ValueError, TypeError):
                meta = {}
        destinatario_audit = {
            "fecha": destinatario_audit_row["created_at"].isoformat(),
            "usuario_nombre": destinatario_audit_row["usuario_nombre"],
            "anterior": meta.get("anterior"),
            "nuevo": meta.get("nuevo"),
            "tipo_cambio": meta.get("tipo_cambio"),
        }

    # Sprint FF bloque 6: path SP archivado (si el caso PQRS quedó archivado).
    metadata_especifica = caso["metadata_especifica"] or {}
    if isinstance(metadata_especifica, str):
        try:
            metadata_especifica = json.loads(metadata_especifica)
        except (ValueError, TypeError):
            metadata_especifica = {}
    sp_archivo = metadata_especifica.get("sp_archivo")

    email_destinatario_efectivo = caso["email_respuesta_override"] or caso["email_origen"]

    return {
        "id": str(caso["id"]),
        "email_origen": caso["email_origen"],
        "email_respuesta_override": caso["email_respuesta_override"],
        "email_destinatario_efectivo": email_destinatario_efectivo,
        "destinatario_override_audit": destinatario_audit,
        "asunto": caso["asunto"],
        "cuerpo": caso["cuerpo"] or "Sin contenido",
        "estado": caso["estado"],
        "prioridad": caso["nivel_prioridad"],
        "tipo": caso["tipo_caso"],
        "tipo_workflow": caso["tipo_workflow"],
        "documento_peticionante": caso["documento_peticionante"],
        "sp_archivo": sp_archivo,
        "metadata_especifica": metadata_especifica,
        "fecha": caso["fecha_recibido"].isoformat() if caso["fecha_recibido"] else None,
        "fecha_vencimiento": caso["fecha_vencimiento"].isoformat() if caso["fecha_vencimiento"] else None,
        "canal": "EMAIL",
        "borrador_respuesta": caso["borrador_respuesta"],
        "borrador_estado": caso["borrador_estado"],
        "problematica_detectada": caso["problematica_detectada"],
        "asignado_a": str(caso["asignado_a"]) if caso["asignado_a"] else None,
        "asignado_nombre": caso["asignado_nombre"],
        "pqr_origenes": pqr_origenes_data,
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
    idx_id = len(values)
    # SEC-2026-05-21: scope por tenant (super_admin opera cualquiera).
    values.append(current_user.role == "super_admin")
    values.append(uuid.UUID(current_user.tenant_uuid))
    updated_id = await conn.fetchval(
        f"UPDATE pqrs_casos SET {', '.join(updates)} "
        f"WHERE id = ${idx_id} AND (${idx_id+1} OR cliente_id = ${idx_id+2}) RETURNING id", *values)
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


class DestinatarioOverrideRequest(BaseModel):
    """Body para PATCH /casos/{id}/destinatario.

    - email: nuevo destinatario (None / "" / null → quitar override y
      volver a usar `email_origen`).
    """
    email: Optional[str] = None


# Regex email moderadamente estricta (RFC 5322 light).
_EMAIL_OVERRIDE_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


@router.patch("/{caso_id}/destinatario")
async def editar_destinatario(
    caso_id: str,
    body: DestinatarioOverrideRequest,
    request: Request,
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
):
    """Editar el destinatario al que se enviará la respuesta del caso.

    Sprint FlexFintech 2026-05-27 — bloque 5.

    Cuando admin/super_admin necesita override (típico: el adjunto pide
    responder a un email distinto al `email_origen`). Setea
    `pqrs_casos.email_respuesta_override`. El endpoint enviar-lote usa
    `override or email_origen`.

    Pasar `email=null` o `""` para quitar el override (vuelve al email_origen).

    Auditoría: registra acción 'DESTINATARIO_EDITADO' en audit_log_respuestas
    con metadata `{anterior, nuevo, usuario}`.
    """
    if current_user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Solo admin / super_admin")

    nuevo_email = (body.email or "").strip().lower() or None
    if nuevo_email is not None and not _EMAIL_OVERRIDE_RE.match(nuevo_email):
        raise HTTPException(
            status_code=400,
            detail=f"Email inválido: {body.email!r}",
        )

    # Traer caso actual (con scope tenant excepto super_admin)
    es_super = current_user.role == "super_admin"
    actual = await conn.fetchrow(
        """SELECT id, cliente_id, email_origen, email_respuesta_override
           FROM pqrs_casos
           WHERE id = $1 AND ($2 OR cliente_id = $3)""",
        uuid.UUID(caso_id), es_super, uuid.UUID(current_user.tenant_uuid),
    )
    if not actual:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    anterior = actual["email_respuesta_override"] or actual["email_origen"]

    await conn.execute(
        """UPDATE pqrs_casos SET email_respuesta_override = $1,
                                  updated_at = NOW()
           WHERE id = $2""",
        nuevo_email, uuid.UUID(caso_id),
    )

    # Audit
    ip = request.client.host if request.client else None
    await conn.execute(
        """INSERT INTO audit_log_respuestas
              (caso_id, usuario_id, accion, ip_origen, metadata)
           VALUES ($1, $2, 'DESTINATARIO_EDITADO', $3, $4)""",
        uuid.UUID(caso_id), uuid.UUID(current_user.usuario_id), ip,
        json.dumps({
            "anterior": anterior,
            "nuevo": nuevo_email,
            "email_origen_caso": actual["email_origen"],
            "tipo_cambio": "QUITAR_OVERRIDE" if nuevo_email is None else "SET_OVERRIDE",
        }),
    )

    return {
        "status": "ok",
        "caso_id": caso_id,
        "email_destinatario_efectivo": nuevo_email or actual["email_origen"],
        "fue_override": nuevo_email is not None,
    }


class AplicarPlantillaRequest(BaseModel):
    """Body para POST /casos/{id}/aplicar-plantilla.

    Aplica una plantilla del catálogo del tenant al borrador del caso.
    Renderiza placeholders básicos del cuerpo de la plantilla con datos del
    caso y deja el resultado en `borrador_respuesta`.
    """
    plantilla_id: str


# Placeholders soportados en el cuerpo de las plantillas (rendering simple).
# Cualquier `{clave}` desconocido queda como literal — no inventamos datos.
def _render_placeholders(cuerpo: str, caso_row, hoy_iso: str) -> str:
    if not cuerpo:
        return ""
    mapping = {
        "cedula":      caso_row.get("documento_peticionante") or "",
        "documento":   caso_row.get("documento_peticionante") or "",
        "email":       caso_row.get("email_origen") or "",
        "asunto":      caso_row.get("asunto") or "",
        "fecha":       hoy_iso,
        "radicado":    caso_row.get("numero_radicado") or "",
        "tipo_caso":   caso_row.get("tipo_caso") or "",
    }
    out = cuerpo
    for k, v in mapping.items():
        out = out.replace("{" + k + "}", str(v))
    return out


@router.post("/{caso_id}/aplicar-plantilla")
async def aplicar_plantilla(
    caso_id: str,
    body: AplicarPlantillaRequest,
    request: Request,
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
) -> Dict[str, Any]:
    """Aplicar una plantilla al borrador del caso (sprint FF — bloque 7).

    Permisos: admin / super_admin (analista no — todavía no decidimos si dejarle).
    Reglas:
      - La plantilla debe pertenecer al mismo `cliente_id` que el caso
        (excepto super_admin, que puede aplicar cualquiera).
      - Renderiza placeholders básicos en el cuerpo ({cedula}, {fecha}, etc.).
      - Escribe en `borrador_respuesta` y pone `borrador_estado = 'PENDIENTE_REVISION'`.
      - Audit: action 'PLANTILLA_APLICADA' con metadata
        {plantilla_id, plantilla_problematica, longitud_cuerpo}.
    """
    if current_user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Solo admin / super_admin")

    es_super = current_user.role == "super_admin"

    caso = await conn.fetchrow(
        """SELECT id, cliente_id, email_origen, asunto, tipo_caso,
                  numero_radicado, documento_peticionante
           FROM pqrs_casos
           WHERE id = $1 AND ($2 OR cliente_id = $3)""",
        uuid.UUID(caso_id), es_super, uuid.UUID(current_user.tenant_uuid),
    )
    if not caso:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    plantilla = await conn.fetchrow(
        """SELECT id, cliente_id, problematica, cuerpo, tipo_workflow, is_active
           FROM plantillas_respuesta
           WHERE id = $1::uuid""",
        uuid.UUID(body.plantilla_id),
    )
    if not plantilla:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    if not plantilla["is_active"]:
        raise HTTPException(status_code=400, detail="Plantilla inactiva")
    if not es_super and plantilla["cliente_id"] != caso["cliente_id"]:
        raise HTTPException(status_code=403, detail="Plantilla de otro tenant")

    from datetime import date
    cuerpo_renderizado = _render_placeholders(
        plantilla["cuerpo"], dict(caso), date.today().isoformat()
    )

    await conn.execute(
        """UPDATE pqrs_casos
           SET borrador_respuesta = $1,
               borrador_estado    = 'PENDIENTE_REVISION',
               updated_at         = NOW()
           WHERE id = $2""",
        cuerpo_renderizado, uuid.UUID(caso_id),
    )

    ip = request.client.host if request.client else None
    await conn.execute(
        """INSERT INTO audit_log_respuestas
              (caso_id, usuario_id, accion, ip_origen, metadata)
           VALUES ($1, $2, 'PLANTILLA_APLICADA', $3, $4)""",
        uuid.UUID(caso_id), uuid.UUID(current_user.usuario_id), ip,
        json.dumps({
            "plantilla_id": str(plantilla["id"]),
            "plantilla_problematica": plantilla["problematica"],
            "plantilla_workflow": plantilla["tipo_workflow"],
            "longitud_cuerpo": len(cuerpo_renderizado),
        }),
    )

    return {
        "status": "ok",
        "caso_id": caso_id,
        "plantilla_id": str(plantilla["id"]),
        "plantilla_problematica": plantilla["problematica"],
        "borrador_respuesta": cuerpo_renderizado,
        "borrador_estado": "PENDIENTE_REVISION",
    }


class BorradorUpdateRequest(BaseModel):
    texto: str

@router.put("/{caso_id}/borrador")
async def editar_borrador(
    caso_id: str, body: BorradorUpdateRequest,
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
):
    caso = await conn.fetchrow(
        "SELECT id, cliente_id, tipo_caso, borrador_respuesta FROM pqrs_casos "
        "WHERE id = $1 AND ($2 OR cliente_id = $3)",
        uuid.UUID(caso_id),
        current_user.role == "super_admin",
        uuid.UUID(current_user.tenant_uuid),
    )
    if not caso:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    original_ai = caso["borrador_respuesta"] or ""

    if body.texto == original_ai:
        return {"ok": True, "unchanged": True}

    await conn.execute(
        "UPDATE pqrs_casos SET borrador_respuesta = $1 WHERE id = $2",
        body.texto, caso["id"],
    )
    await conn.execute(
        "INSERT INTO audit_log_respuestas (caso_id, usuario_id, accion, metadata) VALUES ($1,$2,'BORRADOR_EDITADO',$3)",
        caso["id"], uuid.UUID(current_user.usuario_id), json.dumps({"chars": len(body.texto)}),
    )

    if original_ai:
        similarity = _text_similarity(original_ai, body.texto)
        try:
            await conn.execute(
                """INSERT INTO borrador_feedback
                   (caso_id, cliente_id, tipo_caso, usuario_id, original_ai, editado_usuario, similarity_score)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                caso["id"], caso["cliente_id"], caso["tipo_caso"],
                uuid.UUID(current_user.usuario_id),
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
    # SEC-2026-05-21: scope por tenant; 404 si el caso no pertenece (no afecta filas).
    rechazado = await conn.fetchval(
        "UPDATE pqrs_casos SET borrador_estado = 'RECHAZADO' "
        "WHERE id = $1 AND ($2 OR cliente_id = $3) RETURNING id",
        uuid.UUID(caso_id),
        current_user.role == "super_admin",
        uuid.UUID(current_user.tenant_uuid),
    )
    if not rechazado:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
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
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo demasiado grande (máx 25MB)")

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

    # FF-fix 2026-06: el envío debe respetar el proveedor del buzón del tenant.
    # Antes esta query filtraba proveedor='ZOHO' → para tenants OUTLOOK (FlexFintech,
    # cuentas en Microsoft 365) devolvía None y caía SIEMPRE al fallback SMTP de
    # Gmail (democlasificador). Ahora traemos el buzón activo cualquiera sea su
    # proveedor y enrutamos el envío según corresponda (OUTLOOK→Graph, ZOHO→Zoho).
    buzon = await conn.fetchrow(
        """SELECT email_buzon, proveedor, azure_client_id, azure_client_secret,
                  azure_tenant_id, zoho_refresh_token, zoho_account_id
           FROM config_buzones
           WHERE cliente_id=$1 AND is_active=TRUE
           ORDER BY CASE WHEN proveedor='OUTLOOK' THEN 0 ELSE 1 END
           LIMIT 1""",
        uuid.UUID(current_user.tenant_uuid),
    )
    proveedor = (buzon["proveedor"] or "").upper() if buzon else None
    zoho = ZohoServiceV2(
        buzon["azure_client_id"], buzon["azure_client_secret"],
        buzon["zoho_refresh_token"], buzon["zoho_account_id"]
    ) if buzon and proveedor == "ZOHO" else None
    outlook_sender = OutlookSenderV2(
        buzon["azure_client_id"], buzon["azure_client_secret"], buzon["azure_tenant_id"]
    ) if buzon and proveedor == "OUTLOOK" else None

    # Sprint FF bloque 6: SharePoint engine para archivado post-envío.
    # Se construye 1 vez por lote — reutiliza el access token entre cases.
    sp_engine = None
    try:
        sp_row = await conn.fetchrow(
            """SELECT sharepoint_site_id, sharepoint_base_folder,
                      azure_client_id, azure_client_secret, azure_tenant_id
               FROM config_buzones
               WHERE cliente_id = $1 AND sharepoint_site_id IS NOT NULL
               LIMIT 1""",
            uuid.UUID(current_user.tenant_uuid),
        )
        if sp_row and sp_row["sharepoint_site_id"]:
            from app.services.sharepoint_engine import SharePointEngineV2
            sp_engine = SharePointEngineV2(
                sp_row["azure_client_id"], sp_row["azure_client_secret"],
                sp_row["azure_tenant_id"],
                sp_row["sharepoint_site_id"], sp_row["sharepoint_base_folder"],
            )
    except Exception as e:
        logger.warning(f"SP engine init failed (sigue sin archivado): {e}")

    lote_id = uuid.uuid4()
    now     = datetime.now(timezone.utc)
    ip      = request.client.host if request.client else None
    enviados, errores = [], []

    for cid in body.caso_ids:
        try:
            caso = await conn.fetchrow(
                "SELECT id, email_origen, email_respuesta_override, asunto, "
                "cuerpo, borrador_respuesta, documento_peticionante, "
                "tipo_workflow, tipo_caso, problematica_detectada, fecha_recibido "
                "FROM pqrs_casos WHERE id = $1",
                uuid.UUID(cid),
            )
            if not caso or not caso["borrador_respuesta"]:
                errores.append({"caso_id": cid, "motivo": "Sin borrador o no encontrado"}); continue

            # Sprint FF bloque 5: override del destinatario si admin editó.
            email_destino = caso["email_respuesta_override"] or caso["email_origen"]
            fue_override = caso["email_respuesta_override"] is not None

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
            ok = False
            metodo_envio = "ninguno"
            # FF-fix 2026-06: enrutar el envío por el proveedor del buzón del tenant.
            # OUTLOOK (Microsoft 365, ej. FlexFintech) → Graph sendMail desde el
            # propio buzón. ZOHO → API Zoho. Si el camino primario falla, recién
            # ahí cae al fallback SMTP, y AHORA con el remitente correcto.
            if outlook_sender:
                try:
                    # firma-por-tenant 2026-06-25: FF → texto (sin imagen);
                    # Recovery/ARC → imagen institucional inline (CID).
                    from app.services.firma_engine import firma_html_cid, firma_bytes as _firma_tenant_bytes, usa_imagen as _usa_img
                    _buzon_email = buzon["email_buzon"]
                    _firma = _firma_tenant_bytes() if _usa_img(email_buzon=_buzon_email) else None
                    _html = (
                        "<div style='font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.6'>"
                        + _md_to_html(caso["borrador_respuesta"])
                        + firma_html_cid(email_buzon=_buzon_email)
                        + "</div>"
                    )
                    ok = outlook_sender.send_reply(
                        _buzon_email, email_destino, subject, _html,
                        firma_bytes=_firma, adjuntos=adjuntos_data or None,
                    )
                    if ok:
                        metodo_envio = "outlook_graph"
                    else:
                        logger.warning(f"Graph retornó False para caso {cid} — intentando fallback SMTP")
                except Exception as gerr:
                    logger.error(f"Graph excepción caso {cid}: {gerr} — intentando fallback SMTP")
            elif zoho:
                try:
                    ok = zoho.send_reply(email_destino, subject, caso["borrador_respuesta"],
                                         buzon["email_buzon"], adjuntos=adjuntos_data or None)
                    if ok:
                        metodo_envio = "zoho"
                    else:
                        logger.warning(f"Zoho retornó False para caso {cid} — intentando fallback SMTP")
                except Exception as zoho_err:
                    logger.error(f"Zoho excepción caso {cid}: {zoho_err} — intentando fallback SMTP")
            if not ok:
                # Fallback SMTP: pasar el buzón de origen como remitente para no
                # filtrar desde Gmail demo. Requiere SMTP_FALLBACK_USER/PASS con
                # credenciales del buzón (o relay que permita ese From).
                ok = _send_via_smtp_fallback(
                    email_destino, subject, caso["borrador_respuesta"],
                    from_address=buzon["email_buzon"] if buzon else None,
                )
                if ok:
                    metodo_envio = "smtp_fallback"
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
                    json.dumps({
                        "email_destino": email_destino,
                        "email_origen_caso": caso["email_origen"],
                        "fue_override": fue_override,
                        "asunto": subject,
                        "lote_size": len(body.caso_ids),
                        "metodo_envio": metodo_envio,
                    }),
                )
                enviados.append(cid)

                # ─── Sprint FF cierre-de-loop "el modelo aprende" 2026-05-27 ─
                # Re-ingestion al KB: indexar la respuesta enviada como
                # `caso_enviado` para que futuros casos similares la retrieven.
                # Best-effort (si Voyage falla, log + sigue).
                try:
                    from app.services.rag_engine import aprender_de_envio
                    await aprender_de_envio(
                        conn, caso["id"], current_user.tenant_uuid,
                        caso["asunto"], caso["borrador_respuesta"],
                        tipo_caso=caso.get("tipo_caso"),
                        problematica=caso.get("problematica_detectada"),
                    )
                except Exception as kb_err:
                    logger.warning(f"aprender_de_envio falló caso {cid}: {kb_err}")

                # ─── Sprint FF bloque 6: archivado SharePoint ──────────
                # Solo para tipo_workflow='PQRS' (decisión D2). Best-effort
                # — si falla, log warn y sigue sin romper el envío.
                if (sp_engine and caso["tipo_workflow"] == "PQRS"
                        and caso["documento_peticionante"]):
                    try:
                        # Construir HTML del mail original
                        mail_html = _render_mail_html(
                            asunto=caso["asunto"],
                            cuerpo=caso["cuerpo"] or "",
                            sender=caso["email_origen"],
                            fecha=caso["fecha_recibido"],
                        ).encode("utf-8")
                        # Construir HTML de la respuesta
                        respuesta_html = _render_respuesta_html(
                            subject=subject,
                            destinatario=email_destino,
                            cuerpo=caso["borrador_respuesta"],
                            fecha=now,
                        ).encode("utf-8")
                        # bug_020B fix: para el ARCHIVO histórico SP queremos
                        # los adjuntos ORIGINALES del mail entrante (es_reply=FALSE),
                        # NO los uploads del admin para la respuesta (es_reply=TRUE
                        # que ya están en adj_rows arriba para el envío Zoho).
                        adj_orig_rows = await conn.fetch(
                            "SELECT storage_path, nombre_archivo, content_type "
                            "FROM pqrs_adjuntos WHERE caso_id=$1 AND es_reply=FALSE",
                            caso["id"],
                        )
                        adj_para_sp = []
                        for ar in adj_orig_rows:
                            content_bytes = download_file(ar["storage_path"])
                            if content_bytes:
                                adj_para_sp.append({
                                    "nombre_archivo": ar["nombre_archivo"],
                                    "content_bytes": content_bytes,
                                    "content_type": ar["content_type"]
                                                    or "application/octet-stream",
                                })

                        sp_path = await sp_engine.archivar_caso(
                            cedula=caso["documento_peticionante"],
                            fecha=now,
                            mail_original_html=mail_html,
                            respuesta_html=respuesta_html,
                            adjuntos=adj_para_sp,
                        )
                        if sp_path:
                            await conn.execute(
                                """UPDATE pqrs_casos
                                   SET metadata_especifica =
                                       COALESCE(metadata_especifica, '{}'::jsonb)
                                       || jsonb_build_object('sp_archivo', $1::text)
                                   WHERE id = $2""",
                                sp_path, caso["id"],
                            )
                    except Exception as sp_err:
                        logger.warning(f"SP archivar_caso falló caso {cid}: {sp_err}")
            else:
                errores.append({"caso_id": cid, "motivo": "Error Zoho al enviar"})
        except Exception as e:
            logger.error(f"Error lote caso {cid}: {e}")
            errores.append({"caso_id": cid, "motivo": str(e)})

    return {"enviados": len(enviados), "lote_id": str(lote_id), "errores": errores}


# ============================================================
# Estrategia D — Vinculación manual TUTELA ↔ PQR previo
# ============================================================

class VincularPQRBody(BaseModel):
    pqr_id: str


@router.get("/{tutela_id}/pqrs-vinculables")
async def listar_pqrs_vinculables(
    tutela_id: str,
    q: Optional[str] = Query(None, max_length=100),
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
) -> Dict[str, Any]:
    """Lista PQRs candidatos a vincular a una tutela (mismo cliente, no-TUTELA, no ya vinculados).
    Filtra por asunto/email/radicado si q presente. Limit 20."""
    tutela = await conn.fetchrow(
        """SELECT cliente_id, email_origen, pqr_origenes, tipo_caso
           FROM pqrs_casos WHERE id = $1 AND ($2 OR cliente_id = $3)""",
        uuid.UUID(tutela_id),
        current_user.role == "super_admin",
        uuid.UUID(current_user.tenant_uuid),
    )
    if not tutela:
        raise HTTPException(status_code=404, detail="Tutela no encontrada")
    if tutela["tipo_caso"] != "TUTELA":
        raise HTTPException(status_code=400, detail="Solo se pueden vincular PQRs a casos tipo TUTELA")

    yas = tutela["pqr_origenes"] or []
    params: List[Any] = [tutela["cliente_id"], yas]
    where_extra = ""
    if q:
        params.append(f"%{q}%")
        where_extra = (
            f" AND (asunto ILIKE ${len(params)} OR email_origen ILIKE ${len(params)} "
            f"OR numero_radicado ILIKE ${len(params)})"
        )
    rows = await conn.fetch(
        f"""SELECT id, numero_radicado, asunto, tipo_caso, estado, email_origen, fecha_recibido
            FROM pqrs_casos
            WHERE cliente_id = $1 AND tipo_caso != 'TUTELA' AND id != ALL($2::uuid[])
            {where_extra}
            ORDER BY fecha_recibido DESC LIMIT 20""",
        *params,
    )
    return {
        "items": [
            {
                "id": str(r["id"]),
                "numero_radicado": r["numero_radicado"],
                "asunto": r["asunto"],
                "tipo_caso": r["tipo_caso"],
                "estado": r["estado"],
                "email_origen": r["email_origen"],
                "fecha_recibido": r["fecha_recibido"].isoformat() if r["fecha_recibido"] else None,
            }
            for r in rows
        ]
    }


@router.post("/{tutela_id}/vincular-pqr")
async def vincular_pqr(
    tutela_id: str,
    body: VincularPQRBody,
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
) -> Dict[str, Any]:
    """Agrega un PQR al array pqr_origenes de la tutela (estrategia D — manual)."""
    pqr_uuid = uuid.UUID(body.pqr_id)
    tutela_uuid = uuid.UUID(tutela_id)
    # Validar ambos del mismo cliente y tipos correctos (RLS scoping via cliente_id)
    pair = await conn.fetchrow(
        """SELECT
             (SELECT cliente_id FROM pqrs_casos WHERE id = $1) AS t_cli,
             (SELECT tipo_caso  FROM pqrs_casos WHERE id = $1) AS t_tipo,
             (SELECT cliente_id FROM pqrs_casos WHERE id = $2) AS p_cli,
             (SELECT tipo_caso  FROM pqrs_casos WHERE id = $2) AS p_tipo""",
        tutela_uuid, pqr_uuid,
    )
    if not pair or not pair["t_cli"]:
        raise HTTPException(status_code=404, detail="Tutela no encontrada")
    if pair["t_tipo"] != "TUTELA":
        raise HTTPException(status_code=400, detail="El caso destino no es una TUTELA")
    if not pair["p_cli"]:
        raise HTTPException(status_code=404, detail="PQR no encontrado")
    if pair["p_tipo"] == "TUTELA":
        raise HTTPException(status_code=400, detail="No se puede vincular otra TUTELA como origen")
    if pair["t_cli"] != pair["p_cli"]:
        raise HTTPException(status_code=400, detail="Tutela y PQR deben pertenecer al mismo cliente")
    is_super = current_user.role == "super_admin"
    if not is_super and pair["t_cli"] != uuid.UUID(current_user.tenant_uuid):
        raise HTTPException(status_code=404, detail="Tutela no encontrada")

    # Append idempotente (array_append no duplica? PG sí duplica; usamos NOT contains)
    await conn.execute(
        """UPDATE pqrs_casos
           SET pqr_origenes = array_append(pqr_origenes, $1)
           WHERE id = $2 AND NOT ($1 = ANY(pqr_origenes))""",
        pqr_uuid, tutela_uuid,
    )
    return {"ok": True, "pqr_id": str(pqr_uuid), "tutela_id": str(tutela_uuid)}


@router.delete("/{tutela_id}/vincular-pqr/{pqr_id}")
async def desvincular_pqr(
    tutela_id: str,
    pqr_id: str,
    current_user: UserInToken = Depends(get_current_user),
    conn=Depends(get_db_connection),
) -> Dict[str, Any]:
    """Quita un PQR del array pqr_origenes de la tutela (estrategia D — manual)."""
    is_super = current_user.role == "super_admin"
    updated = await conn.fetchval(
        """UPDATE pqrs_casos
           SET pqr_origenes = array_remove(pqr_origenes, $1)
           WHERE id = $2 AND ($3 OR cliente_id = $4)
           RETURNING id""",
        uuid.UUID(pqr_id), uuid.UUID(tutela_id),
        is_super, uuid.UUID(current_user.tenant_uuid),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Tutela no encontrada")
    return {"ok": True}
