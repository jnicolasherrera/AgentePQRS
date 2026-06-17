import asyncio
import json
import os
import msal
import requests
import asyncpg
from asyncpg.exceptions import InterfaceError, ConnectionDoesNotExistError, PostgresConnectionError
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

# Detector de "tutela escalada de PQR previo" — feature de calidad de servicio.
# Captura el prefijo de 8 hex del id (acuse: PQRS-{year}-{id[:8]}).
RAD_PATTERN = re.compile(r'\bPQRS?-\d{4}-([A-F0-9]{6,12})\b', re.IGNORECASE)

async def detectar_pqr_origenes(conn, db_id, cliente_id, email_origen, cuerpo):
    """
    Para una TUTELA recién insertada, busca PQRs previos del mismo demandante
    en los últimos 90 días que probablemente la originaron (calidad de servicio).

    Estrategias:
      A. Match por email_origen (mismo demandante), ventana 90 días, tipo != TUTELA.
      B. Match por radicado citado en cuerpo (formato PQRS-YYYY-HHHHHHHH).

    Retorna lista de UUIDs (puede ser vacía).
    """
    if not email_origen:
        return []

    # A — mismo email_origen en últimos 90 días
    rows_a = await conn.fetch(
        """SELECT id FROM pqrs_casos
           WHERE cliente_id = $1
             AND LOWER(email_origen) = LOWER($2)
             AND fecha_recibido >= NOW() - INTERVAL '90 days'
             AND tipo_caso != 'TUTELA'
             AND id != $3""",
        cliente_id, email_origen, db_id
    )
    ids_match = {r['id'] for r in rows_a}

    # B — radicados citados en el cuerpo de la tutela
    if cuerpo:
        prefixes = sorted({m.upper() for m in RAD_PATTERN.findall(cuerpo)})
        if prefixes:
            rows_b = await conn.fetch(
                """SELECT id FROM pqrs_casos
                   WHERE cliente_id = $1
                     AND tipo_caso != 'TUTELA'
                     AND id != $2
                     AND UPPER(SUBSTRING(id::text, 1, 8)) = ANY($3::text[])""",
                cliente_id, db_id, prefixes
            )
            ids_match.update(r['id'] for r in rows_b)

    return list(ids_match)

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
from app.services.clasificador import parece_pqrs, es_remitente_juzgado, es_spam
from app.services.workflow_classifier import clasificar_workflow
from app.services.plantilla_engine import detectar_problematica_dinamica
from app.constants import TENANT_ABOGADOS_RECOVERY

# Sprint FF hotfix 2026-05-27: ATENCION_CLIENTE solo aplica a FlexFintech.
# Recovery + Demo + cualquier otro tenant SIEMPRE va por flow PQRS legal,
# independiente del contenido. Esto evita que casos Recovery con keywords
# como "comprobante de pago" o "paz y salvo" en el cuerpo se desvíen al
# flow simplificado AC (que NO genera borrador con Claude si tipo_caso=None).
TENANT_FLEXFINTECH = "f7e8d9c0-b1a2-3456-7890-123456abcdef"

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

_ACTIVITY_FLAG = os.environ.get("ACTIVITY_FLAG", "/tmp/master_worker_last_activity")


def _touch_activity():
    """DT-33: actualiza timestamp para healthcheck. No-crítico al runtime —
    si falla (filesystem lleno, permisos), logueamos warning y seguimos.
    Healthcheck eventualmente marcará unhealthy si el flag queda stale."""
    try:
        with open(_ACTIVITY_FLAG, "w") as f:
            f.write(datetime.utcnow().isoformat())
    except Exception as e:
        logger.warning(f"⚠️ _touch_activity failed: {e}")


async def _ensure_alive_connection(conn, dsn: str, force: bool = False):
    """DT-32: si conn está cerrada, es None, o force=True, crea una nueva.

    `force=True` se usa desde el except del loop tras detectar InterfaceError —
    necesario porque is_closed() puede retornar False sobre conexión rota a
    nivel TCP/protocol. Sin force, la conn aparentemente "viva" pero rota se
    preservaría y el bucle reincidiría.

    timeout=10 al connect setup; command_timeout=30 limita queries individuales.

    Retorna (conn, recreated_bool)."""
    if conn is None or conn.is_closed() or force:
        if conn is not None:
            try:
                await conn.close()
            except Exception:
                pass
        new_conn = await asyncpg.connect(dsn, command_timeout=30, timeout=10)
        logger.info("🔄 DB connection (re)abierta")
        return new_conn, True
    return conn, False


# ─────────────────────────────────────────────────────────────────────────
# Helpers para documento_peticionante (sprint FF fix bug_020A)
# ─────────────────────────────────────────────────────────────────────────

# Patrón cédula colombiana: secuencia de 6-12 dígitos, opcionalmente con
# puntos como separadores. Acepta "1.007.403.296", "1007403296", "12345678".
_RE_CEDULA = re.compile(r'\b(\d{1,3}(?:\.\d{3}){2,4}|\d{6,12})\b')

# Imágenes inline: <img src="cid:...">. Cap ~2 MB decodificado (~2.8M chars b64).
_RE_CID = re.compile(r'cid:([^"\'>\s)]+)', re.IGNORECASE)
_INLINE_MAX_B64 = 2_800_000


async def _lookup_cedula_historica(conn, cliente_id, sender):
    """Busca cédula en historico_email_cedula por sender (case-insensitive)."""
    if not sender:
        return None
    try:
        row = await conn.fetchrow(
            "SELECT cedula FROM historico_email_cedula "
            "WHERE cliente_id = $1 AND lower(email) = lower($2) LIMIT 1",
            cliente_id, sender,
        )
        return row["cedula"] if row else None
    except Exception as e:
        logger.warning(f"lookup cedula histórica falló: {e}")
        return None


def _extraer_cedula_del_cuerpo(cuerpo):
    """Fallback: extrae cédula del cuerpo del email. None si no encuentra."""
    if not cuerpo:
        return None
    m = _RE_CEDULA.search(cuerpo[:2000])
    if not m:
        return None
    raw = m.group(1)
    digits = re.sub(r'\D', '', raw)
    return digits if 6 <= len(digits) <= 12 else None


def _download_attachments_inline(em, prov):
    """Descarga los adjuntos del email en memoria (sin uploadear todavía).

    Devuelve lista de dicts {nombre_archivo, content_bytes, content_type, raw_meta}
    para alimentar el borrador con texto extraído. El raw_meta sirve para
    el upload posterior a MinIO/SP sin re-descargar.

    Best-effort: cada adjunto que falle se loggea y skipea. NUNCA propaga.
    Sprint FF F1 2026-05-27.
    """
    out = []
    for att in (em.get('attachments') or []):
        try:
            if prov == 'OUTLOOK':
                a_name = att['name']; a_id = att['id']
                a_type = att.get('contentType', 'application/octet-stream')
                a_size = att.get('size', 0)
                content = em['prov_obj'].download_attachment(em['email_buzon'], em['id'], a_id)
            elif prov == 'ZOHO':
                a_name = att.get('attachmentName', 'unknown')
                a_id = att.get('attachmentId', '')
                a_type = att.get('contentType', 'application/octet-stream')
                a_size = att.get('attachmentSize', 0)
                content = em['prov_obj'].download_attachment(em['id'], a_id, folder_id=em.get('folder_id'))
            else:
                continue
            if content:
                out.append({
                    "nombre_archivo": a_name,
                    "content_bytes": content,
                    "content_type": a_type,
                    "size": int(a_size or 0),
                })
        except Exception as e:
            logger.warning(f"download_attachment falló para {att}: {e}")
    return out


def _inline_images_a_base64(em, prov):
    """Reemplaza <img src="cid:..."> por data:base64 usando el contentBytes que
    Graph ya devuelve en get_attachments_meta. Devuelve el cuerpo reescrito.

    Solo OUTLOOK (FF usa Graph; Zoho fuera de alcance). Best-effort: si una
    imagen no matchea o supera el cap, se deja el cid: intacto. NUNCA propaga.
    Sprint imágenes inline 2026-06-17.
    """
    body = em.get('body') or ''
    if prov != 'OUTLOOK' or 'cid:' not in body.lower():
        return body
    try:
        mapa = {}
        for att in (em.get('attachments') or []):
            cid = (att.get('contentId') or '').strip().strip('<>').strip()
            b64 = att.get('contentBytes')
            if not cid or not b64:
                continue
            if len(b64) > _INLINE_MAX_B64:
                logger.warning(f"inline image {cid} supera cap ({len(b64)} chars b64), se saltea")
                continue
            ctype = att.get('contentType') or 'application/octet-stream'
            mapa[cid] = f'data:{ctype};base64,{b64}'

        if not mapa:
            return body

        def _repl(m):
            cid = m.group(1).strip().strip('<>').strip()
            return mapa.get(cid, m.group(0))

        return _RE_CID.sub(_repl, body)
    except Exception as e:
        logger.warning(f"_inline_images_a_base64 falló, body intacto: {e}")
        return body


async def procesar_atencion_cliente(conn, r, em, c_id, b, dt, prov):
    """Flow simplificado para emails clasificados como ATENCION_CLIENTE
    (consultas operativas, no PQRS legal).

    Diferencias vs flow PQRS:
    - No usa `clasificar_hibrido` (tipo_caso queda NULL).
    - No calcula `fecha_vencimiento` con festivos CO (no hay plazo legal).
    - No envía acuse de cortesía (DT-41 N/A).
    - Round-robin incluye `admin` además de analista/abogado (FlexFintech
      tiene solo admins activos hoy).
    - Inserta `tipo_workflow='ATENCION_CLIENTE'` + `problematica_detectada`.
    - Generación de borrador filtra plantillas por workflow=ATENCION_CLIENTE.

    Sprint FlexFintech 2026-05-27 — bloque 3 + fixes ultrareview #11.
    """
    # bug_005 fix: filtro de spam ANTES de cualquier insert / borrador / SSE.
    # El flow PQRS pasa por parece_pqrs (que filtra noreply@, newsletter@, etc.);
    # AC bypassaba ese filtro y procesaba DHL/transactional/newsletter como casos.
    if es_spam(em['sender'], em['subject']):
        logger.info(f"AC ignorado (spam): {em['subject'][:60]}")
        try:
            if prov == 'OUTLOOK':
                em['prov_obj'].mark_as_read(em['email_buzon'], em['id'])
            else:
                em['prov_obj'].mark_as_read(em['id'])
        except Exception:
            pass
        return None

    # bug_016 fix: detector dinámico — matchea también las plantillas
    # DB seedeadas para FF (49 plantillas con keywords), no solo las 8 hardcoded.
    problematica = await detectar_problematica_dinamica(
        conn, str(c_id), em['subject'], em['body'],
        tipo_workflow='ATENCION_CLIENTE',
    )

    # bug_020A fix: autocompletar documento_peticionante.
    # 1) Lookup en historico_email_cedula (3010 pares seedeados FF).
    # 2) Fallback a extracción regex del cuerpo.
    documento = await _lookup_cedula_historica(conn, c_id, em['sender'])
    if not documento:
        documento = _extraer_cedula_del_cuerpo(em['body'])

    # Round-robin entre agentes (admin/analista/abogado activos)
    agentes = await conn.fetch(
        "SELECT id FROM usuarios WHERE cliente_id = $1 "
        "AND rol IN ('admin','analista','abogado') AND is_active = TRUE "
        "ORDER BY created_at ASC",
        c_id,
    )
    asignado_a, fecha_asignacion = None, None
    if agentes:
        idx = int(await r.incr(f"rr_ac:{c_id}")) - 1
        asignado_a = agentes[idx % len(agentes)]['id']
        fecha_asignacion = dt

    db_id = await conn.fetchval(
        """INSERT INTO pqrs_casos
              (cliente_id, email_origen, asunto, cuerpo, estado, nivel_prioridad,
               fecha_recibido, tipo_workflow, problematica_detectada,
               documento_peticionante, external_msg_id, asignado_a, fecha_asignacion)
           VALUES ($1,$2,$3,$4,'ABIERTO','NORMAL',$5,'ATENCION_CLIENTE',$6,$7,$8,$9,$10)
           ON CONFLICT (cliente_id, external_msg_id) WHERE external_msg_id IS NOT NULL DO NOTHING
           RETURNING id""",
        c_id, em['sender'], em['subject'], em.get('cuerpo_html') or em['body'], dt,
        problematica, documento, (em['id'] or '').strip() or None,
        asignado_a, fecha_asignacion,
    )
    if not db_id:
        logger.info(f"⏭️  AC email ya procesado: {(em['id'] or '')[:20]}")
        return None

    # Sprint FF F1: descargar adjuntos para contexto del borrador
    adjuntos_descargados = _download_attachments_inline(em, prov) if em.get('attachments') else []
    if adjuntos_descargados:
        logger.info(f"📎 AC {len(adjuntos_descargados)} adjuntos descargados para contexto (caso {db_id})")

    # Borrador con plantillas AC (filter en obtener_plantilla via tipo_workflow)
    try:
        await generar_borrador_para_caso(
            conn, str(c_id), str(db_id),
            em['subject'], em['body'][:1000],
            nombre_cliente=None,
            tipo_caso=None,
            email_origen=em['sender'],
            tipo_workflow='ATENCION_CLIENTE',
            adjuntos_inline=adjuntos_descargados or None,
        )
    except Exception as e:
        logger.warning(f"AC borrador falló para {db_id}: {e}")

    # Upload adjuntos AC a MinIO + INSERT pqrs_adjuntos (best-effort)
    for adj in adjuntos_descargados:
        try:
            path = await upload_to_minio(adj["content_bytes"], f"{db_id}_{adj['nombre_archivo']}", folder=f"casos/{db_id}")
            if path:
                await conn.execute(
                    "INSERT INTO pqrs_adjuntos (caso_id, cliente_id, nombre_archivo, storage_path, content_type, tamano_bytes) "
                    "VALUES ($1,$2,$3,$4,$5,$6)",
                    db_id, c_id, adj["nombre_archivo"], path, adj["content_type"], adj["size"],
                )
        except Exception as e:
            logger.warning(f"AC adjunto upload falló: {e}")

    # Mark as read (mismo patrón que PQRS)
    try:
        if prov == 'OUTLOOK':
            em['prov_obj'].mark_as_read(em['email_buzon'], em['id'])
        else:
            em['prov_obj'].mark_as_read(em['id'])
    except Exception as e:
        logger.warning(f"AC mark_as_read falló: {e}")

    # Publicar SSE — frontend distingue por campo `tipo`
    notif = {
        "id": str(db_id), "subject": em['subject'], "tenant_id": str(c_id),
        "email": em['sender'], "tipo": "ATENCION_CLIENTE",
        "problematica": problematica, "prioridad": "NORMAL",
        "estado": "ABIERTO", "cliente_nombre": b.get('cliente_nombre') or "",
    }
    await r.publish("pqrs_stream_v2", json.dumps(notif))
    logger.info(f"✅ AC caso inyectado [{prov}]: {db_id} (problematica={problematica})")
    return db_id


async def master_worker():
    logger.info("🚀 [MASTER WORKER V2.1] Híbrido: Outlook/Zoho + SharePoint Storage...")
    r = redis.from_url(REDIS_URL, decode_responses=True)
    conn, _ = await _ensure_alive_connection(None, DATABASE_URL)
    outlook = MultiTenantOutlookListener()

    while True:
        _touch_activity()  # DT-33: marcar actividad antes de cada ciclo
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

                # Cutoff y workflow default heredados del buzón (sprint FF bloque 3).
                procesar_desde = b.get('procesar_desde')  # TIMESTAMPTZ o None
                default_workflow = b.get('tipo_workflow') or 'PQRS'

                for em in parsed_emails:
                    # Parse fecha del email una vez (la usan filtro cutoff + INSERT).
                    from datetime import timezone as _tz
                    dt = pd.to_datetime(em['date']).to_pydatetime()
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=_tz.utc)

                    # bug_010 fix: chequear seguimiento ANTES del cutoff. Un Re:
                    # viejo de un caso abierto debe registrarse como comentario,
                    # no descartarse silenciosamente. _registrar_seguimiento es
                    # barato (short-circuit si subject no es Re:/Fw:).
                    if await _registrar_seguimiento(conn, em, c_id):
                        continue

                    # Cutoff: ignorar mails anteriores a procesar_desde (evita
                    # reprocesar histórico como CASOS NUEVOS al activar buzón).
                    if procesar_desde and dt < procesar_desde:
                        continue

                    # Imágenes inline (cid:) → base64 embebido para el render del
                    # frontend. En clave aparte: NO contamina em['body'] (que usa
                    # la clasificación / el prompt de Claude). Best-effort.
                    em['cuerpo_html'] = _inline_images_a_base64(em, prov)

                    # ─── Dispatcher PQRS vs ATENCION_CLIENTE (sprint FF bloque 3) ───
                    # Hotfix 2026-05-27: AC SOLO para FlexFintech (decisión del
                    # cliente). Otros tenants siempre PQRS, no importa el contenido.
                    if str(c_id) == TENANT_FLEXFINTECH:
                        workflow = clasificar_workflow(
                            em['subject'], em['body'], em['sender'],
                            default_workflow=default_workflow,
                        )
                    else:
                        workflow = 'PQRS'

                    if workflow == 'ATENCION_CLIENTE':
                        await procesar_atencion_cliente(conn, r, em, c_id, b, dt, prov)
                        continue

                    # ─── Flow PQRS (legal — sin cambios) ───
                    if not parece_pqrs(em['subject'], em['body'], em['sender']):
                        logger.info(f"Ignorado (no es PQRS): {em['subject'][:60]}")
                        continue
                    resultado = await clasificar_hibrido(em['subject'], em['body'], em['sender'])
                    if resultado.tipo.value not in TIPOS_VALIDOS:
                        logger.info(f"🚫 Descartado [{resultado.tipo.value}]: {em['subject'][:60]}")
                        continue
                    # dt ya calculado arriba (al inicio del loop). Calcular vencimiento:
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

                    # bug_020A fix: populate documento_peticionante.
                    # Prioridad: clasificar_hibrido.cedula → historico_email_cedula → regex body.
                    documento = (resultado.cedula or "").strip() or None
                    if not documento:
                        documento = await _lookup_cedula_historica(conn, c_id, em['sender'])
                    if not documento:
                        documento = _extraer_cedula_del_cuerpo(em['body'])

                    db_id = await conn.fetchval(
                        """INSERT INTO pqrs_casos (cliente_id, email_origen, asunto, cuerpo, estado, nivel_prioridad, fecha_recibido, tipo_caso, fecha_vencimiento, documento_peticionante, external_msg_id, asignado_a, fecha_asignacion)
                           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                           ON CONFLICT (cliente_id, external_msg_id) WHERE external_msg_id IS NOT NULL DO NOTHING
                           RETURNING id""",
                        c_id, em['sender'], em['subject'], em['cuerpo_html'], 'ABIERTO', resultado.prioridad.value, dt, resultado.tipo.value, venc, documento, (em['id'] or '').strip() or None, asignado_a, fecha_asignacion
                    )
                    if not db_id:
                        logger.info(f"⏭️  Email ya procesado, ignorando: {em['id'][:20]}")
                        continue

                    # Auto-match: si es TUTELA, ¿hay PQR previo del mismo demandante?
                    # Señal de calidad de servicio: tutela = consecuencia de mala atención.
                    if resultado.tipo.value == "TUTELA":
                        try:
                            origenes = await detectar_pqr_origenes(
                                conn, db_id, c_id, em['sender'], em['body']
                            )
                            if origenes:
                                await conn.execute(
                                    "UPDATE pqrs_casos SET pqr_origenes = $1 WHERE id = $2",
                                    origenes, db_id
                                )
                                logger.info(
                                    f"⚖️  TUTELA {str(db_id)[:8]} escalada de "
                                    f"{len(origenes)} PQR(s) previo(s): "
                                    f"{[str(o)[:8] for o in origenes]}"
                                )
                        except Exception as e:
                            logger.warning(f"⚠️  Auto-match pqr_origenes falló para {db_id}: {e}")

                    # Acuse de recibo solo para Abogados Recovery (excluye tutelas
                    # y remitentes judiciales — DT-41: no responder un oficio de
                    # juzgado con un acuse automático de cortesía).
                    if (str(c_id) == TENANT_ABOGADOS_RECOVERY
                            and resultado.tipo.value != "TUTELA"
                            and not es_remitente_juzgado(em['sender'])):
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

                    # Sprint FF F1: descargar adjuntos UNA VEZ ANTES del borrador
                    # para que Claude los lea como contexto (no doble descarga
                    # entre extract y upload posterior).
                    adjuntos_descargados = _download_attachments_inline(em, prov) if em.get('attachments') else []
                    if adjuntos_descargados:
                        logger.info(f"📎 {len(adjuntos_descargados)} adjuntos descargados para contexto borrador (caso {db_id})")

                    # Generar borrador con plantilla si existe para el tenant + adjuntos inline
                    caso_radicado = radicado if str(c_id) == TENANT_ABOGADOS_RECOVERY else None
                    await generar_borrador_para_caso(
                        conn, str(c_id), str(db_id),
                        em['subject'], em['body'][:1000],
                        nombre_cliente=resultado.nombre_cliente,
                        cedula=resultado.cedula,
                        tipo_caso=resultado.tipo.value,
                        radicado=caso_radicado,
                        email_origen=em['sender'],
                        tipo_workflow='PQRS',
                        adjuntos_inline=adjuntos_descargados or None,
                    )

                    # Upload adjuntos a MinIO/SP + INSERT pqrs_adjuntos (con bytes ya en memoria)
                    for adj in adjuntos_descargados:
                        a_name = adj["nombre_archivo"]
                        a_type = adj["content_type"]
                        a_size = adj["size"]
                        content = adj["content_bytes"]
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

        except (InterfaceError, ConnectionDoesNotExistError, PostgresConnectionError, ConnectionResetError, OSError, asyncio.TimeoutError) as conn_err:
            # DT-32: pool/conn muerta (típico tras restart de DB). Recrear.
            # force=True porque is_closed() puede ser False sobre conn rota TCP.
            logger.warning(f"⚠️ DB connection lost: {conn_err.__class__.__name__}: {conn_err}")
            try:
                conn, _ = await _ensure_alive_connection(conn, DATABASE_URL, force=True)
            except Exception as recreate_err:
                logger.error(f"❌ Failed to recreate DB conn: {recreate_err}")
                await asyncio.sleep(10)
                continue
            await asyncio.sleep(2)
            continue
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
