import msal
import requests
from datetime import datetime, timedelta
import logging
import os

logger = logging.getLogger(__name__)

class SharePointEngineV2:
    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(self, client_id, client_secret, tenant_id, site_id, base_folder):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.site_id = site_id
        self.base_folder = base_folder
        self._access_token = None
        self._token_expiry = None
        self._drive_id = None

    def _get_access_token(self):
        if self._access_token and self._token_expiry and datetime.utcnow() < self._token_expiry:
            return self._access_token

        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        app = msal.ConfidentialClientApplication(
            self.client_id, authority=authority, client_credential=self.client_secret
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in result:
            raise Exception("MSAL SharePoint Auth Error")
        
        self._access_token = result["access_token"]
        self._token_expiry = datetime.utcnow() + timedelta(minutes=50)
        return self._access_token

    def _get_drive_id(self):
        if self._drive_id: return self._drive_id
        token = self._get_access_token()
        url = f"{self.GRAPH_API_BASE}/sites/{self.site_id}/drives"
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
        drives = resp.json().get("value", [])
        for d in drives:
            if "Documentos" in d.get("name", "") or d.get("driveType") == "documentLibrary":
                self._drive_id = d["id"]
                return d["id"]
        return drives[0]["id"] if drives else None

    async def upload_file(self, content: bytes, filename: str, folder_suffix: str):
        """Sube archivo a SharePoint. folder_suffix suele ser casos/{id}"""
        token = self._get_access_token()
        drive_id = self._get_drive_id()

        # Estructura organizada: Base / COLOMBIA / Año-Mes / Caso
        mes_anio = datetime.now().strftime("%Y-%m")
        full_path = f"{self.base_folder}/COLOMBIA/{mes_anio}/{folder_suffix}/{filename}"
        encoded_path = full_path.replace(" ", "%20")

        url = f"{self.GRAPH_API_BASE}/drives/{drive_id}/root:/{encoded_path}:/content"
        resp = requests.put(url, headers={"Authorization": f"Bearer {token}"}, data=content)

        if resp.status_code < 300:
            logger.info(f"✅ Archivo en SharePoint: {full_path}")
            return full_path
        else:
            logger.error(f"❌ SharePoint Upload Error: {resp.text}")
            return None

    # ─────────────────────────────────────────────────────────────────────
    # archivar_caso — sprint FlexFintech 2026-05-27 bloque 6
    # ─────────────────────────────────────────────────────────────────────

    def _upload_to(self, drive_id, full_path, content, content_type="application/octet-stream"):
        """PUT bytes a un path absoluto del drive. Crea carpetas si no existen."""
        token = self._get_access_token()
        encoded = requests.utils.quote(full_path, safe="/")
        url = f"{self.GRAPH_API_BASE}/drives/{drive_id}/root:/{encoded}:/content"
        resp = requests.put(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": content_type},
            data=content,
        )
        if resp.status_code < 300:
            return full_path
        logger.error("SP upload %s falló: %d %s", full_path, resp.status_code, resp.text[:300])
        return None

    async def archivar_caso(
        self,
        *,
        cedula,
        fecha,
        mail_original_html,
        respuesta_html,
        adjuntos=None,
    ):
        """Archiva una contestación PQRS en {base_folder}/{cedula}_{YYYY-MM-DD}/.

        Sube 3 tipos de archivo:
          - mail_original.html  (decisión D5 del sprint — HTML, no .eml)
          - respuesta.html
          - cada adjunto del mail entrante con su nombre original

        Args:
            cedula: documento del peticionante. Si vacía → None (skip).
            fecha: datetime/date/str — se formatea YYYY-MM-DD (decisión D4).
            mail_original_html, respuesta_html: bytes UTF-8 renderizados.
            adjuntos: lista de dicts {nombre_archivo, content_bytes, content_type}.

        Returns:
            Path SP de la carpeta del caso si todo OK; None si falla.

        Best-effort: si alguna PUT falla, log warn y devuelve None.
        El caller (enviar-lote) NO debe romper su flow ante esto.
        """
        if not cedula or not str(cedula).strip():
            logger.warning("SP archivar_caso: cedula vacía — skip archivado")
            return None

        # Formato fecha (decisión D4): YYYY-MM-DD
        if hasattr(fecha, "strftime"):
            fecha_s = fecha.strftime("%Y-%m-%d")
        else:
            fecha_s = str(fecha)[:10]

        folder_name = f"{cedula}_{fecha_s}"
        carpeta_caso = f"{self.base_folder}/{folder_name}"

        drive_id = self._get_drive_id()
        if not drive_id:
            logger.error("SP archivar_caso: no drive_id")
            return None

        # 1) mail original (HTML)
        self._upload_to(
            drive_id, f"{carpeta_caso}/mail_original.html",
            mail_original_html, "text/html; charset=utf-8",
        )
        # 2) respuesta (HTML)
        self._upload_to(
            drive_id, f"{carpeta_caso}/respuesta.html",
            respuesta_html, "text/html; charset=utf-8",
        )
        # 3) adjuntos
        for adj in (adjuntos or []):
            nombre = adj.get("nombre_archivo") or "adjunto.bin"
            content = adj.get("content_bytes") or b""
            ctype = adj.get("content_type") or "application/octet-stream"
            if content:
                self._upload_to(drive_id, f"{carpeta_caso}/{nombre}", content, ctype)

        logger.info(
            f"✅ SP archivar_caso: {carpeta_caso} (+{len(adjuntos or [])} adjuntos)"
        )
        return carpeta_caso
