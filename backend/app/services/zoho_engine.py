import base64
import os
import requests
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("ZOHO_SERVICE")

def _md_to_html(text: str) -> str:
    """Convierte markdown básico (bold, italic, headers) a HTML."""
    import re
    # Headers ## → <h3>, # → <h2>
    text = re.sub(r'^### (.+)$', r'<h4 style="margin:12px 0 4px">\1</h4>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$',  r'<h3 style="margin:14px 0 6px">\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$',   r'<h2 style="margin:16px 0 8px">\1</h2>', text, flags=re.MULTILINE)
    # Bold **texto** y __texto__
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__',     r'<strong>\1</strong>', text)
    # Italic *texto* y _texto_ (no captura los que ya son bold)
    text = re.sub(r'\*([^*\n]+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_([^_\n]+?)_',   r'<em>\1</em>', text)
    # Saltos de línea → <br>
    text = text.replace("\n", "<br>")
    return text


def _firma_html() -> str:
    """Carga la firma de correo como imagen base64 embebida."""
    path = os.path.join(os.path.dirname(__file__), "..", "static", "firma_correo.jpeg")
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<br><img src="data:image/jpeg;base64,{b64}" style="max-width:560px;display:block;" alt="Firma" />'
    except Exception:
        return ""

class ZohoServiceV2:
    ZOHO_ACCOUNTS_URL = "https://accounts.zoho.com"
    ZOHO_MAIL_API = "https://mail.zoho.com/api"

    # Class-level registries shared across instances, keyed by refresh_token
    _backoff_registry: dict = {}       # {refresh_token: backoff_until}
    _token_cache: dict = {}            # {refresh_token: (access_token, expiry)}
    _consecutive_failures: dict = {}   # {refresh_token: int}

    ZOHO_MAX_RETRIES = int(os.environ.get("ZOHO_MAX_RETRIES", "4"))
    ZOHO_BACKOFF_BASE_SECONDS = int(os.environ.get("ZOHO_BACKOFF_BASE_SECONDS", "90"))

    _last_send_times: list = []
    _SEND_INTERVAL = 3.0
    _MAX_PER_MINUTE = 15

    def __init__(self, client_id, client_secret, refresh_token, account_id=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.account_id = account_id

    def _get_access_token(self):
        now = datetime.utcnow()
        # Check backoff
        backoff_until = ZohoServiceV2._backoff_registry.get(self.refresh_token)
        if backoff_until and now < backoff_until:
            remaining = int((backoff_until - now).total_seconds())
            failures = ZohoServiceV2._consecutive_failures.get(self.refresh_token, 0)
            raise Exception(f"Zoho token rate-limited, intento {failures}/{self.ZOHO_MAX_RETRIES}, retry en {remaining}s")
        # Check class-level token cache (survives instance recreation)
        cached = ZohoServiceV2._token_cache.get(self.refresh_token)
        if cached:
            token, expiry = cached
            if now < expiry:
                return token
        # Refresh token
        url = f"{self.ZOHO_ACCOUNTS_URL}/oauth/v2/token"
        data = {
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
        }
        resp = requests.post(url, data=data)
        if resp.status_code != 200:
            if "too many requests" in resp.text.lower():
                failures = ZohoServiceV2._consecutive_failures.get(self.refresh_token, 0) + 1
                ZohoServiceV2._consecutive_failures[self.refresh_token] = failures
                # Exponential backoff: 90s, 180s, 600s, 1800s
                backoff_map = {1: 1, 2: 2, 3: 6.67, 4: 20}
                multiplier = backoff_map.get(failures, 20)
                wait_seconds = int(self.ZOHO_BACKOFF_BASE_SECONDS * multiplier)
                ZohoServiceV2._backoff_registry[self.refresh_token] = now + timedelta(seconds=wait_seconds)
                if failures >= self.ZOHO_MAX_RETRIES:
                    logger.critical(
                        f"Zoho rate-limit CRITICO: {failures} fallos consecutivos, "
                        f"backoff {wait_seconds}s. Buzón posiblemente inoperante."
                    )
                else:
                    logger.warning(
                        f"Zoho rate-limit detectado, intento {failures}/{self.ZOHO_MAX_RETRIES}, "
                        f"backoff {wait_seconds}s"
                    )
            raise Exception(f"Error Zoho Token: {resp.text}")
        # Success — reset failure counter and cache token at class level
        ZohoServiceV2._backoff_registry.pop(self.refresh_token, None)
        ZohoServiceV2._consecutive_failures.pop(self.refresh_token, None)
        res = resp.json()
        access_token = res["access_token"]
        expiry = now + timedelta(seconds=res.get("expires_in", 3600) - 60)
        ZohoServiceV2._token_cache[self.refresh_token] = (access_token, expiry)
        return access_token

    def _make_request(self, endpoint, method="GET", params=None, json_data=None):
        token = self._get_access_token()
        headers = {"Authorization": f"Zoho-oauthtoken {token}", "Content-Type": "application/json"}
        url = f"{self.ZOHO_MAIL_API}{endpoint}"
        if method == "GET":
            response = requests.get(url, headers=headers, params=params)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=json_data)
        else:
            response = requests.request(method, url, headers=headers, json=json_data)
        if response.status_code >= 400:
            logger.error(f"Zoho API Error [{method} {endpoint}]: {response.text}")
            return None
        return response.json()

    def fetch_unread_emails(self, folder_id="ZOHO_INBOX"):
        acc_id = self._get_account_id()
        # Resolver folder_id numérico si viene como placeholder
        if not folder_id or folder_id == "ZOHO_INBOX":
            folders_res = self._make_request(f"/accounts/{acc_id}/folders")
            if folders_res:
                for f in folders_res.get("data", []):
                    if f.get("folderName", "").upper() == "INBOX":
                        folder_id = f["folderId"]
                        break
            if not folder_id or folder_id == "ZOHO_INBOX":
                logger.error("Zoho: no se encontró el folderId de INBOX")
                return []

        endpoint = f"/accounts/{acc_id}/messages/view"
        params = {"folderId": folder_id, "limit": 10, "status": "unread"}
        res = self._make_request(endpoint, params=params)
        return res.get("data", []) if res else []

    def get_message_detail(self, message_id, folder_id=None):
        acc_id = self._get_account_id()
        if folder_id:
            res = self._make_request(f"/accounts/{acc_id}/folders/{folder_id}/messages/{message_id}/content")
        else:
            res = self._make_request(f"/accounts/{acc_id}/messages/{message_id}/content")
        return res.get("data") if res else None

    def get_attachments_list(self, message_id, folder_id):
        """Devuelve lista de adjuntos: [{attachmentId, attachmentName, contentType, attachmentSize}]"""
        acc_id = self._get_account_id()
        res = self._make_request(
            f"/accounts/{acc_id}/folders/{folder_id}/messages/{message_id}/attachmentinfo"
        )
        if res and isinstance(res.get("data"), dict):
            atts = res["data"].get("attachments", [])
            logger.info(f"Zoho adjuntos encontrados: {len(atts)} para msg={message_id}")
            return atts
        logger.warning(f"Zoho attachmentinfo retornó vacío para msg={message_id} (res={type(res).__name__})")
        return []

    def download_attachment(self, message_id, attachment_id, folder_id=None):
        acc_id = self._get_account_id()
        token = self._get_access_token()
        if folder_id:
            url = f"{self.ZOHO_MAIL_API}/accounts/{acc_id}/folders/{folder_id}/messages/{message_id}/attachments/{attachment_id}"
        else:
            url = f"{self.ZOHO_MAIL_API}/accounts/{acc_id}/messages/{message_id}/attachments/{attachment_id}"
        resp = requests.get(url, headers={"Authorization": f"Zoho-oauthtoken {token}"})
        if resp.status_code == 200 and resp.content:
            logger.info(f"Zoho adjunto descargado: att={attachment_id} ({len(resp.content)} bytes)")
            return resp.content
        logger.error(f"Zoho descarga falló: att={attachment_id} status={resp.status_code} body={resp.text[:200]}")
        return None

    def mark_as_read(self, message_id):
        acc_id = self._get_account_id()
        self._make_request(
            f"/accounts/{acc_id}/updatemessage",
            method="PUT",
            json_data={"mode": "markAsRead", "messageId": [message_id]}
        )

    def _rate_limit_send(self):
        """Esperar si es necesario antes de enviar para no disparar el bloqueo de Zoho."""
        import time
        now = time.time()
        ZohoServiceV2._last_send_times = [
            t for t in ZohoServiceV2._last_send_times if now - t < 60
        ]
        if len(ZohoServiceV2._last_send_times) >= ZohoServiceV2._MAX_PER_MINUTE:
            oldest = ZohoServiceV2._last_send_times[0]
            wait = 60 - (now - oldest) + 1
            if wait > 0:
                logger.warning(f"Zoho rate limit: esperando {wait:.1f}s para no exceder {ZohoServiceV2._MAX_PER_MINUTE} emails/min")
                time.sleep(wait)
        if ZohoServiceV2._last_send_times:
            elapsed = now - ZohoServiceV2._last_send_times[-1]
            if elapsed < ZohoServiceV2._SEND_INTERVAL:
                time.sleep(ZohoServiceV2._SEND_INTERVAL - elapsed)
        ZohoServiceV2._last_send_times.append(time.time())

    def send_reply(self, to_email: str, subject: str, body: str, from_address: str,
                   adjuntos: list | None = None) -> bool:
        """Envía un email de respuesta HTML con firma institucional vía Zoho Mail API.
        adjuntos: lista de {nombre, content (bytes), content_type}
        """
        self._rate_limit_send()
        firma = _firma_html()
        html_body = (
            "<div style='font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.6'>"
            + _md_to_html(body)
            + firma
            + "</div>"
        )
        acc_id = self._get_account_id()

        if not adjuntos:
            res = self._make_request(
                f"/accounts/{acc_id}/messages",
                method="POST",
                json_data={
                    "fromAddress": from_address,
                    "toAddress": to_email,
                    "subject": subject,
                    "content": html_body,
                    "mailFormat": "html",
                },
            )
            return res is not None

        # multipart/form-data cuando hay adjuntos
        token = self._get_access_token()
        url = f"{self.ZOHO_MAIL_API}/accounts/{acc_id}/messages"
        headers = {"Authorization": f"Zoho-oauthtoken {token}"}
        data = {
            "fromAddress": from_address,
            "toAddress": to_email,
            "subject": subject,
            "content": html_body,
            "mailFormat": "html",
        }
        files = [
            ("attachment", (adj["nombre"], adj["content"], adj["content_type"]))
            for adj in adjuntos
        ]
        resp = requests.post(url, headers=headers, data=data, files=files)
        if resp.status_code >= 400:
            logger.error(f"Zoho send con adjuntos [{resp.status_code}]: {resp.text}")
            return False
        return True

    def send_acuse_recibo(
        self,
        to_email: str,
        from_address: str,
        numero_radicado: str,
        tipo_caso: str,
        nombre_cliente: str | None,
        fecha_limite: str,
        nombre_entidad: str = "FlexLegal",
    ) -> bool:
        """Envía acuse de recibo HTML al ciudadano/cliente al radicar su caso."""
        self._rate_limit_send()
        TONOS = {
            "TUTELA":    ("Acción de Tutela",    "#DC2626", "Su caso fue escalado al área jurídica con carácter urgente."),
            "PETICION":  ("Derecho de Petición", "#2563EB", "Su petición fue radicada y asignada al equipo responsable."),
            "QUEJA":     ("Queja",               "#D97706", "Lamentamos su inconformidad. Nuestro equipo dará respuesta oportuna."),
            "RECLAMO":   ("Reclamo",             "#D97706", "Su reclamo fue recibido y será atendido dentro del plazo legal."),
            "SOLICITUD": ("Solicitud",           "#059669", "Su solicitud fue radicada y será procesada a la brevedad."),
        }
        label, color, mensaje_tipo = TONOS.get(tipo_caso, ("Caso", "#6B7280", "Su caso fue recibido correctamente."))
        saludo = f"Estimado/a {nombre_cliente}," if nombre_cliente else "Estimado/a usuario/a,"

        html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:32px 0">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08)">

        <!-- Header -->
        <tr>
          <td style="background:#0a0a0a;padding:24px 32px;">
            <span style="color:#9D50FF;font-size:22px;font-weight:bold;letter-spacing:1px;">SistemaPQRS</span>
            <span style="color:#555;font-size:13px;margin-left:8px;">by {nombre_entidad}</span>
          </td>
        </tr>

        <!-- Badge tipo -->
        <tr>
          <td style="padding:24px 32px 0">
            <span style="background:{color};color:#fff;padding:4px 14px;border-radius:20px;font-size:12px;font-weight:bold;letter-spacing:0.5px;">{label}</span>
          </td>
        </tr>

        <!-- Cuerpo -->
        <tr>
          <td style="padding:20px 32px 8px">
            <p style="color:#111;font-size:16px;margin:0 0 8px">{saludo}</p>
            <p style="color:#374151;font-size:15px;margin:0 0 20px">
              Hemos recibido correctamente su comunicación. {mensaje_tipo}
            </p>
          </td>
        </tr>

        <!-- Cuadro radicado -->
        <tr>
          <td style="padding:0 32px 20px">
            <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px">
              <tr>
                <td style="padding:16px 20px">
                  <p style="margin:0 0 10px;color:#6B7280;font-size:12px;text-transform:uppercase;letter-spacing:0.5px;">Número de radicado</p>
                  <p style="margin:0 0 16px;color:#111;font-size:22px;font-weight:bold;letter-spacing:1px;">{numero_radicado}</p>
                  <table>
                    <tr>
                      <td style="padding-right:32px">
                        <p style="margin:0;color:#6B7280;font-size:12px">Tipo de caso</p>
                        <p style="margin:4px 0 0;color:#111;font-size:14px;font-weight:600">{label}</p>
                      </td>
                      <td>
                        <p style="margin:0;color:#6B7280;font-size:12px">Fecha límite de respuesta</p>
                        <p style="margin:4px 0 0;color:{color};font-size:14px;font-weight:600">{fecha_limite}</p>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Instrucción -->
        <tr>
          <td style="padding:0 32px 24px">
            <p style="color:#374151;font-size:14px;margin:0">
              Conserve el número de radicado para hacer seguimiento a su caso.
              Recibirá una respuesta formal antes de la fecha indicada.
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:16px 32px">
            <p style="margin:0;color:#9CA3AF;font-size:12px">
              Este mensaje fue generado automáticamente por SistemaPQRS. Por favor no responda a este correo.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

        acc_id = self._get_account_id()
        res = self._make_request(
            f"/accounts/{acc_id}/messages",
            method="POST",
            json_data={
                "fromAddress": from_address,
                "toAddress":   to_email,
                "subject":     f"Radicado {numero_radicado} — Confirmación de recepción",
                "content":     html,
                "mailFormat":  "html",
            },
        )
        return res is not None

    def _get_account_id(self):
        if self.account_id:
            return self.account_id
        res = self._make_request("/accounts")
        if res and res.get("data"):
            self.account_id = res["data"][0]["accountId"]
            return self.account_id
        raise Exception("No se pudo obtener Zoho account_id")
