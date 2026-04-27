import asyncio
import asyncpg
import redis.asyncio as redis
import json
import imaplib
import smtplib
import email as email_lib
import os
import re
import uuid
import logging
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parsedate_to_datetime, parseaddr
from email.header import decode_header, make_header

from app.services.ai_engine import clasificar_hibrido
from app.services.plantilla_engine import generar_borrador_para_caso
from app.services.clasificador import parece_pqrs
from app.services.storage_engine import upload_file as upload_to_minio, client as minio_client, BUCKET_NAME as MINIO_BUCKET

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("DEMO_WORKER")

TIPOS_VALIDOS = {"TUTELA", "PETICION", "QUEJA", "RECLAMO", "SOLICITUD"}

DATABASE_URL = os.environ.get("WORKER_DB_URL", "postgresql://aequitas_worker:changeme_worker@postgres_v2:5432/pqrs_v2")
REDIS_URL     = os.environ.get("REDIS_URL",    "redis://redis_v2:6379")
GMAIL_USER    = os.environ.get("DEMO_GMAIL_USER",     "democlasificador@gmail.com")
GMAIL_PASS    = os.environ.get("DEMO_GMAIL_PASSWORD", "")
RESET_MINUTES = int(os.environ.get("DEMO_RESET_MINUTES", "30"))

# UUID fijo para el tenant de demo (debe existir en clientes_tenant)
DEMO_TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DEMO_ABOGADO_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")

MAX_ATTACHMENT_MB = int(os.environ.get("MAX_ATTACHMENT_MB", "10"))
MAX_ATTACHMENTS_PER_EMAIL = 5
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg", "image/png", "image/gif",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/msword", "application/vnd.ms-excel",
    "application/octet-stream",
}

TIPO_INFO = {
    "TUTELA":      ("Acción de Tutela",   "CRÍTICA", "48 horas"),
    "PETICION":    ("Derecho de Petición","MEDIA",   "15 días hábiles"),
    "QUEJA":       ("Queja",              "ALTA",    "15 días hábiles"),
    "RECLAMO":     ("Reclamo",            "ALTA",    "15 días hábiles"),
    "SOLICITUD":   ("Solicitud",          "MEDIA",   "10 días hábiles"),
    "FELICITACION":("Felicitación",       "BAJA",    "30 días hábiles"),
}


# ── Gmail IMAP ────────────────────────────────────────────────────────────────

def fetch_unread_gmail():
    emails = []
    if not GMAIL_PASS:
        logger.warning("DEMO_GMAIL_PASSWORD no configurado — saltando lectura")
        return emails
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(GMAIL_USER, GMAIL_PASS)
        mail.select("INBOX")
        _, ids = mail.search(None, "UNSEEN")

        for imap_id in ids[0].split():
            _, data = mail.fetch(imap_id, "(RFC822)")
            raw = email_lib.message_from_bytes(data[0][1])

            body = ""
            adjuntos = []
            if raw.is_multipart():
                for part in raw.walk():
                    ct = part.get_content_type()
                    disp = str(part.get("Content-Disposition", ""))

                    # Extraer body de texto
                    if ct == "text/plain" and "attachment" not in disp and not body:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="ignore")
                        continue

                    # Extraer adjuntos
                    filename = part.get_filename()
                    if not filename:
                        continue
                    if ct not in ALLOWED_MIME_TYPES:
                        logger.info(f"📎 Adjunto ignorado (MIME no permitido): {filename} [{ct}]")
                        continue
                    if len(adjuntos) >= MAX_ATTACHMENTS_PER_EMAIL:
                        logger.warning(f"📎 Límite de adjuntos alcanzado ({MAX_ATTACHMENTS_PER_EMAIL}), ignorando: {filename}")
                        break
                    content = part.get_payload(decode=True)
                    if not content:
                        continue
                    size = len(content)
                    if size > MAX_ATTACHMENT_MB * 1024 * 1024:
                        logger.warning(f"📎 Adjunto excede {MAX_ATTACHMENT_MB}MB: {filename} ({size/(1024*1024):.1f}MB)")
                        continue
                    adjuntos.append({
                        "filename": filename,
                        "mime_type": ct,
                        "size_bytes": size,
                        "content": content,
                    })
            else:
                payload = raw.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="ignore")

            _, sender = parseaddr(raw.get("From", ""))
            try:
                date = parsedate_to_datetime(raw.get("Date", ""))
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
            except Exception:
                date = datetime.now(timezone.utc)

            if adjuntos:
                logger.info(f"📎 {len(adjuntos)} adjunto(s) extraídos de email: {[a['filename'] for a in adjuntos]}")

            emails.append({
                "message_id": raw.get("Message-ID") or str(uuid.uuid4()),
                "subject":    str(make_header(decode_header(raw.get("Subject", "(sin asunto)")))),
                "sender":     sender,
                "body":       body,
                "date":       date,
                "adjuntos":   adjuntos,
            })
            mail.store(imap_id, "+FLAGS", "\\Seen")

        mail.logout()
        logger.info(f"📬 Gmail: {len(emails)} email(s) no leídos")
    except Exception as e:
        logger.error(f"Gmail IMAP error: {e}")
    return emails


# ── Acuse de recibo vía Gmail SMTP ────────────────────────────────────────────

PLAZOS_DEMO = {
    "TUTELA":    ("Acción de Tutela",    "#DC2626", "48 horas"),
    "PETICION":  ("Derecho de Petición", "#2563EB", "15 días hábiles"),
    "QUEJA":     ("Queja",              "#D97706", "8 días hábiles"),
    "RECLAMO":   ("Reclamo",            "#D97706", "8 días hábiles"),
    "SOLICITUD": ("Solicitud",          "#059669", "15 días hábiles"),
}

MENSAJES_TIPO = {
    "TUTELA":    "Su caso fue escalado al área jurídica con carácter urgente.",
    "PETICION":  "Su petición fue radicada y asignada al equipo responsable.",
    "QUEJA":     "Lamentamos su inconformidad. Nuestro equipo dará respuesta oportuna.",
    "RECLAMO":   "Su reclamo fue recibido y será atendido dentro del plazo legal.",
    "SOLICITUD": "Su solicitud fue radicada y será procesada a la brevedad.",
}

def send_acuse_demo(to_email: str, numero_radicado: str, tipo: str, nombre_cliente: str | None):
    if not GMAIL_PASS:
        logger.warning("DEMO_GMAIL_PASSWORD no configurado — acuse no enviado")
        return

    label, color, plazo = PLAZOS_DEMO.get(tipo, ("Caso", "#6B7280", "15 días hábiles"))
    mensaje_tipo = MENSAJES_TIPO.get(tipo, "Su caso fue recibido correctamente.")
    saludo = f"Estimado/a {nombre_cliente}," if nombre_cliente else "Estimado/a usuario/a,"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:32px 0">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08)">
        <tr>
          <td style="background:#0a0a0a;padding:24px 32px;">
            <span style="color:#9D50FF;font-size:22px;font-weight:bold;letter-spacing:1px;">FlexPQR</span>
            <span style="color:#555;font-size:13px;margin-left:8px;">Demo FlexPQR</span>
          </td>
        </tr>
        <tr>
          <td style="padding:24px 32px 0">
            <span style="background:{color};color:#fff;padding:4px 14px;border-radius:20px;font-size:12px;font-weight:bold;">{label}</span>
          </td>
        </tr>
        <tr>
          <td style="padding:20px 32px 8px">
            <p style="color:#111;font-size:16px;margin:0 0 8px">{saludo}</p>
            <p style="color:#374151;font-size:15px;margin:0 0 20px">Hemos recibido correctamente su comunicación. {mensaje_tipo}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:0 32px 20px">
            <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px">
              <tr>
                <td style="padding:16px 20px">
                  <p style="margin:0 0 10px;color:#6B7280;font-size:12px;text-transform:uppercase;">Número de radicado</p>
                  <p style="margin:0 0 16px;color:#111;font-size:22px;font-weight:bold;letter-spacing:1px;">{numero_radicado}</p>
                  <table>
                    <tr>
                      <td style="padding-right:32px">
                        <p style="margin:0;color:#6B7280;font-size:12px">Tipo de caso</p>
                        <p style="margin:4px 0 0;color:#111;font-size:14px;font-weight:600">{label}</p>
                      </td>
                      <td>
                        <p style="margin:0;color:#6B7280;font-size:12px">Fecha límite de respuesta</p>
                        <p style="margin:4px 0 0;color:{color};font-size:14px;font-weight:600">{plazo}</p>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding:0 32px 24px">
            <p style="color:#374151;font-size:14px;margin:0">
              Conserve el número de radicado para hacer seguimiento a su caso.
              Recibirá una respuesta formal antes del plazo indicado.
            </p>
          </td>
        </tr>
        <tr>
          <td style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:16px 32px">
            <p style="margin:0;color:#9CA3AF;font-size:12px">
              Este mensaje fue generado automáticamente por FlexPQR. Por favor no responda a este correo.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    try:
        msg = MIMEMultipart("alternative")
        msg["From"]    = f"FlexPQR <{GMAIL_USER}>"
        msg["To"]      = to_email
        msg["Subject"] = f"Radicado {numero_radicado} — Confirmación de recepción"
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())

        logger.info(f"Acuse enviado → {to_email} [{label}] {numero_radicado}")
    except Exception as e:
        logger.error(f"SMTP error al enviar acuse: {e}")


# ── Auto-envío de respuesta IA (EXCLUSIVO TENANT DEMO) ───────────────────────
#
# ADVERTENCIA: Esta función auto-envía la respuesta IA generada sin pasar por
# aprobación humana. Es aceptable ÚNICAMENTE para el tenant demo (showcase
# público en bandeja Gmail controlada). En Abogados Recovery y cualquier otro
# tenant productivo el envío sigue siendo human-in-the-loop vía
# POST /api/v2/casos/aprobar-lote. NO replicar este patrón a master_worker_outlook
# ni a ningún otro worker sin aprobación regulatoria explícita.

def _md_to_html_demo(text: str) -> str:
    """Conversión markdown→HTML mínima para respuestas IA del demo."""
    import re
    text = re.sub(r'^### (.+)$', r'<h4 style="margin:12px 0 4px">\1</h4>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$',  r'<h3 style="margin:14px 0 6px">\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$',   r'<h2 style="margin:16px 0 8px">\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    text = re.sub(r'\*([^*\n]+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_([^_\n]+?)_', r'<em>\1</em>', text)
    return text.replace("\n", "<br>")


def send_respuesta_ia_demo(to_email: str, asunto_original: str, body_md: str, numero_radicado: str) -> bool:
    """
    Envía la respuesta IA (borrador_respuesta) al remitente vía Gmail SMTP.
    Retorna True si el envío fue exitoso, False en otro caso.
    """
    if not GMAIL_PASS:
        logger.warning("[DEMO RESPUESTA IA] DEMO_GMAIL_PASSWORD no configurado — respuesta IA no enviada")
        return False

    body_html = _md_to_html_demo(body_md.strip())
    subject_clean = (asunto_original or "Su PQRS").strip()
    if subject_clean.lower().startswith("re:"):
        reply_subject = f"{subject_clean} — Radicado {numero_radicado}"
    else:
        reply_subject = f"Re: {subject_clean} — Radicado {numero_radicado}"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:32px 0">
    <tr><td align="center">
      <table width="640" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08)">
        <tr>
          <td style="background:#0a0a0a;padding:24px 32px;">
            <span style="color:#9D50FF;font-size:22px;font-weight:bold;letter-spacing:1px;">FlexPQR</span>
            <span style="color:#888;font-size:13px;margin-left:8px;">Respuesta oficial</span>
          </td>
        </tr>
        <tr>
          <td style="padding:24px 32px 8px">
            <p style="margin:0 0 6px;color:#6B7280;font-size:12px;text-transform:uppercase;letter-spacing:0.5px;">Radicado</p>
            <p style="margin:0;color:#111;font-size:18px;font-weight:bold;letter-spacing:1px;">{numero_radicado}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 32px 24px;color:#374151;font-size:15px;line-height:1.6">
            {body_html}
          </td>
        </tr>
        <tr>
          <td style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:16px 32px">
            <p style="margin:0;color:#9CA3AF;font-size:12px">
              Este mensaje fue generado automáticamente por FlexPQR (entorno demo).
              Conserve el número de radicado para cualquier seguimiento posterior.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    try:
        msg = MIMEMultipart("alternative")
        msg["From"]    = f"FlexPQR <{GMAIL_USER}>"
        msg["To"]      = to_email
        msg["Subject"] = reply_subject
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())

        logger.info(f"[DEMO RESPUESTA IA] Enviada → {to_email} | {numero_radicado}")
        return True
    except Exception as e:
        logger.error(f"[DEMO RESPUESTA IA] SMTP error: {e}")
        return False


# ── Guardado de adjuntos ──────────────────────────────────────────────────────

def _sanitize_filename(name: str) -> str:
    """Elimina caracteres problemáticos del nombre de archivo."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    return name[:200]


async def save_adjuntos(conn, caso_id: uuid.UUID, adjuntos: list[dict]):
    """Sube adjuntos a MinIO y los registra en pqrs_adjuntos."""
    for adj in adjuntos:
        try:
            safe_name = _sanitize_filename(adj["filename"])
            unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
            path = await upload_to_minio(adj["content"], unique_name, folder=f"casos/{caso_id}")
            if not path:
                logger.warning(f"📎 MinIO upload falló para {adj['filename']} — caso {caso_id}")
                continue
            await conn.execute(
                """INSERT INTO pqrs_adjuntos
                       (caso_id, cliente_id, nombre_archivo, storage_path, content_type, tamano_bytes)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                caso_id, DEMO_TENANT_ID, adj["filename"], path, adj["mime_type"], adj["size_bytes"],
            )
            logger.info(f"📎 Adjunto guardado: {adj['filename']} ({adj['size_bytes']/1024:.1f}KB) → {path}")
        except Exception as e:
            logger.warning(f"📎 Error guardando adjunto {adj['filename']}: {e}")
            continue


# ── Worker principal ──────────────────────────────────────────────────────────

async def demo_worker():
    logger.info(f"🎯 [DEMO WORKER] Iniciando — bandeja: {GMAIL_USER} | reset: {RESET_MINUTES} min")
    r    = redis.from_url(REDIS_URL, decode_responses=True)
    conn = await asyncpg.connect(DATABASE_URL)

    while True:
        try:
            emails = fetch_unread_gmail()

            for em in emails:
                if not parece_pqrs(em["subject"], em["body"], em["sender"]):
                    logger.info(f"Ignorado (no es PQRS): {em['subject'][:60]}")
                    continue

                # Deduplicación por Message-ID (24h TTL)
                dedup_key = f"demo:msg:{em['message_id']}"
                if await r.exists(dedup_key):
                    continue
                await r.setex(dedup_key, 86400, "1")

                # Clasificación híbrida (keywords + Claude Haiku)
                resultado = await clasificar_hibrido(em["subject"], em["body"], em["sender"])

                if resultado.tipo.value not in TIPOS_VALIDOS:
                    logger.info(f"Descartado [{resultado.tipo.value}]: {em['subject'][:60]}")
                    continue

                fecha_venc = em["date"] + timedelta(days=resultado.plazo_dias)

                db_id = await conn.fetchval(
                    """INSERT INTO pqrs_casos
                           (cliente_id, email_origen, asunto, cuerpo, estado, nivel_prioridad,
                            fecha_recibido, tipo_caso, fecha_vencimiento, external_msg_id)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                       ON CONFLICT (cliente_id, external_msg_id)
                           WHERE external_msg_id IS NOT NULL DO NOTHING
                       RETURNING id""",
                    DEMO_TENANT_ID,
                    em["sender"],
                    em["subject"],
                    em["body"][:8000],
                    "ABIERTO",
                    resultado.prioridad.value,
                    em["date"],
                    resultado.tipo.value,
                    fecha_venc,
                    em["message_id"],
                )

                if db_id:
                    # Guardar adjuntos antes de continuar con acuse/respuesta
                    if em.get("adjuntos"):
                        await save_adjuntos(conn, db_id, em["adjuntos"])

                    radicado = f"PQRS-{em['date'].year}-{str(db_id)[:8].upper()}"
                    await conn.execute(
                        """UPDATE pqrs_casos
                           SET acuse_enviado=TRUE, numero_radicado=$1,
                               asignado_a=$3, fecha_asignacion=NOW()
                           WHERE id=$2""",
                        radicado, db_id, DEMO_ABOGADO_ID,
                    )

                    notif = {
                        "id": str(db_id),
                        "subject": em["subject"],
                        "tenant_id": str(DEMO_TENANT_ID),
                        "email": em["sender"],
                        "tipo": resultado.tipo.value,
                        "prioridad": resultado.prioridad.value,
                        "estado": "ABIERTO",
                        "vencimiento": fecha_venc.isoformat(),
                        "cliente_nombre": "Demo FlexPQR",
                    }
                    await r.publish("pqrs_stream_v2", json.dumps(notif))
                    logger.info(f"Caso demo creado: {db_id} | {resultado.tipo.value} | {radicado}")

                    send_acuse_demo(
                        to_email=em["sender"],
                        numero_radicado=radicado,
                        tipo=resultado.tipo.value,
                        nombre_cliente=resultado.nombre_cliente,
                    )

                    await generar_borrador_para_caso(
                        conn, str(DEMO_TENANT_ID), str(db_id),
                        em["subject"], em["body"][:1000],
                        nombre_cliente=resultado.nombre_cliente,
                        cedula=resultado.cedula,
                        tipo_caso=resultado.tipo.value,
                        radicado=radicado,
                        email_origen=em["sender"],
                    )

                    # ── Auto-envío respuesta IA (SOLO tenant demo) ──
                    borrador_row = await conn.fetchrow(
                        "SELECT borrador_respuesta, borrador_estado FROM pqrs_casos WHERE id=$1",
                        db_id,
                    )
                    borrador_text = (borrador_row["borrador_respuesta"] or "").strip() if borrador_row else ""
                    if borrador_text:
                        enviado_ok = send_respuesta_ia_demo(
                            to_email=em["sender"],
                            asunto_original=em["subject"],
                            body_md=borrador_text,
                            numero_radicado=radicado,
                        )
                        if enviado_ok:
                            await conn.execute(
                                """UPDATE pqrs_casos
                                   SET borrador_estado='ENVIADO',
                                       estado='CERRADO',
                                       enviado_at=NOW(),
                                       aprobado_at=NOW()
                                   WHERE id=$1""",
                                db_id,
                            )
                            await conn.execute(
                                """INSERT INTO audit_log_respuestas (caso_id, accion, metadata)
                                   VALUES ($1, 'ENVIADO_AUTO_DEMO', $2)""",
                                db_id,
                                json.dumps({
                                    "email_destino": em["sender"],
                                    "asunto": em["subject"],
                                    "metodo_envio": "gmail_smtp",
                                    "auto_aprobado_por": "demo_worker",
                                    "nota": "Auto-envío exclusivo del tenant demo — sin aprobación humana",
                                }),
                            )
                            cambio = {
                                "id": str(db_id),
                                "tenant_id": str(DEMO_TENANT_ID),
                                "estado": "CERRADO",
                                "borrador_estado": "ENVIADO",
                                "event": "caso_estado_cambiado",
                            }
                            await r.publish("pqrs_stream_v2", json.dumps(cambio))
                            logger.info(f"[DEMO RESPUESTA IA] Caso {db_id} auto-cerrado (ENVIADO)")
                        else:
                            logger.warning(f"[DEMO RESPUESTA IA] Envío fallido — caso {db_id} queda en BORRADOR")
                    else:
                        logger.warning(f"[DEMO RESPUESTA IA] Borrador vacío para caso {db_id} — no se envía")

            # ── Reset: eliminar casos demo más viejos que RESET_MINUTES ──────
            old_ids = await conn.fetch(
                """SELECT id FROM pqrs_casos
                   WHERE cliente_id = $1
                     AND external_msg_id IS NOT NULL
                     AND created_at < NOW() - make_interval(mins => $2)""",
                DEMO_TENANT_ID,
                RESET_MINUTES,
            )
            if old_ids:
                ids = [r["id"] for r in old_ids]
                # Limpiar archivos de MinIO antes de borrar registros
                adj_paths = await conn.fetch(
                    "SELECT storage_path FROM pqrs_adjuntos WHERE caso_id = ANY($1::uuid[])", ids,
                )
                for row in adj_paths:
                    try:
                        minio_client.remove_object(MINIO_BUCKET, row["storage_path"])
                    except Exception:
                        pass
                await conn.execute("DELETE FROM audit_log_respuestas WHERE caso_id = ANY($1::uuid[])", ids)
                await conn.execute("DELETE FROM pqrs_comentarios WHERE caso_id = ANY($1::uuid[])", ids)
                await conn.execute("DELETE FROM pqrs_adjuntos WHERE caso_id = ANY($1::uuid[])", ids)
                await conn.execute("DELETE FROM pqrs_casos WHERE id = ANY($1::uuid[])", ids)
                logger.info(f"🗑️  Demo reset: {len(ids)} caso(s) eliminado(s) (>{RESET_MINUTES} min)")

        except Exception as e:
            logger.error(f"💥 Demo Worker error: {e}")

        await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(demo_worker())
