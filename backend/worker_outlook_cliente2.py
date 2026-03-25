import asyncio
import json
import msal
import requests
import asyncpg
import redis.asyncio as redis
import pandas as pd
from datetime import datetime, timedelta

# Configuración de Entorno V2 y Credenciales de V1 Original
AZURE_CLIENT_ID = "b2f0910b-d300-4a55-963a-59aeb5acabf6"
AZURE_CLIENT_SECRET = "os.environ.get("AZURE_CLIENT_SECRET")"
AZURE_TENANT_ID = "f765bba0-7d35-4248-9711-5770de77ab2b"
AZURE_TARGET_MAILBOX = "clientes@empresademo.com"

# Infraestructura V2
from app.services.ai_engine import clasificar_hibrido
from app.services.storage_engine import upload_file
import base64

# Infraestructura V2
DATABASE_URL = "postgresql://pqrs_admin:pg_password@postgres_v2:5432/pqrs_v2"
REDIS_URL = "redis://redis_v2:6379"
TENANT_CLIENTE2 = "d1cf5e93-4121-4124-abf7-0f8dc1b070a9" # ID de Cliente 2

# ... (En un caso real, aquí cambiaríamos las credenciales de Outlook o la carpeta de búsqueda)
FOLDER_ID_CLIENTE2 = "AAMkADUxOGI3MjNmLTRmYjYtNDRlMC04ZjdkLTI5NWI5NTVlMTYwYQAuAAAAAAAfifyJAfEXQb8nwih5Ou3GAQA_6g6Es0c0QJlfW-ufh7p9AADpbc9rAAA=" # Mock

class OutlookListenerV2:
    def __init__(self):
        self.access_token = None
        self.token_expiry = None

    def _get_token(self):
        if self.access_token and self.token_expiry and datetime.utcnow() < self.token_expiry:
            return self.access_token

        authority = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}"
        app = msal.ConfidentialClientApplication(
            AZURE_CLIENT_ID, authority=authority, client_credential=AZURE_CLIENT_SECRET
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in result:
            raise Exception("No se pudo autenticar con Graph API: " + result.get("error_description", "Error"))
        
        self.access_token = result["access_token"]
        self.token_expiry = datetime.utcnow() + timedelta(minutes=50)
        return self.access_token

    def _make_request(self, endpoint):
        headers = {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }
        url = f"https://graph.microsoft.com/v1.0/users/{AZURE_TARGET_MAILBOX}{endpoint}"
        resp = requests.get(url, headers=headers)
        if resp.status_code >= 400:
            print("Error Microsoft Graph:", resp.text)
            return []
        return resp.json().get("value", [])

    def fetch_unread_emails_colombia(self):
        # Leemos correos NO LEÍDOS directamente desde la carpeta "03. Empresa Colombia"
        # y limitamos a 5
        folder_id = "AAMkADUxOGI3MjNmLTRmYjYtNDRlMC04ZjdkLTI5NWI5NTVlMTYwYQAuAAAAAAAfifyJAfEXQb8nwih5Ou3GAQA_6g6Es0c0QJlfW-ufh7p9AADpbc9rAAA="
        endpoint = f"/mailFolders/{FOLDER_ID_CLIENTE2}/messages?$top=5&$filter=isRead eq false&$orderby=receivedDateTime desc"
        messages = self._make_request(endpoint)
        
        parsed_emails = []
        for msg in messages:
            sender = msg.get("from", {}).get("emailAddress", {}).get("address", "anonimo@correo.co")
            subject = msg.get("subject", "Sin asunto")
            
            # Estamos en 03. Empresa Colombia, todo es PQR válido acá
            parsed_emails.append({
                "id_outlook": msg["id"],
                "sender": sender,
                "subject": subject,
                "body": msg.get("body", {}).get("content", "Body Error"),
                "date": msg.get("receivedDateTime")
            })
        return parsed_emails

    def get_attachments_metadata(self, email_id):
        endpoint = f"/messages/{email_id}/attachments"
        return self._make_request(endpoint)

    def download_attachment(self, email_id, attachment_id):
        headers = {"Authorization": f"Bearer {self._get_token()}"}
        url = f"https://graph.microsoft.com/v1.0/users/{AZURE_TARGET_MAILBOX}/messages/{email_id}/attachments/{attachment_id}"
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            return base64.b64decode(data["contentBytes"])
        return None

    def mark_as_read(self, email_id):
        headers = {"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json"}
        url = f"https://graph.microsoft.com/v1.0/users/{AZURE_TARGET_MAILBOX}/messages/{email_id}"
        requests.patch(url, headers=headers, json={"isRead": True})

async def email_worker():
    print("🚀 [WORKER] Iniciando Listener de Microsoft Graph (Outlook Real)...")
    listener = OutlookListenerV2()
    r = redis.from_url(REDIS_URL, decode_responses=True)
    conn = await asyncpg.connect(DATABASE_URL)
    
    query_insert = """
    INSERT INTO pqrs_casos (cliente_id, email_origen, asunto, cuerpo, estado, nivel_prioridad, fecha_recibido, tipo_caso, fecha_vencimiento)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id
    """

    while True:
        try:
            print("📡 Buscando nuevos correos en clientes@empresademo.com...")
            new_emails = listener.fetch_unread_emails_colombia()
            
            for email in new_emails:
                print(f"📥 PROCESANDO: {email['subject']}")
                
                # USAR EL NUEVO CLASIFICADOR MIGRADO DE V1
                resultado = await clasificar_hibrido(email['subject'], email['body'], email['sender'])
                
                fecha = datetime.fromisoformat(email['date'].replace("Z", "+00:00")).replace(tzinfo=None)
                
                # El clasificador ya nos da el plazo en días basado en las reglas de negocio
                vencimiento = (pd.Timestamp(fecha) + pd.offsets.CustomBusinessDay(n=resultado.plazo_dias)).to_pydatetime()
                
                # Inserción en Postgres V2
                db_id = await conn.fetchval(
                    query_insert, 
                    TENANT_CLIENTE2, 
                    email['sender'], 
                    email['subject'], 
                    email['body'][:1000],
                    'ABIERTO', 
                    resultado.prioridad.value, 
                    fecha, 
                    resultado.tipo.value, 
                    vencimiento
                )
                
                # Notificar al Front vía Redis (SSE lo replicará)
                notificacion_redis = {
                    "id": str(db_id),
                    "subject": email['subject'],
                    "client": email['sender'],
                    "severity": resultado.prioridad.value,
                    "status": "Abierto",
                    "source": "Outlook Nativo",
                    "date": fecha.strftime("%d/%m/%Y %H:%M"),
                    "tipo": resultado.tipo.value,
                    "vencimiento": vencimiento.isoformat(),
                    "confianza": resultado.confianza,
                    "es_juzgado": resultado.es_juzgado
                }
                await r.publish("pqrs_stream_v2", json.dumps(notificacion_redis))
                print(f"✅ CASO CLASIFICADO ({resultado.tipo.value}) E INYECTADO: {db_id}")
                
                # 4. PROCESAR ADJUNTOS (LA BÓVEDA)
                attachments = listener.get_attachments_metadata(email['id_outlook'])
                for att in attachments:
                    if att.get("@odata.type") == "#microsoft.graph.fileAttachment":
                        print(f"📎 Descargando adjunto: {att['name']}")
                        content = listener.download_attachment(email['id_outlook'], att['id'])
                        if content:
                            # Subir a MinIO
                            storage_path = await upload_file(
                                content, 
                                f"{db_id}_{att['name']}", 
                                folder=f"casos/{db_id}"
                            )
                            if storage_path:
                                # Registrar en DB
                                await conn.execute(
                                    "INSERT INTO pqrs_adjuntos (caso_id, cliente_id, nombre_archivo, storage_path, content_type, tamano_bytes) VALUES ($1, $2, $3, $4, $5, $6)",
                                    db_id, TENANT_CLIENTE2, att['name'], storage_path, att['contentType'], att['size']
                                )
                                print(f"✅ Adjunto guardado en Bóveda: {att['name']}")

                listener.mark_as_read(email['id_outlook'])
                
        except Exception as e:
            print("[ERROR WORKER]", str(e))
            
        print("💤 Esperando 10 segundos para el proximo escaneo...")
        await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(email_worker())
