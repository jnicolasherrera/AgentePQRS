"""Envío de respuestas vía Microsoft Graph (Outlook / Microsoft 365).

Sprint FlexFintech 2026-06 — fix de remitente.
Los buzones con proveedor='OUTLOOK' (ej. clientes@flexfintech.com, cuentas en
Microsoft 365) deben responder NATIVAMENTE desde su propio buzón, no por el
fallback SMTP de Gmail (democlasificador) ni por Zoho.

Reusa el patrón de autenticación de master_worker_outlook.py:
MSAL ConfidentialClientApplication + acquire_token_for_client con las
credenciales Azure por-tenant que ya viven en config_buzones
(azure_client_id, azure_client_secret, azure_tenant_id).

Requiere permiso de aplicación **Mail.Send** (Application Permission) concedido
con admin consent en la App Registration de Azure. La ingesta ya usa Mail.Read;
Mail.Send es el permiso adicional necesario para enviar.

Endpoint: POST /users/{email_buzon}/sendMail
Doc: https://learn.microsoft.com/graph/api/user-sendmail
"""

import base64
import logging
from datetime import datetime, timedelta
from typing import List, Optional

import msal
import requests

logger = logging.getLogger("OUTLOOK_SEND")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_FIRMA_CID = "firma_arc"  # mismo CID que usa casos.py para la firma inline


class OutlookSenderV2:
    """Cliente mínimo de envío por Microsoft Graph para un tenant dado.

    Las credenciales (client_id, client_secret, tenant_id) son las MISMAS que
    usa la ingesta de ese buzón — provienen de config_buzones.
    """

    def __init__(self, client_id: str, client_secret: str, tenant_id: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    def _get_token(self) -> str:
        if self._access_token and self._token_expiry and datetime.utcnow() < self._token_expiry:
            return self._access_token
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        app = msal.ConfidentialClientApplication(
            self.client_id, authority=authority, client_credential=self.client_secret
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in result:
            raise Exception(
                "Auth Graph (send) falló: " + result.get("error_description", "sin detalle")
            )
        self._access_token = result["access_token"]
        # Token Graph vive ~60 min; renovamos a los 50 por seguridad.
        self._token_expiry = datetime.utcnow() + timedelta(minutes=50)
        return self._access_token

    def send_reply(
        self,
        from_buzon: str,
        to_email: str,
        subject: str,
        html_body: str,
        firma_bytes: Optional[bytes] = None,
        adjuntos: Optional[List[dict]] = None,
    ) -> bool:
        """Envía un email HTML desde `from_buzon` vía Graph sendMail.

        from_buzon : casilla de Microsoft 365 que figura como remitente (ej.
                     clientes@flexfintech.com). El token de app debe tener
                     Mail.Send sobre ese buzón.
        firma_bytes: si se pasa, se adjunta como imagen inline (CID) — el
                     html_body debe referenciarla con src="cid:firma_arc".
        adjuntos   : lista de {nombre, content (bytes), content_type}.
        """
        attachments = []

        # Firma institucional inline (referenciada por CID en el HTML).
        if firma_bytes:
            attachments.append({
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": "firma.jpg",
                "contentType": "image/jpeg",
                "isInline": True,
                "contentId": _FIRMA_CID,
                "contentBytes": base64.b64encode(firma_bytes).decode("ascii"),
            })

        # Adjuntos de respuesta (PDFs, etc.) — NO inline.
        for ad in (adjuntos or []):
            attachments.append({
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": ad["nombre"],
                "contentType": ad.get("content_type") or "application/octet-stream",
                "isInline": False,
                "contentBytes": base64.b64encode(ad["content"]).decode("ascii"),
            })

        message = {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": [{"emailAddress": {"address": to_email}}],
        }
        if attachments:
            message["attachments"] = attachments

        payload = {"message": message, "saveToSentItems": True}

        url = f"{GRAPH_BASE}/users/{from_buzon}/sendMail"
        headers = {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
        except Exception as e:
            logger.error(f"Graph sendMail excepción (from={from_buzon} → {to_email}): {e}")
            return False

        # sendMail devuelve 202 Accepted sin body cuando tiene éxito.
        if resp.status_code == 202:
            logger.info(f"✉️ Graph sendMail OK: {from_buzon} → {to_email}")
            return True
        logger.error(
            f"Graph sendMail FALLÓ ({resp.status_code}) from={from_buzon} → {to_email}: {resp.text[:400]}"
        )
        return False
