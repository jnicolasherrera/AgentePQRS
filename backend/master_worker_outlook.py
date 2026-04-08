import asyncio
import json
import os
import msal
import requests
import asyncpg
import redis.asyncio as redis
import pandas as pd
from datetime import datetime, timedelta
import base64
import logging
import re
import uuid as _uuid

# Configuración Base
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MASTER_WORKER")

# Infraestructura V2 — worker usa aequitas_worker (BYPASSRLS nativo)
DATABASE_URL = os.environ.get("WORKER_DB_URL", "postgresql://aequitas_worker:changeme_worker@postgres_v2:5432/pqrs_v2")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis_v2:6379")

# Credenciales Maestras Outlook para Flex
AZURE_CLIENT_ID = "b2f0910b-d300-4a55-963a-59aeb5acabf6"
AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET")
AZURE_TENANT_ID = "f765bba0-7d35-4248-9711-5770de77ab2b"

from app.services.ai_engine import clasificar_hibrido
from app.services.storage_engine import upload_file as upload_to_minio
from app.services.zoho_engine import ZohoServiceV2
from app.services.sharepoint_engine import SharePointEngineV2
from app.services.plantilla_engine import generar_borrador_para_caso
from app.services.clasificador import parece_pqrs

TENANT_ABOGADOS_RECOVERY = "effca814-b0b5-4329-96be-186c0333ad4b"

_RE_PREFIX = re.compile(r'^(?:(?:[a-z]{1,4}\s*-\s*)+)?(?:re|fw|fwd|rv|rta|r)\s*:\s*', re.IGNORECASE)
_RE_RADICADO = re.compile(r'PQRS-\d{4}-[A-F0-9]{6,8}', re.IGNORECASE)

def _strip_prefixes(subject: str) -> str:
    """Quita recursivamente Re:/Fw:/CO-/etc. hasta llegar al asunto base."""
    prev = None
    while prev != subject:
        prev = subject
        subject = _RE_PREFIX.sub("", subject).strip()
    return subject

async def _registrar_seguimiento(conn, em: dict, c_id) -> bool:
    """Detecta si el email es respuesta a un caso existente.
    Si lo es, inserta un comentario y retorna True para saltar la creación.
    """
    subject = em.get("subject", "")
    body = em.get("body", "") or ""

    # Solo emails con prefijo RE/FW (incluyendo variantes como 'CO - Re:')
    if not _RE_PREFIX.match(subject):
        return False

    caso = None

    # 1. Buscar radicado explícito en asunto o cuerpo
    match = _RE_RADICADO.search(subject) or _RE_RADICADO.search(body[:1000])
    if match:
        radicado = match.group(0).upper()
        caso = await conn.fetchrow(
            "SELECT id, estado FROM pqrs_casos WHERE numero_radicado = $1 AND cliente_id = $2",
            radicado, c_id,
        )

    # 2. Fallback: buscar por asunto base + mismo remitente (últimos 90 días)
    if not caso:
        base = _strip_prefixes(subject)
        if len(base) >= 8:
            caso = await conn.fetchrow(
                """SELECT id, estado FROM pqrs_casos
                   WHERE cliente_id = $1 AND email_origen = $2
                     AND asunto ILIKE $3
                     AND fecha_recibido > NOW() - INTERVAL '90 days'
                   ORDER BY fecha_recibido DESC LIMIT 1""",
                c_id, em["sender"], f"%{base}%",
            )

    if not caso:
        return False

    caso_id = caso["id"]
    comentario = f"[Seguimiento ciudadano]\nDe: {em['sender']}\nAsunto: {subject}\n\n{body[:2000]}"
    await conn.execute(
        """INSERT INTO pqrs_comentarios (id, caso_id, cliente_id, comentario, tipo_evento, created_at)
           VALUES ($1, $2, $3, $4, 'SEGUIMIENTO_CIUDADANO', NOW())""",
        _uuid.uuid4(), caso_id, c_id, comentario,
    )
    if caso["estado"] in ("CERRADO", "CONTESTADO"):
        await conn.execute(
            "UPDATE pqrs_casos SET estado='EN_PROCESO', updated_at=NOW() WHERE id=$1",
            caso_id,
        )
    logger.info(f"🔁 Seguimiento Re: vinculado (de {em['sender']}): {subject[:60]}")
    return True

class MultiTenantOutlookListener:
    def __init__(self, azure_conf=None):
        self.conf = azure_conf or {
            "client_id": AZURE_CLIENT_ID,
            "secret": AZURE_CLIENT_SECRET,
            "tenant": AZURE_TENANT_ID
        }
        self.access_token = None
        self.token_expiry = None

    def _get_token(self):
        if self.access_token and self.token_expiry and datetime.utcnow() < self.token_expiry:
            return self.access_token
        authority = f"https://login.microsoftonline.com/{self.conf['tenant']}"
        app = msal.ConfidentialClientApplication(self.conf['client_id'], authority=authority, client_credential=self.conf['secret'])
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in result: raise Exception(f"Auth Graph Fail")
        self.access_token = result["access_token"]
        self.token_expiry = datetime.utcnow() + timedelta(minutes=50)
        return self.access_token

    def fetch_emails(self, email_buzon, folder_id):
        headers = {"Authorization": f"Bearer {self._get_token()}"}
        url = f"https://graph.microsoft.com/v1.0/users/{email_buzon}/mailFolders/{folder_id}/messages?$top=5&$filter=isRead eq false"
        resp = requests.get(url, headers=headers)
        return resp.json().get("value", []) if resp.status_code < 400 else []

    def get_attachments_meta(self, email_buzon, msg_id):
        headers = {"Authorization": f"Bearer {self._get_token()}"}
        url = f"https://graph.microsoft.com/v1.0/users/{email_buzon}/messages/{msg_id}/attachments"
        resp = requests.get(url, headers=headers)
        return resp.json().get("value", []) if resp.status_code < 400 else []

    def download_attachment(self, email_buzon, msg_id, att_id):
        headers = {"Authorization": f"Bearer {self._get_token()}"}
        url = f"https://graph.microsoft.com/v1.0/users/{email_buzon}/messages/{msg_id}/attachments/{att_id}"
        resp = requests.get(url, headers=headers)
        return base64.b64decode(resp.json()["contentBytes"]) if resp.status_code == 200 else None

    def mark_as_read(self, email_buzon, msg_id):
        headers = {"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json"}
        requests.patch(f"https://graph.microsoft.com/v1.0/users/{email_buzon}/messages/{msg_id}", headers=headers, json={"isRead": True})

async def master_worker():
    logger.info("🚀 [MASTER WORKER V2.1] Híbrido: Outlook/Zoho + SharePoint Storage...")
    r = redis.from_url(REDIS_URL, decode_responses=True)
    conn = await asyncpg.connect(DATABASE_URL)
    outlook = MultiTenantOutlookListener()

    while True:
        try:
            buzones = await conn.fetch("""
                SELECT b.*, c.nombre AS cliente_nombre
                FROM config_buzones b
                JOIN clientes_tenant c ON b.cliente_id = c.id
                WHERE b.is_active = TRUE
            """)

            for b in buzones:
              try:
                c_id, email, prov = b['cliente_id'], b['email_buzon'], b['proveedor']
                logger.info(f"📥 Procesando: {email} [{prov}]")

                parsed_emails = []
                if prov == 'OUTLOOK':
                    # Usamos las credenciales AZURE de la tabla si existen, sino fallback flex
                    az_client = b['azure_client_id'] or AZURE_CLIENT_ID
                    az_secret = b['azure_client_secret'] or AZURE_CLIENT_SECRET
                    az_tenant = b['azure_tenant_id'] or AZURE_TENANT_ID
                    
                    listener = MultiTenantOutlookListener({"client_id": az_client, "secret": az_secret, "tenant": az_tenant})
                    raw_msgs = listener.fetch_emails(email, b['azure_folder_id'])
                    for m in raw_msgs:
                        parsed_emails.append({
                            "id": m["id"], "subject": m.get("subject", ""), 
                            "sender": m.get("from", {}).get("emailAddress", {}).get("address", ""),
                            "body": m.get("body", {}).get("content", ""), "date": m["receivedDateTime"],
                            "attachments": listener.get_attachments_meta(email, m["id"]), "prov_obj": listener, "email_buzon": email
                        })
                elif prov == 'ZOHO':
                    zoho = ZohoServiceV2(b['azure_client_id'], b['azure_client_secret'], b['zoho_refresh_token'], b['zoho_account_id'])
                    raw_msgs = zoho.fetch_unread_emails(b['azure_folder_id'])
                    for m in raw_msgs:
                        body = m.get("summary", "")
                        try:
                            detail = zoho.get_message_detail(m["messageId"], m.get("folderId"))
                            if detail and detail.get("content"):
                                body = detail["content"]
                        except Exception:
                            pass
                        attachments = []
                        has_att = m.get("hasAttachment")
                        if has_att == "1" or has_att is True:
                            logger.info(f"📎 Email con adjuntos detectado: {m.get('subject', '')[:50]}")
                            attachments = zoho.get_attachments_list(m["messageId"], m.get("folderId"))
                            logger.info(f"📎 Adjuntos listados: {len(attachments)} para msg={m['messageId']}")
                        parsed_emails.append({
                            "id": m["messageId"], "subject": m.get("subject", ""),
                            "sender": m.get("fromAddress", ""), "body": body,
                            "date": datetime.fromtimestamp(int(m["receivedTime"])/1000).isoformat(),
                            "attachments": attachments, "prov_obj": zoho, "email_buzon": email,
                            "folder_id": m.get("folderId"),
                        })

                # SharePoint Config para este tenant
                sp_engine = None
                if b['sharepoint_site_id']:
                    # Reutilizamos credenciales de Azure del cliente para SharePoint si no hay otras
                    sp_client = b['azure_client_id'] or AZURE_CLIENT_ID
                    sp_secret = b['azure_client_secret'] or AZURE_CLIENT_SECRET
                    sp_tenant = b['azure_tenant_id'] or AZURE_TENANT_ID
                    sp_engine = SharePointEngineV2(sp_client, sp_secret, sp_tenant, b['sharepoint_site_id'], b['sharepoint_base_folder'])

                TIPOS_VALIDOS = {"TUTELA", "PETICION", "QUEJA", "RECLAMO", "SOLICITUD"}

                for em in parsed_emails:
                    # Respuesta de ciudadano a caso existente → seguimiento, no nuevo caso
                    if await _registrar_seguimiento(conn, em, c_id):
                        continue
                    if not parece_pqrs(em['subject'], em['body'], em['sender']):
                        logger.info(f"Ignorado (no es PQRS): {em['subject'][:60]}")
                        continue
                    resultado = await clasificar_hibrido(em['subject'], em['body'], em['sender'])
                    if resultado.tipo.value not in TIPOS_VALIDOS:
                        logger.info(f"🚫 Descartado [{resultado.tipo.value}]: {em['subject'][:60]}")
                        continue
                    from datetime import timezone as _tz
                    dt = pd.to_datetime(em['date']).to_pydatetime()
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=_tz.utc)
                    venc = (pd.Timestamp(dt).tz_convert('UTC') + pd.offsets.CustomBusinessDay(n=resultado.plazo_dias)).to_pydatetime()
                    
                    # Round-robin: obtener analistas activos del tenant
                    analistas = await conn.fetch(
                        "SELECT id FROM usuarios WHERE cliente_id = $1 AND rol IN ('analista', 'abogado') AND is_active = TRUE ORDER BY created_at ASC",
                        c_id
                    )
                    asignado_a = None
                    fecha_asignacion = None
                    if analistas:
                        rr_key = f"rr:{c_id}"
                        idx = int(await r.incr(rr_key)) - 1
                        asignado_a = analistas[idx % len(analistas)]['id']
                        fecha_asignacion = dt

                    db_id = await conn.fetchval(
                        """INSERT INTO pqrs_casos (cliente_id, email_origen, asunto, cuerpo, estado, nivel_prioridad, fecha_recibido, tipo_caso, fecha_vencimiento, external_msg_id, asignado_a, fecha_asignacion)
                           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                           ON CONFLICT (cliente_id, external_msg_id) WHERE external_msg_id IS NOT NULL DO NOTHING
                           RETURNING id""",
                        c_id, em['sender'], em['subject'], em['body'], 'ABIERTO', resultado.prioridad.value, dt, resultado.tipo.value, venc, (em['id'] or '').strip() or None, asignado_a, fecha_asignacion
                    )
                    if not db_id:
                        logger.info(f"⏭️  Email ya procesado, ignorando: {em['id'][:20]}")
                        continue

                    # Acuse de recibo solo para Abogados Recovery
                    if str(c_id) == TENANT_ABOGADOS_RECOVERY:
                        try:
                            radicado = f"PQRS-{dt.year}-{str(db_id)[:8].upper()}"
                            PLAZOS = {
                                "TUTELA":    "48 horas",
                                "PETICION":  "15 días hábiles",
                                "QUEJA":     "8 días hábiles",
                                "RECLAMO":   "8 días hábiles",
                                "SOLICITUD": "15 días hábiles",
                            }
                            plazo_txt = PLAZOS.get(resultado.tipo.value, "15 días hábiles")
                            zoho_prov = em.get('prov_obj')
                            if zoho_prov and isinstance(zoho_prov, ZohoServiceV2):
                                enviado = zoho_prov.send_acuse_recibo(
                                    to_email=em['sender'],
                                    from_address=em['email_buzon'],
                                    numero_radicado=radicado,
                                    tipo_caso=resultado.tipo.value,
                                    nombre_cliente=resultado.nombre_cliente,
                                    fecha_limite=plazo_txt,
                                )
                                if enviado:
                                    await conn.execute(
                                        "UPDATE pqrs_casos SET acuse_enviado=TRUE, numero_radicado=$1 WHERE id=$2",
                                        radicado, db_id,
                                    )
                        except Exception as e_acuse:
                            logger.warning(f"Acuse no enviado para {db_id}: {e_acuse}")

                    # Generar borrador con plantilla si existe para el tenant
                    caso_radicado = radicado if str(c_id) == TENANT_ABOGADOS_RECOVERY else None
                    await generar_borrador_para_caso(
                        conn, str(c_id), str(db_id),
                        em['subject'], em['body'][:1000],
                        nombre_cliente=resultado.nombre_cliente,
                        cedula=resultado.cedula,
                        tipo_caso=resultado.tipo.value,
                        radicado=caso_radicado,
                        email_origen=em['sender'],
                    )

                    if em['attachments']:
                        logger.info(f"📎 Procesando {len(em['attachments'])} adjuntos para caso {db_id}")
                    for att in em['attachments']:
                        content = None
                        a_name, a_type, a_size = "", "", 0
                        try:
                            if prov == 'OUTLOOK':
                                a_name, a_id, a_type, a_size = att['name'], att['id'], att['contentType'], att['size']
                                content = em['prov_obj'].download_attachment(em['email_buzon'], em['id'], a_id)
                            elif prov == 'ZOHO':
                                a_name = att.get('attachmentName', 'unknown')
                                a_id = att.get('attachmentId', '')
                                a_type = att.get('contentType', 'application/octet-stream')
                                a_size = att.get('attachmentSize', 0)
                                logger.info(f"💾 Descargando adjunto Zoho: '{a_name}' ({int(a_size)/1024:.1f}KB)")
                                content = em['prov_obj'].download_attachment(em['id'], a_id, folder_id=em.get('folder_id'))
                        except Exception as dl_err:
                            logger.error(f"❌ Error descargando adjunto '{a_name}': {dl_err}")
                            continue

                        if content:
                            path = None
                            if sp_engine:
                                try:
                                    path = await sp_engine.upload_file(content, f"{db_id[:8]}_{a_name}", folder_suffix=str(db_id))
                                except Exception as spe:
                                    logger.error(f"SharePoint Failing: {spe}, falling back to MinIO")

                            if not path:
                                path = await upload_to_minio(content, f"{db_id}_{a_name}", folder=f"casos/{db_id}")

                            if path:
                                await conn.execute("INSERT INTO pqrs_adjuntos (caso_id, cliente_id, nombre_archivo, storage_path, content_type, tamano_bytes) VALUES ($1,$2,$3,$4,$5,$6)",
                                               db_id, c_id, a_name, path, a_type, int(a_size))
                                logger.info(f"✅ Adjunto guardado: '{a_name}' → {path}")
                            else:
                                logger.error(f"❌ Adjunto '{a_name}' no se pudo subir a storage")
                        else:
                            logger.warning(f"⚠️ Adjunto '{a_name}' descarga vacía (sin content)")

                    if prov == 'OUTLOOK':
                        em['prov_obj'].mark_as_read(em['email_buzon'], em['id'])
                    else:
                        em['prov_obj'].mark_as_read(em['id'])
                    notif = {
                        "id": str(db_id),
                        "subject": em['subject'],
                        "tenant_id": str(c_id),
                        "email": em['sender'],
                        "tipo": resultado.tipo.value,
                        "prioridad": resultado.prioridad.value,
                        "estado": "ABIERTO",
                        "vencimiento": venc.isoformat(),
                        "cliente_nombre": b.get('cliente_nombre') or "",
                    }
                    await r.publish("pqrs_stream_v2", json.dumps(notif))
                    logger.info(f"✅ Caso inyectado [{prov}]: {db_id}")

              except Exception as e_buzon:
                logger.error(f"💥 Error procesando buzón {b.get('email_buzon', '?')}: {e_buzon}")

            await check_tutela_alerts_2h(conn, r)

        except Exception as e:
            logger.error(f"💥 Master Worker Error: {e}")
            await asyncio.sleep(5)
        await asyncio.sleep(15)

async def check_tutela_alerts_2h(conn, r):
    """
    Publica alerta SSE para tutelas que llevan >= 2 horas sin atender.
    Se ejecuta en cada ciclo del worker (cada 15s).
    Usa alerta_2h_enviada para no repetir.
    """
    try:
        casos = await conn.fetch("""
            SELECT id, asunto, email_origen, asignado_a, cliente_id,
                   fecha_recibido, fecha_vencimiento
            FROM pqrs_casos
            WHERE tipo_caso = 'TUTELA'
              AND estado = 'ABIERTO'
              AND alerta_2h_enviada = FALSE
              AND fecha_recibido <= NOW() - INTERVAL '2 hours'
        """)

        for caso in casos:
            alerta = {
                "tipo_alerta": "TUTELA_2H",
                "id": str(caso["id"]),
                "subject": caso["asunto"],
                "email": caso["email_origen"],
                "tenant_id": str(caso["cliente_id"]),
                "vencimiento": caso["fecha_vencimiento"].isoformat() if caso["fecha_vencimiento"] else None,
                "mensaje": "⚠️ Tutela sin respuesta — 2 horas desde la llegada",
            }
            await r.publish("pqrs_stream_v2", json.dumps(alerta))
            await conn.execute(
                "UPDATE pqrs_casos SET alerta_2h_enviada = TRUE WHERE id = $1",
                caso["id"]
            )
            logger.warning(f"🔔 Alerta 2h TUTELA: {caso['id']} | {caso['asunto'][:60]}")
    except Exception as e:
        logger.error(f"💥 check_tutela_alerts_2h error: {e}")

if __name__ == "__main__":
    asyncio.run(master_worker())
