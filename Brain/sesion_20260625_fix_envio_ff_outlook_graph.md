# Sesión 2026-06-25 — Fix envío FlexFintech: remitente democlasificador → clientes@flexfintech.com

## Problema reportado
Las respuestas a casos de **FlexFintech** salían desde `democlasificador@gmail.com`
en vez de `clientes@flexfintech.com`. El usuario observó (correctamente) que FF
tiene sus cuentas en **Microsoft 365**, no en Zoho.

## Diagnóstico (validado contra prod)
1. **Config buzones** (`config_buzones`, prod):
   - FlexFintech → `proveedor=OUTLOOK`, `azure_client_id/tenant/secret` completos, **sin Zoho** (`zoho_refresh_token` NULL).
   - Abogados Recovery (ARC) → `proveedor=ZOHO` (sin cambios, no afectado).
2. **Bug en el endpoint de envío** (`backend/app/api/routes/casos.py`, función `enviar-lote`):
   - La query del buzón filtraba `WHERE proveedor='ZOHO'` → para FF devolvía `None`
     → `zoho=None` → caía **SIEMPRE** al `_send_via_smtp_fallback`, que usa
     `SMTP_FALLBACK_USER` o cae a `DEMO_GMAIL_USER` = `democlasificador@gmail.com`.
   - **No existía ningún camino de envío por Graph/Outlook** (la ingesta sí usa Graph; el envío no).
3. **Evidencia `audit_log_respuestas`**: 77 envíos por `smtp_fallback` vs 46 por `zoho`.
4. **Hallazgo Azure**: la App de Azure de FF (`client_id` empieza `b2f0910b…`) tenía SOLO
   permisos de lectura (`Mail.Read, Mail.ReadBasic.All, User.Read.All, Sites/Files.ReadWrite.All, Calendars.ReadWrite`).
   **NO tenía `Mail.Send`** → `sendMail` daba **403 ErrorAccessDenied**. Por eso desde
   el día uno FF podía leer pero nunca enviar.

## Solución implementada (PR #20, rama `fix/ff-envio-outlook-graph`)
- **Nuevo** `backend/app/services/outlook_send_engine.py` → clase `OutlookSenderV2`:
  envío vía Graph `POST /users/{buzon}/sendMail`, firma institucional inline (CID,
  `isInline:true` + `contentId`) + adjuntos (`fileAttachment` base64), token MSAL
  `acquire_token_for_client` con credenciales por-tenant. Devuelve True en 202.
- **`casos.py`**:
  - Query del buzón: trae el buzón activo del tenant SIN filtrar proveedor
    (`ORDER BY CASE WHEN proveedor='OUTLOOK' THEN 0 ELSE 1 END`), trae `proveedor` y `azure_tenant_id`.
  - Instancia `zoho` solo si `proveedor=='ZOHO'`; `outlook_sender` solo si `proveedor=='OUTLOOK'`.
  - Enrutado de envío: `OUTLOOK→Graph`, `ZOHO→Zoho`, fallback SMTP solo si el primario
    falla, ahora pasándole `from_address=buzon['email_buzon']`.
  - `_send_via_smtp_fallback` acepta `from_address` y lo usa en el header `From`.
  - `audit_log` registra `metodo_envio='outlook_graph'`.

## Acción de infra (HECHA)
- Permiso de aplicación **`Mail.Send`** + **admin consent** agregado en la App de Azure de FF
  (lo hizo el usuario en portal.azure.com). Verificado: token incluye `Mail.Send` y
  `sendMail` → **202** (correo de prueba enviado a clientes@flexfintech.com).

## Deploy quirúrgico a prod (HECHO — regla de oro respetada)
- Prod: `ubuntu@18.228.54.9`, `/home/ubuntu/PQRS_V2/`. Servicios compose: `backend_v2`, `postgres_v2`, etc.
- Backup: `backend/app/api/routes/casos.py.bak.20260625`.
- Archivos copiados con **CRLF preservado** (prod usa CRLF; el archivo nuevo se convirtió a CRLF con `sed -i 's/$/\r/'`).
- `docker compose build backend_v2` + `docker compose up -d backend_v2`.
- Verificado: HTTP 200, `/docs` 200, `Application startup complete`, `outlook_graph` presente en el código del contenedor.
- Kafka "no disponible → arranca sin producer" = comportamiento vestigial esperado, NO regresión.

## Pendiente
- **Prueba end-to-end**: la dispara un usuario desde la app (login + password). Al enviar un caso FF,
  confirmar en `audit_log_respuestas` que queda `metodo_envio='outlook_graph'` y que el correo
  llega desde `clientes@flexfintech.com`.
- **Opcional (seguridad)**: `Mail.Send` como Application Permission deja enviar como CUALQUIER buzón
  del tenant. Si se quiere acotar solo a `clientes@flexfintech.com`, aplicar Application Access Policy
  en Exchange Online (PowerShell `New-ApplicationAccessPolicy`).
- Mergear PR #20 a main cuando la prueba e2e confirme.

## Gotchas descubiertos (para futuras sesiones)
- DB prod: tabla de tenants es `clientes_tenant` (NO `clientes`). User admin DB = `pqrs_admin` (bypassa RLS);
  el backend usa `pqrs_backend` con RLS activo → queries sin tenant fijado devuelven None.
- Acceso SSH prod: clave `hermes-vps@flexfintech` autorizada en `ubuntu@18.228.54.9`.
  Usar `ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519`. NO hay SSM (rol AWS sin permiso).
- Servicios compose tienen sufijo `_v2` (backend_v2, postgres_v2) aunque los contenedores se llamen `pqrs_v2_*`.
- `cut -d` NO acepta delimitadores multibyte (ej. `§`); usar `|` o tab.
