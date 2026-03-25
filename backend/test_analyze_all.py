import asyncio
import asyncpg
from app.services.zoho_engine import ZohoServiceV2
from app.services.clasificador import clasificar_texto
import msal
import requests
import pandas as pd
from datetime import datetime

# Configuración (Reutilizando tus credenciales)
ZOHO_CLIENT_ID = "1000.TKA5AEC621AB1NISPL1YEN08VKRHAC"
ZOHO_SECRET = "568f75dac62845e5d8e4caff0deef488c2896803cd"
ZOHO_REFRESH = "1000.1b69662a184a373bc3171bb906733499.1c2be417d333b565605751d1e126fc5c"
ZOHO_ACCOUNT = "2429327000000008002"

AZURE_CLIENT_ID = "b2f0910b-d300-4a55-963a-59aeb5acabf6"
AZURE_SECRET = "os.environ.get("AZURE_CLIENT_SECRET")"
AZURE_TENANT = "f765bba0-7d35-4248-9711-5770de77ab2b"

async def analyze_inboxes():
    print("🕵️  [TEST] Iniciando Análisis de Buzones (Leídos y No Leídos)...")
    
    # 1. ANALIZAR ZOHO (Abogados Recovery)
    print("\n📦 --- BUZÓN ZOHO: pqrs@arcsas.com.co ---")
    try:
        zoho = ZohoServiceV2(ZOHO_CLIENT_ID, ZOHO_SECRET, ZOHO_REFRESH, ZOHO_ACCOUNT)
        # Hack para traer los últimos (sin filtro de unread para el test)
        acc_id = zoho._get_account_id()
        endpoint = f"/accounts/{acc_id}/messages/view"
        params = {"limit": 5} # Traemos los últimos 5 para no saturar
        res = zoho._make_request(endpoint, params=params)
        
        emails = res.get("data", [])
        if not emails:
            print("❌ No se encontraron correos en Zoho.")
        else:
            for m in emails:
                asunto = m.get("subject", "Sin Asunto")
                remitente = m.get("fromAddress", "Desconocido")
                full_m = zoho.get_message_detail(m["messageId"])
                cuerpo = full_m.get("content", "") if full_m else ""
                
                # Análisis
                ana = clasificar_texto(asunto, cuerpo, remitente)
                print(f"📧 [{remitente}] -> {asunto[:50]}...")
                print(f"   └─ 🤖 Clasificación IA: {ana.tipo.value} | Prioridad: {ana.prioridad.value}")
    except Exception as e:
        print(f"💥 Error Zoho: {e}")

    # 2. ANALIZAR OUTLOOK (EmpresaDemo)
    print("\nⓂ️  --- BUZÓN OUTLOOK: clientes@empresademo.com ---")
    try:
        authority = f"https://login.microsoftonline.com/{AZURE_TENANT}"
        app = msal.ConfidentialClientApplication(AZURE_CLIENT_ID, authority=authority, client_credential=AZURE_SECRET)
        token = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])["access_token"]
        
        folder_id = "AAMkADUxOGI3MjNmLTRmYjYtNDRlMC04ZjdkLTI5NWI5NTVlMTYwYQAuAAAAAAAfifyJAfEXQb8nwih5Ou3GAQA_6g6Es0c0QJlfW-ufh7p9AADpbc9rAAA="
        url = f"https://graph.microsoft.com/v1.0/users/clientes@empresademo.com/mailFolders/{folder_id}/messages?$top=5"
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
        
        out_emails = resp.json().get("value", [])
        for m in out_emails:
            asunto = m.get("subject", "Sin Asunto")
            remitente = m.get("from", {}).get("emailAddress", {}).get("address", "Desconocido")
            cuerpo = m.get("body", {}).get("content", "")
            
            # Análisis
            ana = clasificar_texto(asunto, cuerpo, remitente)
            print(f"📧 [{remitente}] -> {asunto[:50]}...")
            print(f"   └─ 🤖 Clasificación IA: {ana.tipo.value} | Prioridad: {ana.prioridad.value}")
            
    except Exception as e:
        print(f"💥 Error Outlook: {e}")

if __name__ == "__main__":
    asyncio.run(analyze_inboxes())
