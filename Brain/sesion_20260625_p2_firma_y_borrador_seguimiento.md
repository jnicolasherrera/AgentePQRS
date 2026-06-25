# Sesión 2026-06-25 (parte 2) — Firma por tenant + borrador en seguimientos

Continuación de la sesión del fix de envío FF. Dos fixes nuevos a partir de feedback del usuario sobre el test de Micaela.

## Problema B — Firma incorrecta (RESUELTO + desplegado)
**Síntoma:** los correos de FlexFintech salían con la imagen de firma de Abogados Recovery/Arcasas.
**Causa:** la firma era una imagen única global (`app/static/firma_correo.jpeg`, CID `firma_arc`) hardcodeada en 3 puntos de envío (`zoho_engine._firma_html`, `casos.py._firma_html`/`_firma_bytes` para Graph y fallback SMTP). Se aplicaba a TODOS los tenants.
**Fix (PR #22, rama `fix/firma-por-tenant`, parte de PR #20):**
- Nuevo `backend/app/services/firma_engine.py`: `firma_html_cid()` (MIME/Graph), `firma_html_datauri()` (Zoho), `usa_imagen()`, `firma_bytes()`. FlexFintech (`f7e8d9c0-b1a2-3456-7890-123456abcdef` o email `*flexfintech.com`) → firma de TEXTO ("Saludos Cordiales / **Flexfintech**", sin imagen). Resto → imagen institucional.
- `zoho_engine.send_reply` usa `firma_html_datauri(from_address)`. `casos.py` (rama Graph + fallback SMTP) usa `firma_html_cid(buzon)` + adjunta imagen solo si `usa_imagen(buzon)`.
- Validado: envío real por Graph con firma de texto; usuario aprobó cómo se ve.
- Desplegado quirúrgico a prod (backups `casos.py.bak.firma.20260625`, `zoho_engine.py.bak.20260625`, rebuild backend_v2, HTTP 200).

## Problema A — Seguimiento no generaba respuesta al nuevo mail (RESUELTO + desplegado)
**Síntoma:** Micaela contestó un caso ya respondido; el sistema registró el comentario y reabrió el caso, pero NO generó un borrador nuevo → el operador no tenía respuesta lista para el nuevo mensaje ("no tomó el nuevo ingreso").
**Fix (suma a PR #21, rama `fix/seguimiento-loop-infinito`):** en `_registrar_seguimiento` (master_worker_outlook.py), dentro del `if not ya_existe` (solo seguimiento nuevo), tras insertar el comentario se llama a `generar_borrador_para_caso(conn, c_id, caso_id, subject, body[:1000], tipo_caso=..., radicado=..., email_origen=..., tipo_workflow=...)` con el contenido del seguimiento → deja `borrador_estado='PENDIENTE'`. Best-effort (try/except). Los SELECT del caso se ampliaron para traer `tipo_caso, tipo_workflow, email_origen, numero_radicado`.
- Validado en prod sobre el caso de Micaela (`f03640cb`): `borrador_estado` pasó de ENVIADO → PENDIENTE con respuesta nueva generada.
- Desplegado quirúrgico a prod (backup `master_worker_outlook.py.bak.borrador.20260625`, rebuild master_worker_v2, healthy).

## Estado de ramas (OJO — no mergeadas, prod va por delante de main en algunos archivos)
- **PR #20** `fix/ff-envio-outlook-graph`: envío FF por Graph. Base de #22.
- **PR #21** `fix/seguimiento-loop-infinito`: loop infinito + borrador-en-seguimiento (2 commits). Sale de main.
- **PR #22** `fix/firma-por-tenant`: firma por tenant. Sale de #20.
- Los 3 están **desplegados quirúrgicamente en prod** pero NO mergeados a main. Al mergear: cuidado con el orden (#20 → #22) y con que prod tiene variantes propias de algunos archivos (master_worker no tiene `_download_attachments_inline` de main).

## Gotcha reforzado
Deploy quirúrgico de archivos que en prod van detrás de main: NO copiar el archivo de la rama; descargar el de prod, aplicarle SOLO los parches con la tool `patch`, verificar `diff` (ignorando CR) = solo tus bloques, re-subir. Se hizo así con `master_worker_outlook.py` (3 veces ya) y `casos.py`.
