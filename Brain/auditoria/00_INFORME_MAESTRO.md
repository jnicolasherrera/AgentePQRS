# Auditoría completa AgentePQRS — Informe Maestro

**Fecha:** 2026-06-25 · **Rama auditada:** `main` (tras merge de #20/#21/#22)
**Método:** 3 subagentes en paralelo (envío/worker · IA/RBAC/DB · frontend/infra/drift) + verificación manual de los 2 críticos top.

> Informes de detalle: `01_envio_ingesta_worker.md`, `02_ia_plantillas_rbac_db.md`, `03_frontend_infra_drift.md`.

## Conteo de hallazgos
| Severidad | Cantidad (únicos) |
|---|---|
| 🔴 CRÍTICO | 6 |
| 🟠 ALTO | 10 |
| 🟡 MEDIO | ~20 |
| ⚪ BAJO | ~18 |

---

## 🔴 CRÍTICOS (parche ya — antes de la nueva versión)

### C1 · Fuga de adjuntos entre tenants — `casos.py:469-471` ✅VERIFICADO
`download_adjunto`: query `WHERE id=$1 AND caso_id=$2`, **sin `cliente_id` ni rol**. Como el backend corre como `pqrs_admin` (BYPASSRLS), **cualquier usuario autenticado puede bajar documentos (tutelas, cédulas, PDFs) de CUALQUIER tenant** iterando UUIDs.
**Fix:** agregar `AND cliente_id = $tenant` (+ filtro `asignado_a` para abogados) a la query.

### C2 · Backend corre como superuser que bypassa RLS — `config.py:5` (arquitectónico)
`database_url` usa `pqrs_admin` (BYPASSRLS). **El RLS no aísla NADA en la API** — todo el aislamiento multi-tenant depende de WHERE manuales. Multiplica la severidad de toda omisión de filtro (C1, A3, A4).
**Fix:** migrar el backend a `pqrs_backend` (RLS activo) usando `SET LOCAL` por transacción. Cambio mayor → planificar; mientras tanto, auditar TODO query por filtro de tenant.

### C3 · `jwt_secret_key` default `"dev-key-change-in-prod"` — `config.py:7`
Si el `.env` de prod no lo sobreescribe, los JWT son **falsificables** → cualquiera firma un token `super_admin` de cualquier tenant. **VERIFICAR en prod ya** que la env var esté seteada.

### C4 · `worker_outlook.py:12` — secreto Azure roto (string literal) ✅VERIFICADO
`AZURE_CLIENT_SECRET = "os.environ.get("AZURE_CLIENT_SECRET")"` → es un string literal, **nunca lee la env**. Además `client_id` y `tenant_id` **hardcodeados en texto plano** (líneas 11,13). Auth Graph de ese worker rota.
**Fix:** `os.environ.get(...)` real + sacar credenciales a env. Confirmar si este worker legacy se usa en prod (si no, **borrarlo** — da falsa superficie).

### C5 · Loop infinito NO arreglado en workers legacy — `worker_outlook.py:118-128`, `worker_outlook_cliente2.py`
El fix de `mark_as_read`-antes-de-`continue` (que aplicamos al `master_worker_outlook.py`) **NO está** en los workers legacy. Mismo patrón que generó las 776k filas. Si alguno está activo en prod → bomba de tiempo.
**Fix:** confirmar qué worker corre en prod (debería ser solo `master_worker_v2`); si los legacy están muertos, borrarlos.

### C6 · Remitente `democlasificador@gmail.com` sigue vivo como fallback — `demo_worker.py:31`, `casos.py:111-112`
El bug original "los mails salen de la casilla equivocada" persiste como **default del fallback SMTP** (`DEMO_GMAIL_USER`). Si el camino primario (Graph/Zoho) falla, todavía puede salir desde el Gmail demo.
**Fix:** quitar el default Gmail; el fallback debe usar el buzón real del tenant o fallar ruidosamente.

---

## 🟠 ALTOS (incluir en el parche de versión)

- **A1 · Fallback SMTP enmascara fallos — `casos.py:1002-1011`.** Ante cualquier `ok=False` de Graph/Zoho, cae a SMTP y marca el caso `ENVIADO/CERRADO` **igual** → el operador cree que respondió aunque no salió nada. Debe propagar el error real.
- **A2 · Credenciales Azure hardcodeadas + usadas como fallback cross-tenant — `master_worker_outlook.py:71,73,536-538`.** Un buzón mal configurado de otro tenant usaría las credenciales de FlexFintech.
- **A3 · `get_caso_detalle` sin filtro `asignado_a` — `casos.py:322-341`.** Un abogado puede **ver** casos fuera de su cartera (fuga intra-tenant entre carteras de Recovery).
- **A4 · `update_caso` (PATCH) sin verificación de rol — `casos.py:490-534`.** Cualquier rol autenticado puede cambiar estado/reasignar casos. Escalada de privilegios.
- **A5 · `UPDATE pqrs_casos WHERE id=$5` sin `cliente_id` — `plantilla_engine.py:473-481`.** En el worker (BYPASSRLS) puede escribir sobre casos de otro tenant si hay colisión.
- **A6 · Conexión del pool con `set_config(is_local=false)` — `core/db.py:63-87`.** El tenant **persiste** en la conexión devuelta al pool. Hoy mitigado por BYPASSRLS, pero bomba latente al migrar a `pqrs_backend` (C2). Usar `SET LOCAL` transaccional.
- **A7 · Prompt injection en clasificación y borrador — `ai_engine.py:116-124`, `plantilla_engine.py:161-168`.** El email entrante (asunto/cuerpo/remitente + adjuntos + RAG) se interpola **sin sanitizar** en el prompt de Claude que genera la respuesta legal al ciudadano.
- **A8 · `em['id']:20` puede lanzar TypeError — `master_worker_outlook.py:679`.**
- **A9 · Motivo de error hardcodeado "Error Zoho" — `casos.py:1108`** (aunque el fallo sea de Graph/SMTP).
- **A10 · DRIFT frontend operador (`5ea8c2b`) NO en prod.** Los abogados ven UI admin que el backend rechaza con 403. Deploy quirúrgico pendiente (Fase 2a).

---

## 🟡 MEDIOS (destacados — lista completa en informes 01/02)
- `ai_engine.py:144` — Claude **nunca** puede marcar `NO_PQR` (se sobreescribe) → ruido de casos falsos.
- `plantilla_engine.py:118,448` — estado RAG en atributo de función mutable → **race condition cross-caso** en worker concurrente.
- `ai_classifier.py:64` — adjuntos binarios (PDF/imagen) decodificados como UTF-8 al clasificar (no usa `document_reader`).
- `master_worker_outlook.py:230` — `mark_as_read` (Graph) **ignora el status** del PATCH → eslabón débil del fix del loop.
- Paths "no-PQRS / tipo-descartado / cutoff" del master **no marcan leído** → reproceso perpetuo (consume cuota Graph, sin inflar filas).
- `obtener_plantilla` `LIMIT 1` sin `ORDER BY` → plantilla no determinista con duplicados.
- Firma: si `firma_bytes()` es None (imagen ausente), sale firma vacía en silencio para tenants con imagen.
- `_es_flexfintech` por substring `"flexfintech.com" in email` → un `noreply@noflexfintech.com` matchearía.
- `/health` (DT-25, commit `87c7df7`) **no está en prod** → probes de monitoreo dan 404.

## ⚪ BAJOS (deuda menor)
- `asyncio.get_event_loop()` deprecado (`ai_classifier.py:102`).
- `md_to_html` rompe con asteriscos sueltos (`email_utils.py:21`).
- `email_respuesta_override` no se limpia tras enviar (`casos.py:944`).
- `personalizar_borrador` `.replace()` literal frágil (`plantilla_engine.py:341`).
- `workers/inbound_email/main.py` es un stub que solo loguea (falsa sensación de procesamiento).
- Secretos en claro en `docker-compose.yml` (Redis/MinIO/PG) — DT-20.

---

## 🚀 Plan de parche → nueva versión (propuesto)

**Lote 1 — Seguridad multi-tenant (URGENTE, parche quirúrgico a prod):**
1. C1: filtro tenant+cartera en `download_adjunto`.
2. C3: verificar `jwt_secret_key` en prod (si está el default → rotar YA).
3. A3+A4: filtro `asignado_a` en `get_caso_detalle` + verificación de rol en `update_caso`.
4. A1: fallback SMTP que NO marque enviado si falla.

**Lote 2 — Higiene de workers (riesgo operativo):**
5. C4+C5+C6: confirmar qué workers corren en prod; borrar legacy muertos; quitar default Gmail.
6. A2: credenciales Azure a env (no hardcode/fallback cross-tenant).

**Lote 3 — Robustez IA/datos (mejora calidad):**
7. A7: sanitizar input antes del prompt de Claude.
8. Medios de IA: `NO_PQR` respetado, RAG sin estado compartido, parser de adjuntos real.

**Lote 4 — Arquitectura (sesión aparte, mantenimiento):**
9. C2+A6: migrar backend a `pqrs_backend` + `SET LOCAL` transaccional. RLS real.
10. Alinear prod con main (drift ~8 commits) en ventana de mantenimiento.

> **Regla de oro vigente:** todo a prod es quirúrgico (backup `.bak` + CRLF + archivo puntual + rebuild del servicio). NO `git pull` en prod. NO seed de plantillas. Validar cada lote: red de seguridad → dry-run → tanda chica → lote completo.
