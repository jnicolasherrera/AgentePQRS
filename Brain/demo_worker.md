# demo_worker — flujo end-to-end tenant demo

Worker exclusivo del tenant demo (`11111111-1111-1111-1111-111111111111`) que procesa la bandeja Gmail pública del showcase comercial. A diferencia de `master_worker_outlook.py`, el demo cierra el ciclo **sin intervención humana** para poder mostrar el flujo completo en vivo.

## Contenedor
- Nombre: `pqrs_v2_demo_worker`
- Imagen: build desde `backend/Dockerfile`
- Entry: `python -u demo_worker.py`
- Redeploy aislado: `docker compose up -d --no-deps --build demo_worker`

## Variables de entorno
- `DEMO_GMAIL_USER` — buzón Gmail del demo
- `DEMO_GMAIL_PASSWORD` — App Password Gmail
- `DEMO_RESET_MINUTES` — casos demo más antiguos que N minutos se eliminan automáticamente
- `WORKER_DB_URL`, `REDIS_URL`

## Flujo de 4 pasos

### 1. Ingesta — Gmail IMAP
`fetch_unread_gmail()` lee mensajes UNSEEN de `imap.gmail.com:993`, los marca `\Seen` y retorna lista de dicts `{message_id, subject, sender, body, date}`.

### 2. Clasificación + persistencia
- Dedup por `Message-ID` con Redis SETEX 24h
- `clasificar_hibrido()` (keywords + Claude Haiku) → `tipo`, `prioridad`, `nombre_cliente`, `cedula`, `plazo_dias`
- `INSERT pqrs_casos` con `ON CONFLICT (cliente_id, external_msg_id) DO NOTHING`
- Asignación automática a `DEMO_ABOGADO_ID`
- Genera `numero_radicado = PQRS-{year}-{uuid[:8]}`
- Publica evento de creación a Redis `pqrs_stream_v2`

### 3. Acuse de recibo — Gmail SMTP
`send_acuse_demo(to_email, numero_radicado, tipo, nombre_cliente)` envía HTML con branding FlexPQR (header negro, acento `#9D50FF`, badge de tipo con color dinámico, caja con radicado y plazo). SMTP_SSL contra `smtp.gmail.com:465`.

### 4. Auto-envío respuesta IA — EXCLUSIVO DEMO
- `generar_borrador_para_caso()` produce el borrador (plantilla sectorial o fallback IA) y lo persiste en `pqrs_casos.borrador_respuesta` + `borrador_estado='PENDIENTE'`
- El loop re-lee el borrador desde DB
- Si no está vacío, llama `send_respuesta_ia_demo(to_email, asunto_original, body_md, numero_radicado)`:
  - Renderiza markdown → HTML con `_md_to_html_demo()` (headers, bold, italic, `<br>`)
  - Envuelve en el mismo layout FlexPQR que el acuse
  - Asunto: `Re: {asunto_original} — Radicado {numero_radicado}`
  - Retorna `bool` indicando éxito SMTP
- Si envío OK:
  - `UPDATE pqrs_casos SET borrador_estado='ENVIADO', estado='CERRADO', enviado_at=NOW(), aprobado_at=NOW()` (sin `aprobado_por` porque no hay humano)
  - `INSERT audit_log_respuestas (caso_id, accion='ENVIADO_AUTO_DEMO', metadata={email_destino, asunto, metodo_envio='gmail_smtp', auto_aprobado_por='demo_worker', nota})`
  - Publica a `pqrs_stream_v2` un evento `{event: 'caso_estado_cambiado', id, tenant_id, estado, borrador_estado}` para que el Kanban del frontend actualice en vivo
- Si envío falla: el caso queda en `BORRADOR` y el worker loguea warning (comportamiento degradado seguro)
- Si borrador vacío (edge case): loguea warning, no envía

## Reset automático
Al final de cada ciclo, elimina casos demo más antiguos que `DEMO_RESET_MINUTES` (default 30 min), incluyendo audit_log, comentarios, adjuntos y el caso mismo. Esto mantiene la bandeja demo limpia entre presentaciones.

## Referencias al código
- `backend/demo_worker.py:118-209` — `send_acuse_demo`
- `backend/demo_worker.py:214-223` — `_md_to_html_demo`
- `backend/demo_worker.py:226-295` — `send_respuesta_ia_demo` (helper de envío IA)
- `backend/demo_worker.py:400-452` — hook de auto-envío en el loop principal

## ⚠️ Regla regulatoria
El auto-envío del paso 4 **nunca** debe replicarse a `master_worker_outlook.py` ni a ningún otro tenant productivo. Recovery y demás están sujetos a SLAs de Ley 1755/2015 y régimen SFC que exigen human-in-the-loop vía `POST /api/v2/casos/aprobar-lote`. Ver `Brain/00_DIRECTIVAS_CLAUDE_CODE.md` sección "Comportamiento exclusivo del demo_worker".
