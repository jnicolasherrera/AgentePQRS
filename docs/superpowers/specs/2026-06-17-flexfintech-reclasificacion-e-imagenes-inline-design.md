# Spec — FlexFintech: reclasificación PQRS⇄AC + imágenes inline del cuerpo

**Fecha:** 2026-06-17
**Tenant afectado:** FlexFintech (`f7e8d9c0-b1a2-3456-7890-123456abcdef`) — único con universo dual AC. Proveedor de buzón: **Outlook/Graph**.
**Origen:** pedidos de Micaela (FF) por chat. Tres incidencias → dos cambios independientes.

## Contexto y diagnóstico

El sprint FF dejó un "universo dual" `tipo_workflow ∈ {PQRS, ATENCION_CLIENTE}` que se setea **una sola vez al ingerir** el correo (`master_worker_outlook.py`, gate FF en línea 535) y que **no se puede cambiar después** (no existe endpoint). El frontend pinta la bandeja filtrando por `tipo_workflow`.

Hallazgos verificados en código:

1. **Imágenes inline no se ven** — el cuerpo HTML se guarda tal cual en `pqrs_casos.cuerpo` (worker línea 580-584) y el frontend lo renderiza en un `<iframe srcDoc={cuerpo}>` (`caso-detail-overlay.tsx`). El worker sólo baja adjuntos clásicos `fileAttachment` (`_download_attachments_inline`, línea 273-308); las imágenes inline llegan como `<img src="cid:...">` y el `cid:` no resuelve fuera del MIME → imagen rota.
2. **"No PQR" no va a Atención al Cliente** — el botón "No PQRS" hace `POST /admin/casos/{id}/feedback {es_pqrs:false}` (admin.py:212), que marca `es_pqrs=false` (señal de aprendizaje) y manda el caso a un filtro de **descarte/borrado** (`DELETE /no-pqrs`, admin.py:253). **No toca `tipo_workflow`.** Por eso nunca aparece en AC.
3. **No hay "Sí es PQR" desde AC** — espejo del punto 2: no existe acción ni endpoint para mover `ATENCION_CLIENTE → PQRS`.

## Decisiones tomadas

- **"No es PQR"** pasa a **mover el caso a Atención al Cliente** (`tipo_workflow=ATENCION_CLIENTE`), manteniendo `es_pqrs=false` como señal de aprendizaje. El descarte/spam real queda como acción separada (futuro, fuera de alcance).
- **Reclasificar "solo mueve"**: al levantar un caso de AC→PQRS no se re-genera borrador ni se toca `tipo_caso`; el analista regenera con el botón existente si hace falta.
- **Imágenes inline → base64 embebido** en el HTML guardado. Renderiza seguro en el `<iframe>` sin depender de que MinIO sea accesible desde el browser ni de auth en `<img>`.
- **Outlook únicamente** (FF usa Graph). Zoho inline fuera de alcance.

---

## Cambio B — Reclasificación bidireccional PQRS ⇄ ATENCION_CLIENTE

*(cubre pedidos 2 y 3)*

### Backend — `backend/app/api/routes/admin.py`

Nuevo endpoint `PATCH /admin/casos/{caso_id}/workflow`, admin/super_admin:

- **Body:** `{ "tipo_workflow": "PQRS" | "ATENCION_CLIENTE" }`.
- **Guards:**
  - Tenant scoping con el patrón `es_super` existente (igual que `feedback`/`no-pqrs`).
  - "Tiene AC disponible": el tenant debe tener `ATENCION_CLIENTE` entre sus workflows disponibles (reusar la query de `workflows_disponibles` de `/auth/me`: DISTINCT `tipo_workflow` de `config_buzones` ∪ `plantillas_respuesta` activas del tenant). Si no → `403`. Esto limita el feature a FF sin hardcodear el UUID.
  - `tipo_workflow` target válido (∈ {PQRS, ATENCION_CLIENTE}) → si no, `400`.
- **Efecto:**
  - `UPDATE pqrs_casos SET tipo_workflow=$nuevo, es_pqrs=$flag` donde `flag = false` si AC, `true` si PQRS.
  - `INSERT pqrs_clasificacion_feedback` (señal de aprendizaje en ambas direcciones; mismo shape que el endpoint feedback).
  - `INSERT audit_log_respuestas` con `accion='WORKFLOW_RECLASIFICADO'`, `metadata={anterior, nuevo}`.
- **No** regenera borrador, **no** toca `tipo_caso` ni `borrador_estado`.
- **Respuesta:** `{ "ok": true, "tipo_workflow": "<nuevo>" }`.

### Frontend — `frontend/src/components/ui/caso-detail-overlay.tsx`

- **Modo PQRS:** `handleNoPQRS` deja de postear feedback y pasa a llamar `PATCH /admin/casos/{id}/workflow {tipo_workflow:"ATENCION_CLIENTE"}`. Label del botón: **"No es PQR → Atención al cliente"**. Al éxito, `onStatusChange` saca el caso de la bandeja PQRS (idealmente cierra/refresca el overlay).
- **Modo AC** (`esAC === true`): botón nuevo **"Sí es PQR"** → `PATCH ... {tipo_workflow:"PQRS"}`. Al éxito sale de AC y aparece en bandeja PQRS ("levantado").
- **Gating:** ambos botones sólo visibles si `tieneAC` (`useTenantWorkflows`) y rol admin → invisibles para Recovery/Demo.
- La bandeja (`admin-bandeja.tsx`) refetchea tras `onStatusChange`.

### Guard a verificar

El filtro/borrado "No PQRS" (vista PQRS) debe estar scopeado por `tipo_workflow='PQRS'`, para que un caso movido a AC (con `es_pqrs=false`) **no** sea borrable por accidente desde la vista PQRS. Confirmar en el plan; si no lo está, agregar el scope.

### Tests

- Endpoint: PQR→AC mueve `tipo_workflow` y setea `es_pqrs=false`; AC→PQR mueve y setea `es_pqrs=true`; ambos crean fila de audit. 403 para no-admin. 403 para tenant sin AC (Recovery). 400 para `tipo_workflow` inválido.

---

## Cambio A — Imágenes inline del cuerpo (base64)

### Worker — `backend/master_worker_outlook.py`

- Helper nuevo `_inline_images_a_base64(em, prov) -> str`:
  - Regex `src=["']cid:([^"']+)["']` sobre `em['body']`.
  - Para cada `cid`, matchear contra `em['attachments']` por `contentId` (Graph lo expone; el cid puede venir envuelto en `<>` → normalizar).
  - Bajar bytes con `download_attachment` (reusa el método existente), base64-encode, construir `data:{contentType};base64,{b64}` y reemplazar `cid:<id>`.
  - **Caps:** saltear imágenes > ~2 MB; tope total prudente. Si una falla, dejar el `cid:` intacto (= comportamiento actual, imagen rota) — **best-effort, nunca propaga excepción ni rompe la ingestión.**
  - Devuelve el cuerpo reescrito (o el original si no hubo cambios).
- Extender `MultiTenantOutlookListener.get_attachments_meta` para incluir `contentId` e `isInline` (Graph `/messages/{id}/attachments` ya los devuelve).
- **Call site único:** dentro de `for em in parsed_emails`, tras el chequeo de cutoff (~línea 530) y **antes** del dispatch PQRS/AC (~línea 532): `em['body'] = _inline_images_a_base64(em, prov)`. Así cubre los dos inserts (PQRS y `procesar_atencion_cliente`) sin duplicar.

### Frontend

Sin cambios: el `<iframe srcDoc>` ya renderiza `data:` URIs y el `sandbox="allow-popups"` no las bloquea. Solo verificación visual.

### Tests

- Unit del helper con un email fixture (cuerpo con `cid:` + attachment con `contentId` matching) → el cuerpo resultante contiene `data:...;base64,`. Caso sin inline → cuerpo intacto. Imagen sobre el cap → se saltea sin error.

---

## Alcance, migraciones, deploy

- **Cero migraciones de DB nuevas**: `tipo_workflow` ya existe; el audit usa `metadata` JSON; base64 va en `cuerpo` TEXT existente.
- **Orden:** B primero (Mica lo escaló dos veces), A después. Branch desde `main`, dos commits/PRs separados.
- **Verificación:** tests nuevos + `scripts/verify.sh` (pytest dentro de `pqrs_v2_backend` + `/health` + prod read-only).
- **Deploy:** ventana **>18:00** (no cortar servicio). Staging (`15.229.114.148`) → prod (`18.228.54.9`). Preflight: diff `frontend/package.json` (reuse vs rebuild imagen front) + restaurar `docker-compose.yml` del backup post `git pull`.

## Criterios de aceptación

**B:**
1. Admin FF, caso PQRS → "No es PQR" → el caso sale de la bandeja PQRS y aparece en Atención al Cliente; fila de audit `WORKFLOW_RECLASIFICADO`.
2. Admin FF, caso AC → "Sí es PQR" → el caso aparece en bandeja PQRS ("levantado"); fila de audit.
3. Recovery/Demo: los botones no aparecen y el endpoint responde 403.
4. No-admin: 403.

**A:**
5. Correo Outlook con imagen inline (`cid:`) → `caso.cuerpo` contiene `data:...;base64,` y el detalle muestra la imagen.
6. Correo sin inline → cuerpo sin cambios.
7. Imagen sobre el cap → se saltea, ingestión OK.

## Fuera de alcance

- Descarte/spam real como acción separada (hoy queda sin botón propio tras repurposar "No PQRS"; decidir en un cambio futuro).
- Re-procesamiento automático de borrador al reclasificar.
- Zoho inline (FF es Outlook).
- Servir imágenes desde MinIO (se eligió base64; revisitar si el tamaño de `cuerpo` se vuelve problema).

## Riesgos

- `get_attachments_meta` podría no traer hoy los inline → mitigado extendiéndolo; verificar que Graph los liste.
- Bloat de `cuerpo` con base64 → mitigado con caps; sólo afecta el payload del detalle (las listas no cargan `cuerpo`).
- `es_pqrs=false` en casos AC podría exponerlos al borrado "No PQRS" → mitigado con el guard de scoping por `tipo_workflow`.
