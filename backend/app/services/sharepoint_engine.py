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
