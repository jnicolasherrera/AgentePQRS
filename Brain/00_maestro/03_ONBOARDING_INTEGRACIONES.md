# Onboarding de Integraciones -- FlexPQR

## Integraciones Activas

### 1. Microsoft Outlook (Graph API)
- **Tipo:** Polling periodico + Webhooks push
- **Worker:** `master_worker_outlook.py` -- lee buzones configurados en `config_buzones`
- **Auth:** MSAL ConfidentialClientApplication (client_credentials flow)
- **Webhook endpoint:** `POST /api/webhooks/microsoft-graph` (HMAC-SHA256 validation)
- **Handshake:** `GET /api/webhooks/microsoft-graph?validationToken=...` devuelve el token en text/plain
- **Flujo:** Notificacion -> Dedup Redis (SETNX 7d) -> Kafka publish -> AI Consumer

### 2. Google Workspace (Gmail Push)
- **Webhook endpoint:** `POST /api/webhooks/google-workspace`
- **Auth:** Header `X-Goog-Channel-Token` validado contra `GOOGLE_WEBHOOK_TOKEN`
- **Flujo:** Identico al de Microsoft post-validacion

### 3. Zoho Mail
- **Tipo:** Polling via API REST + envio de respuestas
- **Servicio:** `zoho_engine.py` (ZohoServiceV2)
- **Auth:** OAuth2 refresh_token flow con backoff de 90s ante rate limits
- **Capacidades:** fetch_unread_emails, get_message_detail, get_attachments_list, download_attachment, mark_as_read, send_reply, send_acuse_recibo
- **Adjuntos:** Soporte multipart/form-data para enviar archivos
- **Acuse de recibo:** Email HTML con badge de tipo, numero de radicado, fecha limite

### 4. Anthropic Claude (IA)
- **Modelo:** claude-haiku-4-5-20251001
- **Uso 1 -- Clasificacion:** Tool use con `clasificar_pqr` para tipos legales colombianos
- **Uso 2 -- Borradores:** Generacion de respuestas legales con prompts especializados por tipo
- **Retry:** Exponencial ante RateLimitError (5 intentos maximo)
- **Fallback:** Si Claude falla, se usa el resultado del scoring engine de keywords

### 5. MinIO (S3-compatible Storage)
- **Bucket:** `pqrs-vault`
- **Endpoint:** `minio:9000` (interno Docker) / `localhost:9020` (host)
- **Claim Check:** Adjuntos >1MB van a MinIO, solo URI en el mensaje Kafka
- **Presigned URLs:** Para descarga temporal de adjuntos (2h TTL)

### 6. SharePoint (Microsoft Graph)
- **Servicio:** `sharepoint_engine.py` (SharePointEngineV2)
- **Auth:** MSAL client_credentials
- **Estructura:** `{base_folder}/COLOMBIA/{YYYY-MM}/{caso_suffix}/{filename}`
- **Uso:** Storage secundario para archivos de casos

### 7. Redis
- **PubSub:** Canal `pqrs.events.{tenant_id}` para notificaciones SSE en tiempo real
- **Dedup:** `webhook:msgid:{id}` con TTL 7 dias para idempotencia de webhooks
- **Persistencia:** RDB cada 60 cambios, protegido con password

## Configuracion de Buzones

La tabla `config_buzones` permite agregar buzones de email por tenant sin cambiar codigo:

| Campo               | Descripcion                                       |
|---------------------|---------------------------------------------------|
| email_buzon         | Direccion del buzon a monitorear                  |
| proveedor           | OUTLOOK o ZOHO                                    |
| azure_client_id     | App Registration de Azure (si es propio)          |
| azure_client_secret | Secret de la App Registration                     |
| azure_tenant_id     | Tenant ID de Azure AD                             |
| zoho_refresh_token  | Token de refresco para Zoho Mail API              |
| zoho_account_id     | ID de cuenta Zoho                                 |
| is_active           | Activar/desactivar sin borrar                     |
