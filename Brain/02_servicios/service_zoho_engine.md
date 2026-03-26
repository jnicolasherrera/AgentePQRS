---
tags:
  - brain/service
---

# Service: Zoho Engine

## Archivo
`backend/app/services/zoho_engine.py`

## Descripcion
Cliente para Zoho Mail API. Maneja autenticacion OAuth2, lectura de emails, descarga de adjuntos, envio de respuestas con HTML + firma, y acuses de recibo.

## Clase: ZohoServiceV2

### Autenticacion
- OAuth2 refresh_token flow
- Token se renueva automaticamente cuando expira
- **Backoff de rate limit:** Si Zoho responde "too many requests", se activa un backoff de 90s compartido entre instancias (por refresh_token)

### Metodos

#### fetch_unread_emails(folder_id)
- Obtiene hasta 10 emails no leidos del buzón
- Si folder_id es "ZOHO_INBOX", resuelve el ID numerico automaticamente

#### get_message_detail(message_id, folder_id)
- Obtiene el contenido completo de un email

#### get_attachments_list(message_id, folder_id)
- Lista adjuntos del email: attachmentId, attachmentName, contentType, attachmentSize

#### download_attachment(message_id, attachment_id, folder_id)
- Descarga los bytes de un adjunto especifico

#### mark_as_read(message_id)
- Marca un email como leido para evitar reprocesamiento

#### send_reply(to_email, subject, body, from_address, adjuntos)
- Envia email de respuesta con HTML formateado + firma institucional
- Soporta adjuntos via multipart/form-data
- Convierte markdown basico a HTML (bold, italic, headers)
- Incluye firma como imagen base64 embebida

#### send_acuse_recibo(to_email, from_address, numero_radicado, ...)
- Envia acuse de recibo HTML al ciudadano
- Template con header negro, badge de color por tipo, cuadro de radicado
- Tonos personalizados por tipo (TUTELA=rojo, PETICION=azul, etc.)

## Firma de Email
- Archivo: `backend/app/static/firma_correo.jpeg`
- Se convierte a base64 e incrusta como `<img>` en el HTML
- Si el archivo no existe, se omite silenciosamente

## Markdown a HTML
Funcion `_md_to_html()`:
- `### heading` -> `<h4>`
- `## heading` -> `<h3>`
- `# heading` -> `<h2>`
- `**bold**` -> `<strong>`
- `*italic*` -> `<em>`
- `\n` -> `<br>`
