# Sprint Bugs Paola — 2026-04-27

Sprint corto (~3-4 horas) para resolver 4 bugs reportados por Paola Lombana (cliente ARC, prod) el 21-abril que se acumularon durante el sprint Tutelas.

## Contexto

- Sprint Tutelas S1+S2+S3 cerrado en staging (HEAD develop pre-sprint: `106b494`).
- Incidente prod hoy a las ~16:46 UTC: master_worker pool dead, resuelto con docker restart + bridge cron `check_ingestion.sh`. Ver `Brain/incidents/INC-2026-04-27_master_worker_pool_dead.md`.
- 4 bugs reportados por Paola, validados con ella hoy.

## Decisiones validadas con Paola

| Bug | Decisión |
|---|---|
| P1 — Adjuntos del abogado no llegan | Mantener filtro `es_reply=TRUE`. Sólo arreglar la subida (frontend bug). NO reenviar adjuntos del peticionante. |
| P2 — Hay que guardar borrador antes de aprobar | Auto-save sin botón explícito. |
| P3 — Imagen institucional no llega | Mantener imagen institucional ARC (no firma personal por abogado). Arreglar render. |
| P4 — Aviso "Generado por IA" | Remover globalmente. |

## Causa raíz por bug

### P1 — `Content-Type: application/json` global pisa multipart upload

`frontend/src/lib/api.ts:5` setea `Content-Type: application/json` en el cliente axios global. Cuando se hace `api.post(url, formData)` para subir adjuntos, axios envía el body como `multipart/form-data` pero mantiene el header global como `application/json`. FastAPI no puede parsear el body con ese mismatch → **422 Unprocessable Entity**.

**Evidencia (prod ARC, 14 días):**
- Distribución `pqrs_adjuntos`: 152 con `es_reply=FALSE` (entrante) vs **1 con `es_reply=TRUE`** (subido por abogado, del 2026-03-27).
- Logs backend: `POST /reply-adjuntos HTTP/1.0 422 Unprocessable Entity` recurrente.
- Único `es_reply=TRUE` es del 2026-03-27, anterior al deploy que introdujo el bug.

**Sub-bug encontrado**: nginx no tiene `client_max_body_size` configurado → default 1 MB → archivos grandes bloqueados antes de llegar al backend.

**Sub-bug encontrado**: límite hardcoded `10 * 1024 * 1024` en `casos.py:431` también es restrictivo para PDFs típicos de respuesta legal con anexos.

### P2 — Texto editado no llega al envío

Backend `aprobar-lote` lee `borrador_respuesta` desde DB. Frontend tenía botón "Guardar" explícito; si el usuario olvidaba apretar, la edición se perdía.

**Bug expandido durante diagnóstico:** existen DOS entry points distintos en frontend que disparan aprobación, **NINGUNO** persistía antes de aprobar:
1. `frontend/src/components/ui/firma-modal.tsx` (modal explícito).
2. `frontend/src/components/ui/caso-detail-overlay.tsx:handleSendResponse` línea 132 (prompt nativo).

Registrado como **DT-37** (UX a unificar).

### P3 — Imagen institucional no renderiza en Outlook

`backend/app/services/zoho_engine.py:27-35` y `backend/app/api/routes/casos.py:35-42` cargaban la imagen como `<img src="data:image/jpeg;base64,...">` inline. **Outlook desktop frecuentemente bloquea data URIs en correos HTML.**

**Limitación encontrada:** Zoho REST API `POST /messages` no permite especificar imágenes inline con CID directamente en la request. Requiere flujo de 2 pasos (uploadAttachment con `isInline=true` + referenciar `attachmentId`). Out of scope para este sprint.

Registrado como **DT-38** para sprint dedicado.

### P4 — Disclaimer IA en respuesta

`backend/app/services/plantilla_engine.py:82` concatenaba `AVISO_GENERICA` al texto retornado por `generar_borrador_con_ia`. Solo se aplicaba al fallback IA (cuando no hay plantilla específica). Pero ARC no tiene plantillas `GENERICO_*` para los tipos básicos → el fallback se dispara frecuentemente → Paola veía el aviso.

## Implementación

### P1 — Fix subida adjuntos abogado al borrador

| Archivo | Cambio |
|---|---|
| `frontend/src/components/ui/caso-detail-overlay.tsx:161` | Agregado `headers: { "Content-Type": "multipart/form-data" }` al `api.post` para `/reply-adjuntos` |
| `backend/app/api/routes/casos.py:431` | Límite tamaño 10 MB → 25 MB |
| `nginx/nginx.conf` | `client_max_body_size 25M;` agregado en server blocks 443 (`_` y `app.flexpqr.com`) |

### P2 — Auto-save con debounce

| Archivo | Cambio |
|---|---|
| `frontend/src/components/ui/borrador-drawer.tsx` | `useEffect` con `setTimeout(2s)` que llama `PUT /borrador` cuando texto cambia. Indicador visual "Guardando..." / "✓ Guardado" |
| `frontend/src/components/ui/caso-detail-overlay.tsx` | Mismo patrón en el textarea del overlay. Indicador en header del panel "Borrador de Respuesta" |
| `backend/app/api/routes/casos.py` `editar_borrador` | Early return `{"ok": True, "unchanged": True}` si `body.texto == original_ai`. Evita inflar `audit_log_respuestas` y `borrador_feedback` con guardados auto-save de texto idéntico |

### P3 — Firma institucional como CID attachment (SMTP path)

| Archivo | Cambio |
|---|---|
| `backend/app/api/routes/casos.py` | Nuevos helpers `_firma_path()`, `_firma_bytes()`, constante `_FIRMA_CID = "firma_arc"` |
| `backend/app/api/routes/casos.py:_firma_html()` | Retorna `<img src="cid:firma_arc">` en lugar de inline base64 |
| `backend/app/api/routes/casos.py:_send_via_smtp_fallback()` | Reescrito como `MIMEMultipart('related')` + `MIMEImage` con `Content-ID: <firma_arc>` y `Content-Disposition: inline`. Si no hay firma, fallback a `multipart/alternative` clásico |

**Limitación reconocida:** path Zoho REST API (primario) sigue con inline base64 como antes. Ver DT-38.

### P4 — Remover AVISO_GENERICA

| Archivo | Cambio |
|---|---|
| `backend/app/services/plantilla_engine.py:82` | `return texto + AVISO_GENERICA` → `return texto`. Constante `AVISO_GENERICA` se mantiene definida (sin uso) por si se quiere configurable por tenant en el futuro |

## Tests

`backend/tests/test_sprint_paola_2026_04_27.py` (7 tests, 1.60s, sin DB ni red):

| Test | Cobertura |
|---|---|
| `test_p1_upload_24mb_passes_size_check` | UploadFile 24 MB → 200 OK + INSERT |
| `test_p1_upload_26mb_rejects_with_400` | UploadFile 26 MB → HTTPException 400 |
| `test_p2_put_borrador_unchanged_skips_audit` | PUT con texto idéntico → no audit insert |
| `test_p2_put_borrador_changed_inserts_audit` | PUT con texto distinto → UPDATE + audit + feedback |
| `test_p3_smtp_fallback_genera_multipart_related_con_cid` | SMTP fallback genera MIME `multipart/related` con `Content-ID: <firma_arc>` y HTML referencia `cid:firma_arc` |
| `test_p3_smtp_fallback_sin_firma_usa_alternative` | Si firma no existe → fallback a `multipart/alternative` |
| `test_p4_borrador_ia_sin_aviso_generica` | `generar_borrador_con_ia` retorna sólo texto Claude, sin disclaimer |

Stubeo `app.services.storage_engine` en `sys.modules` antes de imports (workaround DT-29).

## DTs registradas

- **DT-37** — Frontend con 2 entry points distintos para aprobar borrador (UX a unificar).
- **DT-38** — Firma institucional inline base64 vía Zoho REST API no garantiza render en Outlook (requiere 2-step API flow).

## Smoke E2E staging

Pendiente al momento de redactar este documento. Plan:
1. Login como abogado test.
2. Editar borrador en caso de prueba — verificar "Guardando..." → "✓ Guardado" tras 2s.
3. Subir PDF de 5 MB al borrador — verificar HTTP 200 + UI muestra el archivo.
4. Aprobar caso → email a dirección controlada de testing.
5. Verificar en cliente: texto editado correcto + adjunto PDF + imagen institucional renderiza (path SMTP) + sin aviso "Generado por IA".

## Deploy a prod

Pendiente. Pre-check obligatorio:
- `ssh flexpqr-prod "cat /home/ubuntu/logs/check_ingestion.log 2>/dev/null | tail -20"` → si tiene alertas últimas 4h, STOP.
- Master_worker estable (Up sin reiniciar por error).

Procedimiento:
- `git push origin develop`
- `ssh flexpqr-prod` + `cd ~/PQRS_V2` + `git pull`
- `docker exec pqrs_v2_frontend npm run build`
- `docker compose restart` (NO build, según runbook)
- Para cambios en nginx config: `docker exec pqrs_v2_nginx nginx -s reload`

## Estado al cierre

- Tests: ✅ 7/7 verdes en 1.60s.
- Working tree: pendiente commits.
- Push origin: pendiente.
- Deploy staging: pendiente.
- Smoke staging: pendiente.
- Deploy prod: pendiente (requiere autorización Nico).
- Validación con Paola: pendiente (post-deploy prod).
