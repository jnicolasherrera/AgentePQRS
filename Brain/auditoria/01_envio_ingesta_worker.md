# Auditoría — Corazón del sistema AgentePQRS

**Áreas:** pipeline de ENVÍO de respuestas, INGESTA de correo y WORKER de seguimientos.
**Fecha:** 2026-06-25 · **Alcance:** solo lectura/análisis (no se modificó código).
**Rama:** main.

Archivos auditados:
- `backend/app/api/routes/casos.py` (1240 líneas) — endpoint `aprobar_lote` (enviar-lote), `_send_via_smtp_fallback`, `_firma_html`, `editar_destinatario`.
- `backend/app/services/outlook_send_engine.py` — `OutlookSenderV2.send_reply` (Graph sendMail).
- `backend/app/services/zoho_engine.py` — `ZohoServiceV2` (token, send_reply, acuse).
- `backend/app/services/firma_engine.py` — firma por tenant.
- `backend/app/services/email_utils.py` — `md_to_html`.
- `backend/master_worker_outlook.py` (860 líneas) — worker principal: ingesta, clasificación, `_registrar_seguimiento`, loop.
- `backend/worker_outlook.py`, `backend/worker_outlook_cliente2.py`, `backend/demo_worker.py` — variantes de worker.
- `workers/inbound_email/main.py`, `workers/inbound_email/producer.py` — stub Kafka.

---

## RESUMEN EJECUTIVO — TOP hallazgos

| # | Severidad | Archivo:línea | Hallazgo |
|---|-----------|---------------|----------|
| 1 | **CRÍTICO** | `worker_outlook.py:118-128` | Loop infinito de reproceso NO arreglado en el worker legacy: `continue` sin `mark_as_read` con fetch filtrando `isRead eq false`. Mismo patrón que causó 776k filas en el master. |
| 2 | **CRÍTICO** | `demo_worker.py:31` | Credencial/identidad hardcodeada: default `democlasificador@gmail.com`. Mismo bug de remitente original "resuelto" sigue vivo como fallback por defecto. |
| 3 | **CRÍTICO** | `worker_outlook.py:12` | `AZURE_CLIENT_SECRET = "os.environ.get(\"AZURE_CLIENT_SECRET\")"` — string literal, NO la llamada. El secreto nunca se lee del entorno → auth Graph rota / valor basura. |
| 4 | **ALTO** | `master_worker_outlook.py:71,73` · `worker_outlook.py:11,13` | Azure `client_id` y `tenant_id` reales hardcodeados en el código fuente (no en env). |
| 5 | **ALTO** | `casos.py:1002-1011` | El fallback SMTP se dispara ante CUALQUIER `ok=False` de Graph/Zoho y enmascara el fallo: marca el caso `ENVIADO`/`CERRADO` aunque SMTP también pueda silenciar problemas de remitente (From ajeno con Gmail). |

---

# ÁREA 1 — PIPELINE DE ENVÍO DE RESPUESTAS

Archivo principal: `casos.py` → `aprobar_lote` (endpoint enviar-lote, def en línea 866).

## (a) Qué hace — flujo paso a paso

1. **Validación de entrada** (871-874): máximo 10 casos por lote; al menos 1.
2. **Re-autenticación por contraseña** (876-879): se re-verifica el `password_hash` del usuario actual (buen control: aprobación de envío requiere password). 401 si falla.
3. **Selección de buzón del tenant** (886-894): query a `config_buzones` por `cliente_id` + `is_active`, ordenando `OUTLOOK` primero (`ORDER BY CASE WHEN proveedor='OUTLOOK' THEN 0 ELSE 1`), `LIMIT 1`.
4. **Construcción de senders** (895-902): `proveedor` normalizado a upper; instancia `ZohoServiceV2` si ZOHO, `OutlookSenderV2` si OUTLOOK.
5. **SharePoint engine** (904-924): best-effort; si falla, sigue sin archivado.
6. **Loop por caso** (931-1111):
   - Trae caso (`borrador_respuesta` obligatorio; si falta → error "Sin borrador").
   - `email_destino = email_respuesta_override or email_origen` (override de destinatario, bloque 5).
   - Carga adjuntos de reply (`es_reply=TRUE`) desde MinIO.
   - `subject = "Re: " + asunto`.
   - **Enrutamiento** (969-1011):
     - OUTLOOK → arma HTML con `md_to_html(borrador)` + firma por tenant (`firma_html_cid`), llama `outlook_sender.send_reply`. Si devuelve False o lanza excepción → cae a SMTP.
     - ZOHO → `zoho.send_reply(...)`. Idem fallback.
     - Si `not ok` tras el camino primario → `_send_via_smtp_fallback(... from_address=buzon["email_buzon"])`.
   - Si `ok`: UPDATE caso a `borrador_estado='ENVIADO', estado='CERRADO'`, INSERT en `audit_log_respuestas` con `metodo_envio`, append a `enviados`.
   - Best-effort: `aprender_de_envio` (re-ingesta KB) y archivado SharePoint (solo PQRS con cédula).
   - Si `not ok`: append a `errores` con motivo fijo "Error Zoho al enviar".
7. **Respuesta** (1113): `{enviados, lote_id, errores}`.

### Sub-flujo `_send_via_smtp_fallback` (97-154)
- Lee `SMTP_FALLBACK_HOST/PORT/USER/PASS` (con fallback a `DEMO_GMAIL_USER/PASSWORD`).
- Si no hay user/pass → log error + return False (envío perdido pero registrado).
- `mail_from = from_address or smtp_user`. Construye MIME `related` (con firma imagen CID) o `alternative` (firma texto).
- `server.sendmail(smtp_user, to_email, root.as_string())` — el envelope-from es `smtp_user`, el header From es `mail_from`.

### Sub-flujo `OutlookSenderV2.send_reply` (outlook_send_engine.py 66-135)
- Adjunta firma inline (CID `firma_arc`) + adjuntos no-inline en base64.
- POST a `/users/{from_buzon}/sendMail` con `saveToSentItems=True`.
- Éxito = HTTP 202. Cualquier excepción → return False (logueado).

### Sub-flujo `ZohoServiceV2.send_reply` (zoho_engine.py 221-272)
- Rate-limit interno (`_rate_limit_send`: 15/min, 3s entre envíos).
- Firma por tenant vía `firma_html_datauri(email_buzon=from_address)`.
- Sin adjuntos: POST JSON; con adjuntos: multipart/form-data.
- Retorna `res is not None` (sin adjuntos) / `status<400` (con adjuntos).

## (b) Bugs

- **[ALTO] `casos.py:1002-1011` — fallback SMTP enmascara fallos del proveedor primario.**
  Si Graph/Zoho devuelven `ok=False` por una razón legítima (token sin permiso `Mail.Send`, buzón mal configurado, From rechazado), el código cae **automáticamente** a SMTP. Si SMTP está configurado con Gmail demo, el correo sale con remitente potencialmente inválido o desde el dominio equivocado, y el caso se marca `ENVIADO`/`CERRADO` igual. El operador cree que respondió bien. Es exactamente el patrón de "fallback que enmascara fallos" + el bug histórico de remitente. Debería distinguir "no se pudo enviar por el canal correcto" de "se envió por un canal alternativo seguro".

- **[ALTO] `casos.py:1108` — motivo de error hardcodeado "Error Zoho al enviar".**
  El branch de error final agrega `{"motivo": "Error Zoho al enviar"}` aunque el tenant sea OUTLOOK o el fallo sea de SMTP. Mensaje engañoso para diagnóstico/soporte.

- **[MEDIO] `casos.py:886-894` — solo se usa UN buzón por tenant para TODO el lote.**
  `LIMIT 1` con orden que prioriza OUTLOOK. Si un tenant tiene múltiples buzones activos (p. ej. uno ZOHO y uno OUTLOOK, o varios buzones OUTLOOK por área), todos los casos del lote se responden desde el mismo buzón, ignorando de qué buzón entró cada caso. No hay vínculo caso→buzón de origen. Riesgo de responder desde el buzón equivocado.

- **[MEDIO] `casos.py:1012-1031` — falta de idempotencia / atomicidad en el envío.**
  El UPDATE de estado y el INSERT de auditoría ocurren tras un envío exitoso pero NO en una transacción explícita. Si el proceso muere entre `send_reply` (correo ya despachado, 202) y el UPDATE, el caso queda en `PENDIENTE`/`borrador` y puede reenviarse en un lote posterior → **doble envío al ciudadano**. No hay guard tipo "ya enviado" antes de despachar (no se chequea `borrador_estado` actual del caso al inicio del loop; solo se exige que exista `borrador_respuesta`).

- **[MEDIO] `casos.py:962` — asunto de respuesta duplica "Re:".**
  `subject = f"Re: {caso['asunto']}"`. Si el caso ya es un seguimiento cuyo `asunto` empieza con "Re:" (caso reabierto por `_registrar_seguimiento`), el envío sale como "Re: Re: ...". No corrompe, pero es ruido y rompe el threading limpio.

- **[BAJO] `email_utils.py:21` — `md_to_html` puede romper HTML/markdown con asteriscos sueltos.**
  La regex de itálicas `\*([^*\n]+?)\*` puede convertir texto legítimo con `*` (listas, multiplicaciones) en `<em>`. Bajo impacto pero afecta render de respuestas.

- **[BAJO] `casos.py:944` vs envío** — el `email_respuesta_override` no se limpia tras enviar. Si el caso se reabre por un seguimiento y se reenvía, el override viejo persiste y podría dirigir la nueva respuesta a un destinatario obsoleto.

## (c) Riesgos de robustez

- **Fallback que enmascara fallos** (ver bug ALTO arriba) — el más serio del área.
- **`except Exception` amplio en el loop** (`casos.py:1109-1111`): captura TODO por caso y solo agrega `{"motivo": str(e)}`. Errores de programación (KeyError, etc.) se reportan como "error de envío" indistintamente; el lote continúa, lo cual es deseable, pero el diagnóstico se degrada.
- **Best-effort silencioso en KB y SharePoint** (`1038-1047`, `1052-1106`): correcto que no rompan el envío, pero un fallo sistemático de archivado SP (requisito legal de retención para PQRS) solo deja un `warning` en logs. Sin alerta → pérdida silenciosa de archivado.
- **Sin transacción** entre envío externo y persistencia de estado → riesgo de doble envío / estado inconsistente.
- **`download_file` sin manejo de None explícito por adjunto** (953-960): si MinIO falla, el adjunto simplemente no se incluye y el correo sale **sin adjunto** sin avisar al operador (envío incompleto silencioso).

---

# ÁREA 2 — INGESTA DE CORREO

Archivo principal: `master_worker_outlook.py` → `master_worker()` (512) y `procesar_atencion_cliente()` (387).

## (a) Qué hace — flujo paso a paso

1. **Setup** (513-516): Redis, conexión DB (`aequitas_worker`, BYPASSRLS), listener Outlook multi-tenant.
2. **Loop infinito** (518): cada ciclo:
   - `_touch_activity()` (healthcheck DT-33).
   - Trae buzones activos con su tenant (521-526).
   - **Por buzón** (528, try interno por buzón):
     - OUTLOOK: credenciales del buzón o fallback global Azure; `listener.fetch_emails(email, folder)` (filtro `isRead eq false`, `$top=5`). Parseo de cada mensaje (sender, body, attachments meta).
     - ZOHO: `zoho.fetch_unread_emails`; por mensaje resuelve `get_message_detail` para el body completo; lista adjuntos si los hay.
     - SharePoint engine por tenant si configurado.
     - Cutoff `procesar_desde` y `default_workflow` del buzón.
   - **Por email** (589):
     - Parsea fecha (tz-aware).
     - **`_registrar_seguimiento`** (600): si es Re:/Fw: vinculable → registra comentario + reabre + `mark_as_read` + `continue`.
     - Cutoff: descarta mails anteriores a `procesar_desde`.
     - Inline images cid→base64 en `em['cuerpo_html']`.
     - Dispatcher PQRS vs ATENCION_CLIENTE: AC solo para FlexFintech (627-637).
     - Flow PQRS: `parece_pqrs` → `clasificar_hibrido` → valida tipo → calcula vencimiento (días hábiles CO) → round-robin de analistas → resuelve `documento_peticionante` (cédula del clasificador / histórico / regex) → INSERT con `ON CONFLICT (cliente_id, external_msg_id) DO NOTHING`.
     - Si TUTELA: `detectar_pqr_origenes` (auto-match con PQRs previos).
     - Acuse de recibo (solo Recovery, no tutela, no juzgado).
     - Descarga adjuntos → genera borrador con Claude → sube adjuntos a SP/MinIO.
     - `mark_as_read` + publica SSE.
3. **`check_tutela_alerts_2h`** al final de cada ciclo (804).
4. **Manejo de reconexión DB** (806-817, DT-32) y `except Exception` general (818-820). Sleep 15s.

`procesar_atencion_cliente` (387-509): flow simplificado FF — sin tipo legal, sin vencimiento, round-robin con admins, borrador AC, mark_as_read, SSE.

## (b) Bugs

- **[CRÍTICO] `worker_outlook.py:12` — secreto Azure como string literal.**
  ```python
  AZURE_CLIENT_SECRET = "os.environ.get("AZURE_CLIENT_SECRET")"
  ```
  No es la llamada a `os.environ.get`; es un string que contiene ese texto (de hecho rompe el quoting). El worker legacy nunca obtendrá el secreto real → fallo de auth Graph. Si este worker se ejecuta, no ingesta nada o crashea.

- **[ALTO] `master_worker_outlook.py:679` — `em['id'][:20]` puede lanzar TypeError.**
  En el log "Email ya procesado" se hace `em['id'][:20]`. Si `em['id']` es None (mensaje sin id), revienta. Aunque el INSERT normaliza con `(em['id'] or '').strip() or None`, el log NO. El `except Exception e_buzon` lo atrapa pero aborta el resto de ese buzón en ese ciclo.

- **[ALTO] `master_worker_outlook.py:536-538` — credenciales Azure globales hardcodeadas como fallback.**
  `AZURE_CLIENT_ID`/`AZURE_TENANT_ID` literales (71,73). Si un buzón no trae sus credenciales, usa las globales de FlexFintech — un buzón mal configurado de OTRO tenant podría intentar autenticarse con las credenciales de FF (cross-tenant). Riesgo de fuga/confusión multi-tenant.

- **[MEDIO] `master_worker_outlook.py:439-440` — round-robin con índice global puede saltar agentes.**
  `idx = r.incr(rr_ac:{c_id}) - 1; agentes[idx % len(agentes)]`. Si la lista de agentes cambia de tamaño entre ciclos (activación/desactivación), el módulo reparte desigual, pero más grave: el contador Redis nunca se acota y es por-tenant compartido entre AC y PQRS usa otra key (`rr:` vs `rr_ac:`) — OK separadas. Riesgo bajo-medio de reparto desbalanceado, no funcional.

- **[MEDIO] `master_worker_outlook.py:558-559` — `except Exception: pass` al traer detalle Zoho.**
  Si `get_message_detail` falla, se usa solo `summary` (cuerpo truncado) silenciosamente. La clasificación y el borrador se generan con texto incompleto sin ninguna señal.

- **[MEDIO] `master_worker_outlook.py:216,222` — fetch/attachments devuelven `[]` ante CUALQUIER error HTTP.**
  `return resp.json().get("value", []) if resp.status_code < 400 else []`. Un 401/429/500 de Graph se trata idéntico a "bandeja vacía". El worker cree que no hay correos y sigue tan campante → **pérdida silenciosa de ingesta** ante problemas de token o throttling. No hay log del status code de error.

- **[BAJO] `master_worker_outlook.py:592` — `import` dentro del loop** (`from datetime import timezone`). Cosmético/perf menor.

- **[BAJO] `master_worker_outlook.py:648` vs `592`** — el comentario dice "dt ya calculado" pero recalcula vencimiento con `pd.Timestamp(dt).tz_convert('UTC')`; si dt ya es UTC está bien, pero depende del tz-handling previo. Verificar con tutelas en horario límite.

## (c) Riesgos de robustez

- **Errores HTTP de Graph tratados como bandeja vacía** (216,222) → ingesta se detiene en silencio. **El más peligroso del área** para disponibilidad.
- **`except Exception: pass`** en detalle Zoho (558) y en mark_as_read de spam (412) → tragan errores.
- **`except Exception as e_buzon`** (801) por buzón: aísla fallos de un buzón (bueno), pero un error temprano (p. ej. línea 679) corta TODO el procesamiento restante de ese buzón en el ciclo; los emails siguientes esperan al próximo ciclo.
- **Credenciales hardcodeadas** (client_id/tenant_id) y fallback cross-tenant.
- **Idempotencia de ingesta:** depende de `ON CONFLICT (cliente_id, external_msg_id)`. Correcto SIEMPRE que `external_msg_id` no sea None. Para mails sin id (`(em['id'] or '').strip() or None` → None), el ON CONFLICT NO aplica (NULL nunca conflicta) → riesgo de duplicados de casos si llega el mismo mail sin id dos veces. Bajo en práctica (Graph siempre da id) pero presente.

---

# ÁREA 3 — WORKER DE SEGUIMIENTOS

Función principal: `_registrar_seguimiento` (`master_worker_outlook.py:103-189`) + su integración en el loop (600-612).

## (a) Qué hace — flujo paso a paso

1. **Short-circuit** (111-112): si el asunto NO matchea `_RE_PREFIX` (Re:/Fw:/CO - Re:/etc.) → return False inmediato (barato).
2. **Match por radicado** (116-124): busca `PQRS-YYYY-XXXXXX` en asunto o primeros 1000 chars del cuerpo; query por `numero_radicado` + `cliente_id`.
3. **Fallback por asunto base + remitente** (126-138): quita prefijos, si el asunto base ≥ 8 chars busca caso del mismo `email_origen` con `asunto ILIKE %base%` en últimos 90 días, el más reciente.
4. **Si no hay caso** → return False (sigue como caso nuevo).
5. **Construye comentario** (143-144).
6. **Guard de idempotencia** (150-155): chequea si YA existe un comentario idéntico (`comentario = $2` + `tipo_evento='SEGUIMIENTO_CIUDADANO'`). Si no existe:
   - INSERT comentario (157-161).
   - **Genera borrador** para el nuevo mensaje (`generar_borrador_para_caso`, dentro del `if not ya_existe`) — best-effort (168-179).
7. **Reapertura** (180-187): si el caso estaba CERRADO/CONTESTADO → `estado='EN_PROCESO'`. Se ejecuta SIEMPRE (idempotente).
8. **return True** (189) → el caller marca leído y hace `continue`.

### Integración en el loop (600-612)
Tras `_registrar_seguimiento`→True: `try` mark_as_read (OUTLOOK con buzón, otros con id) → `except` warning → `continue`. **El fix del loop infinito (mark_as_read antes del continue) está presente en este path.**

## (b) Bugs

- **[CRÍTICO] `worker_outlook.py:118-128` — el fix del loop infinito NO está en el worker legacy.**
  `fetch_unread_emails_colombia` usa `$filter=isRead eq false` (línea 66), pero los `continue` de "no es PQRS" (121) y "descartado por tipo" (128) **no llaman `mark_as_read`**. `mark_as_read` solo se ejecuta al final del flujo exitoso (187). Resultado: todo mail no-PQRS o de tipo descartado se relee en CADA ciclo (cada 10s) para siempre — el mismo patrón que generó 776k filas en el master. Además este worker **no tiene `_registrar_seguimiento` ni dedup**: cualquier mail que no genere caso se reprocesa indefinidamente. `worker_outlook_cliente2.py` comparte la estructura (mark_as_read solo en 181). Severidad CRÍTICA si alguno de estos workers está activo en prod; ALTA si son legacy muertos (verificar despliegue).

- **[MEDIO] `master_worker_outlook.py:150-161` — el guard de idempotencia compara el cuerpo COMPLETO.**
  `WHERE comentario = $2`. El comentario incluye `body[:2000]`. Si el ciudadano reenvía un Re: con una variación mínima (firma del cliente de correo, timestamp citado, "El día X escribió..."), el texto difiere y el guard NO detecta el duplicado → inserta otro comentario y regenera otro borrador. El guard es frágil ante variaciones; la defensa real es `mark_as_read`. Si por cualquier razón el `mark_as_read` falla (Graph 4xx/5xx — recordar que mark_as_read no chequea status, ver abajo), reaparece y el guard puede no atraparlo.

- **[MEDIO] `master_worker_outlook.py:230-232` — `mark_as_read` (OUTLOOK) ignora el resultado del PATCH.**
  `requests.patch(...)` sin verificar status code ni excepción dentro del método. Si el PATCH falla (token, throttling 429), el método retorna normalmente, el `continue` ocurre, pero el mail **sigue no-leído** → reaparece el próximo ciclo. Combinado con el guard frágil (arriba), reabre la puerta al reproceso. El caller envuelve en try/except pero el except solo se dispara si `requests.patch` lanza, no si devuelve 4xx (no lanza por defecto). **Este es el eslabón débil del fix del loop infinito.**

- **[MEDIO] `master_worker_outlook.py:183-187` — reapertura siempre, incluso si el comentario ya existía.**
  Si un seguimiento reaparece (guard atrapó el comentario duplicado → no inserta), igual se ejecuta el UPDATE de reapertura. Si un operador ya movió el caso de CERRADO a otro estado manualmente y el mail reaparece, podría reabrirse no deseadamente. Idempotente respecto al estado pero puede pisar transiciones manuales. Bajo-medio.

- **[BAJO] `master_worker_outlook.py:127-138` — match por `asunto ILIKE %base%` puede vincular caso equivocado.**
  Mismo remitente + asunto similar en 90 días → toma el más reciente. Si el ciudadano tiene varios PQRs con asuntos parecidos ("Reclamo factura"), el seguimiento puede adjuntarse al caso equivocado. Heurístico aceptable pero con falsos positivos.

## (c) Riesgos de robustez

- **El fix del loop infinito depende de que `mark_as_read` realmente marque el mail**, y `mark_as_read` (230-232) no verifica el resultado del PATCH. Es defensa en profundidad incompleta: si Graph rechaza el PATCH, el guard de idempotencia (frágil, compara texto exacto) es la única red, y puede fallar ante variaciones del cuerpo. **Recomendación: que `mark_as_read` chequee status 200/2xx y, si falla, NO se haga `continue` silencioso o se registre métrica.**
- **Verificación del patrón mark_as_read-antes-de-continue en TODOS los paths del master:**
  - Path seguimiento (600-612): ✅ presente.
  - Path spam en AC (405-414): ✅ presente (try/except pass).
  - Path "no es PQRS" (640-642): ❌ **NO marca leído** antes del continue. PERO `fetch_emails` filtra `isRead eq false` → estos mails no-PQRS se reprocesan cada ciclo (se reclasifican como no-PQRS y se descartan otra vez). No insertan nada, así que no hay explosión de filas, pero sí reproceso/llamadas a `parece_pqrs` infinitas y consumo de cuota Graph. **Riesgo MEDIO de reproceso silencioso.**
  - Path "tipo descartado" (644-646): ❌ **igual, no marca leído** antes del continue. Mismo riesgo.
  - Path cutoff `procesar_desde` (616-617): ❌ no marca leído. Un mail viejo bajo cutoff se relee cada ciclo indefinidamente (aunque no genera caso). Reproceso silencioso.
  - Path AC spam (405-414): ✅.
  - Flow exitoso PQRS (783-786) y AC (492-498): ✅.
  > **Conclusión:** el fix se aplicó al path de seguimiento (el que causó las 776k filas), pero los paths "no-PQRS", "tipo descartado" y "cutoff" del master **siguen releyendo el mismo correo cada ciclo**. No explotan la tabla (no insertan), pero consumen cuota Graph y CPU para siempre por cada correo descartado. Es una fuga de recursos y un latente — si en el futuro alguno de esos paths empieza a escribir, vuelve el problema de filas.

---

# HALLAZGOS TRANSVERSALES (firma, credenciales, utilidades)

- **[CRÍTICO] `demo_worker.py:31`** — `GMAIL_USER = os.environ.get("DEMO_GMAIL_USER", "democlasificador@gmail.com")`. El remitente demo hardcodeado como **default**. Si `DEMO_GMAIL_USER` no está seteado en algún entorno, los correos demo salen desde `democlasificador@gmail.com` — exactamente el bug de remitente que se suponía resuelto. Además `casos.py:111-112` usa `DEMO_GMAIL_USER/PASSWORD` como fallback de `SMTP_FALLBACK_USER/PASS`, así que el fallback SMTP del endpoint productivo puede terminar enviando desde `democlasificador@gmail.com` si solo están seteadas las vars demo.

- **[ALTO] Credenciales/identidades hardcodeadas en fuente:**
  - `master_worker_outlook.py:71` `AZURE_CLIENT_ID = "b2f0910b-..."`, `:73` `AZURE_TENANT_ID = "f765bba0-..."`.
  - `worker_outlook.py:11,13` mismos valores.
  - `master_worker_outlook.py:90`, `firma_engine.py:23`, `worker_outlook.py:27` `TENANT_FLEXFINTECH = "f7e8d9c0-..."` (UUID de tenant — menos sensible pero acopla lógica de negocio a un literal repetido en 3+ archivos; riesgo de divergencia).
  - `worker_outlook.py:65` y `worker_outlook.py` usan un `folder_id` de Outlook hardcodeado.

- **[MEDIO] Firma por tenant — fallback que enmascara.** `firma_engine.firma_html_cid/datauri`: si `firma_bytes()` es None (imagen ausente en disco) para un tenant NO-FlexFintech, devuelve `""` silenciosamente → correos de Recovery/ARC salen **sin firma institucional** sin avisar. `zoho_engine._firma_html` (12-20) idéntico: `except: return ""`. Pérdida silenciosa de firma legal.

- **[MEDIO] Detección de FlexFintech por substring de email.** `firma_engine._es_flexfintech` (48-53): `"flexfintech.com" in email_buzon.lower()`. Un buzón como `noreply@notflexfintech.com.attacker.com` o variaciones matchearían. Riesgo bajo-medio de clasificación de firma incorrecta.

- **[BAJO] `zoho_engine.py` registries class-level mutables compartidos** (`_token_cache`, `_backoff_registry`, `_last_send_times`): keyed por `refresh_token` (OK para multi-tenant), pero `_last_send_times` es **global** (no por tenant) → el rate-limit de 15/min se aplica agregado a TODOS los tenants Zoho juntos. Si hay varios tenants Zoho, se limitan mutuamente. Y no hay lock: en concurrencia (varias requests de envío simultáneas) hay race en la lista. Bajo en práctica (worker single-thread) pero presente si el endpoint enviar-lote corre concurrente con el worker.

- **[BAJO] `workers/inbound_email/main.py`** es un stub (no procesa, no guarda, solo loguea). Si está desplegado como "consumidor de correos", da falsa sensación de Cero-Pérdida (su docstring lo afirma) cuando no persiste nada. Riesgo de confusión operativa.

---

# RECOMENDACIONES PRIORIZADAS

1. **Eliminar/clarificar workers legacy** (`worker_outlook.py`, `worker_outlook_cliente2.py`): tienen el bug de loop infinito sin fix y un secreto roto. Si están muertos, borrarlos; si están vivos, aplicar el patrón mark_as_read-antes-de-continue y arreglar el secreto.
2. **Quitar el default `democlasificador@gmail.com`** y todos los `client_id`/`tenant_id`/`folder_id` hardcodeados → mover a env/secret manager. Fallar ruidosamente si faltan.
3. **Endurecer `mark_as_read`** (master): verificar status 2xx; si falla, log WARN con el código y NO confiar solo en el guard de idempotencia.
4. **No marcar `ENVIADO` cuando se cayó al fallback SMTP** sin verificar que el remitente sea válido; distinguir `metodo_envio='smtp_fallback'` como estado degradado que requiere revisión, no como éxito pleno.
5. **Transacción** en el bloque envío→UPDATE→audit del enviar-lote, y guard de "ya enviado" al inicio del loop por caso para evitar doble envío.
6. **Tratar errores HTTP de Graph** (fetch/attachments) distinto de "bandeja vacía": loguear status y, ante 401/429/5xx, no asumir vacío.
7. **Aplicar mark_as_read en los paths no-PQRS / tipo-descartado / cutoff** del master para frenar el reproceso/consumo de cuota Graph perpetuo.
