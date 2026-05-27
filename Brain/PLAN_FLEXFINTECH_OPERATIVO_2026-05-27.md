# Plan + Arquitectura — FlexFintech operativo
**Fecha:** 2026-05-27 (sprint del día siguiente al RAG deploy).
**Scope:** SOLO tenant FlexFintech. No afecta a Recovery ni Demo.
**Estado actual:** plan + arquitectura definidos, ejecución pendiente del OK.

---

## Resumen ejecutivo

Hoy FlexFintech tiene 612 casos en backend pero **funcionalmente no está operativo**:
- Solo 1 caso enviado en 2 meses.
- 0 plantillas en `plantillas_respuesta` → todo cae a Claude genérico.
- Sin analistas con rol válido → round-robin falla silenciosamente.
- Worker lee solo `03. Flex Colombia` → la bandeja `Inbox` (atención al cliente) está ignorada.
- Sin override de destinatario → respuestas salen al `email_origen` aunque el adjunto pida otra dirección.
- Sin archivado en SharePoint de las contestaciones.

Después de este sprint, FlexFintech queda con:
- **2 universos** (PQRS + Atención al cliente) con flows distintos pero infraestructura compartida.
- **~50 plantillas reales** de los Excel `Rtas` + `RTA DC`.
- **RAG enriquecido** con ~2.900 casos históricos (Tier 2, esta semana).
- **Editor de destinatario** + audit.
- **Archivado SharePoint** post-envío.
- **Cédula plana** persistida (necesaria para nombrar carpetas SP).
- **Mañana las 00 hs**: los mails que llegan se procesan en flow nuevo; histórico Outlook movido a `CERRADO` manual.

---

## Frentes del sprint

```
                        ┌─────────────────────────────┐
                        │  FlexFintech operativo      │
                        │  (sprint 2026-05-27)        │
                        └────────────┬────────────────┘
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
   ┌──────────▼────────┐ ┌───────────▼──────────┐ ┌─────────▼─────────┐
   │ F1. 2 UNIVERSOS   │ │ F2. PLANTILLAS DEL   │ │ F3. EDITOR DEST.  │
   │    PQRS + AT.CLI  │ │     EXCEL (Rtas+DC)  │ │     + AUDIT       │
   └─────────┬─────────┘ └──────────┬───────────┘ └─────────┬─────────┘
             │                      │                       │
   ┌─────────▼────────────────┐ ┌───▼──────────────┐ ┌──────▼──────────┐
   │ F4. ARCHIVADO SHAREPOINT │ │ F5. CEDULA PLANA │ │ F6. RAG BACKFILL│
   │     {cedula}_{fecha}/    │ │  + email→cedula  │ │   2900 historic │
   └──────────────────────────┘ └──────────────────┘ │   (Tier 2)      │
                                                     └─────────────────┘
```

---

## F1 — 2 universos en el mismo sistema (PQRS + Atención al cliente)

### Problema
- Worker actual: `master_worker_outlook.py:170` lee 1 carpeta por tenant (la del `azure_folder_id`).
- FlexFintech necesita procesar TAMBIÉN la `Inbox` del mismo buzón, pero con un workflow distinto: **NO son PQRS**, son consultas operativas (paz y salvo, comprobantes, pedir documentación).
- No queremos clasificar como tutela algo que es "mandame mi paz y salvo".

### Diseño

**A. Schema — agregar `tipo_workflow`**

```sql
-- Migración 18 (parte 1): tipo_workflow en config_buzones y pqrs_casos
ALTER TABLE config_buzones
  ADD COLUMN tipo_workflow VARCHAR(30) NOT NULL DEFAULT 'PQRS'
  CHECK (tipo_workflow IN ('PQRS', 'ATENCION_CLIENTE'));

ALTER TABLE pqrs_casos
  ADD COLUMN tipo_workflow VARCHAR(30) NOT NULL DEFAULT 'PQRS'
  CHECK (tipo_workflow IN ('PQRS', 'ATENCION_CLIENTE'));

CREATE INDEX pqrs_casos_workflow_idx ON pqrs_casos (cliente_id, tipo_workflow);

-- También en plantillas_respuesta para separar plantillas operativas vs legales
ALTER TABLE plantillas_respuesta
  ADD COLUMN tipo_workflow VARCHAR(30) NOT NULL DEFAULT 'PQRS'
  CHECK (tipo_workflow IN ('PQRS', 'ATENCION_CLIENTE'));
```

**B. Config buzones — 2 filas para FlexFintech**

```sql
-- (1) PQRS: la actual, sin cambios (folder = 03. Flex Colombia)
UPDATE config_buzones SET tipo_workflow = 'PQRS'
WHERE cliente_id = '<FF-uuid>' AND azure_folder_id = '<03_Flex_Colombia_id>';

-- (2) ATENCION_CLIENTE: nueva fila para la Inbox
INSERT INTO config_buzones (cliente_id, email_buzon, azure_folder_id, azure_client_id,
                            azure_client_secret, azure_tenant_id, proveedor, tipo_workflow,
                            is_active)
VALUES ('<FF-uuid>', 'clientes@flexfintech.com', '<Inbox_id>', '<misma-creds>', ...,
        'OUTLOOK', 'ATENCION_CLIENTE', TRUE);
```

(Inbox id se obtiene con Graph: `GET /users/{email}/mailFolders/inbox`.)

**C. Worker — iterar buzones por tipo_workflow**

```python
# master_worker_outlook.py — donde itera buzones de cada tenant
for b in buzones_del_tenant:
    workflow = b['tipo_workflow']  # 'PQRS' o 'ATENCION_CLIENTE'
    parsed_emails = obtener_emails(token, b['email_buzon'], b['azure_folder_id'])

    if workflow == 'PQRS':
        # flow actual: parece_pqrs → clasificar_hibrido → INSERT con tipo_caso
        await procesar_pqrs(em, c_id, ...)
    elif workflow == 'ATENCION_CLIENTE':
        # flow nuevo: clasificar por problemática operativa, no por TUTELA/PETICION
        await procesar_atencion_cliente(em, c_id, ...)
```

**D. Flow de Atención al cliente (nuevo, simplificado)**

```python
async def procesar_atencion_cliente(em, cliente_id, conn, ...):
    # Saltea `parece_pqrs`, `clasificar_hibrido`, `_calcular_vencimiento` con festivos CO.
    # Solo:
    # 1. Detectar problemática operativa (PEDIDO_PAZ_Y_SALVO / COMPROBANTE_RECIBIDO / etc)
    problematica = detectar_problematica_atencion(asunto, cuerpo)

    # 2. INSERT pqrs_casos con tipo_workflow='ATENCION_CLIENTE', tipo_caso=NULL,
    #    nivel_prioridad='NORMAL', fecha_vencimiento=NULL (sin SLA legal).
    caso_id = await conn.execute("INSERT INTO pqrs_casos ... tipo_workflow='ATENCION_CLIENTE' ...")

    # 3. Generar borrador via plantilla específica (filtrada por tipo_workflow=ATENCION_CLIENTE)
    #    o caer a RAG/Claude si no hay plantilla.
    await generar_borrador_para_caso(... tipo_workflow='ATENCION_CLIENTE' ...)
```

**E. Frontend — 2 vistas (futuro, otro agente)**

- `/dashboard/pqrs` — la actual (casos legales).
- `/dashboard/atencion` — nueva (consultas operativas, sin semáforo SLA, sin clasificación legal).

**F. Filtros en queries existentes**

- Métricas SLA (`stats.py`) deben filtrar `WHERE tipo_workflow = 'PQRS'` para no contaminar con atención al cliente que no tiene SLA.
- Búsqueda de plantillas: `obtener_plantilla` agrega `AND tipo_workflow = $3`.
- Auditoría compartida (`audit_log_respuestas`): sin cambios.

---

## F2 — Plantillas del Excel (Rtas + RTA DC)

### Mapeo Excel → plantillas_respuesta

| Hoja Excel | Filas | tipo_workflow destino | problematica slug |
|---|---|---|---|
| `Rtas` `PAZ Y SALVO / PEDIDO PAZ Y SALVO` | 1 | ATENCION_CLIENTE | `PEDIDO_PAZ_Y_SALVO` |
| `Rtas` `IDENTIFICACION CLIENTE / PEDIR DOCUMENTO` | 1 | ATENCION_CLIENTE | `PEDIR_DOCUMENTO_CLIENTE` |
| `Rtas` `COMPROBANTE / *` | 2 | ATENCION_CLIENTE | `COMPROBANTE_*` |
| `Rtas` `ATENCION AL CLIENTE / *` | varios | ATENCION_CLIENTE | `CASO_*` |
| `Rtas` resto (37 más) | varios | ATENCION_CLIENTE | (mapping caso a caso) |
| `RTA DC` `Desconoce Rappi/FLB/Santander/Bogotá` | 4 | PQRS | `DESCONOCIMIENTO_*` (legal: estos sí son reclamos Datacrédito) |
| `RTA DC` `Pedido documentación / Cliente pide info / Cartera recuperada` | 3 | ATENCION_CLIENTE | `*` |

### Script idempotente

`backend/scripts/seed_plantillas_flexfintech.py`:
```python
"""Carga las plantillas de los Excel Flex/ en plantillas_respuesta (tenant FF).
UPSERT por (cliente_id, problematica) — re-ejecutar es seguro."""
PLANTILLAS = [
    {
        "problematica": "PEDIDO_PAZ_Y_SALVO",
        "tipo_workflow": "ATENCION_CLIENTE",
        "contexto": "Cliente solicita certificado de cancelación de deuda",
        "cuerpo": "📩 Hola, ¡gracias por contactarte con Flex Fintech! 😊\nPara solicitar...",
        "keywords": ["paz y salvo", "certificado de cancelación", "libre de deuda"],
    },
    # ... 49 más
]
```

### Detección automática

Agregar al `_DETECTION_RULES` de `plantilla_engine.py` los keywords para cada plantilla nueva. Detección matcheable por hojas operativas.

---

## F3 — Editor de destinatario + audit

### Problema
- `casos.py:616` hardcodea `caso["email_origen"]` como destinatario.
- Casos donde el adjunto pide "respondan a `nuevomail@otro.com`" obligan a edit manual + fwd manual.

### Diseño

```sql
-- Migración 18 (parte 2): override destinatario
ALTER TABLE pqrs_casos
  ADD COLUMN email_respuesta_override TEXT NULL;
COMMENT ON COLUMN pqrs_casos.email_respuesta_override IS
  'Si está seteado, los envíos usan este email como destinatario en lugar de email_origen.';
```

**Endpoint PATCH**:
```python
@router.patch("/casos/{caso_id}/destinatario")
async def cambiar_destinatario(
    caso_id: str, body: DestinatarioBody,
    current_user: TokenData = Depends(require_admin),  # admin + super_admin
    conn = Depends(get_db),
):
    # validar regex email
    # UPDATE pqrs_casos SET email_respuesta_override = $1
    # INSERT audit_log_respuestas accion='DESTINATARIO_EDITADO'
    #   metadata: {anterior: <email_origen actual>, nuevo: <body.email>, usuario_id}
    return {"ok": True}
```

**Modificación enviar-lote**:
```python
to = caso["email_respuesta_override"] or caso["email_origen"]
ok = zoho.send_reply(to, ...) or _send_via_smtp_fallback(to, ...)
# audit metadata agrega: {email_destino_final: to, fue_override: bool}
```

**Frontend** (otro agente): input editable en vista detalle del caso, visible solo a admins.

---

## F4 — Archivado SharePoint post-envío

### Problema
- Hoy no se archiva nada al enviar. SP solo se usa durante ingesta para adjuntos.
- Cliente pide carpeta `{cedula}_{YYYY-MM-DD}/` con: mail original + respuesta + adjuntos.

### Diseño

**A. Configurar SP en FlexFintech**

Extraer del enlace que pasó el user:
`https://flexfintechcompany.sharepoint.com/:f:/s/FlexFideicomiso/IgAuSUe12D8pTo2GV8Vdf07MAVocthqMhPsxEDNbgQaub38?...`
- Site path: `/sites/FlexFideicomiso`
- Folder ID (sharing token): `IgAuSUe12D8pTo2GV8Vdf07MAVocthqMhPsxEDNbgQaub38`

Resolver vía Graph:
```python
# 1. Site ID
GET /sites/flexfintechcompany.sharepoint.com:/sites/FlexFideicomiso
# 2. Drive default
GET /sites/{site-id}/drive
# 3. Decode sharing link a item ID
GET /shares/u!<base64-de-url>/driveItem
```

Después:
```sql
UPDATE config_buzones SET
  sharepoint_site_id = '<resolved-site-id>',
  sharepoint_base_folder = '<resolved-folder-path>'
WHERE cliente_id = '<FF-uuid>';
```

**B. Permisos Azure**
- App necesita `Sites.ReadWrite.All` o `Files.ReadWrite.All`.
- Si falta: tu acción en Azure portal + admin consent.

**C. Extender `SharePointEngineV2`**

```python
async def archivar_caso(self, caso: dict, mail_original_eml: bytes,
                        respuesta_html: str, adjuntos: list[tuple[str, bytes]]) -> str:
    """Crea carpeta {cedula}_{YYYY-MM-DD}/ y sube 3+ archivos.
    Devuelve el path SP completo."""
    cedula = caso["documento_peticionante"]
    fecha = caso["enviado_at"].strftime("%Y-%m-%d")
    folder_name = f"{cedula}_{fecha}"

    # 1. Crear/asegurar carpeta
    # 2. Subir mail_original.eml
    # 3. Subir respuesta.html (con CSS básico)
    # 4. Subir cada adjunto con su nombre original
    return folder_path
```

**D. Hook en `enviar-lote`**

```python
if ok:
    # ... UPDATE pqrs_casos SET borrador_estado='ENVIADO' ...
    # ... INSERT audit_log_respuestas ENVIADO_LOTE ...

    # Archivado SP (best-effort: si falla, log warning, NO romper envío)
    try:
        if sp_engine and caso["tipo_workflow"] == "PQRS":  # o ambos workflows
            sp_path = await sp_engine.archivar_caso(caso, mail_eml, html_resp, adj_data)
            await conn.execute(
                "UPDATE pqrs_casos SET metadata_especifica = jsonb_set(metadata_especifica, '{sp_archivo}', $1::jsonb) WHERE id = $2",
                json.dumps(sp_path), caso["id"],
            )
    except Exception as e:
        logger.warning(f"archivado SP falló caso {cid}: {e}")
```

**E. Recuperar el mail original como .eml**
- Graph: `GET /users/{email}/messages/{id}/$value` devuelve MIME crudo.
- Persistir el `external_msg_id` ya existente para poder pedirlo después.
- Si el mensaje fue movido a CERRADO (manual), el ID sigue válido — Graph resuelve.

---

## F5 — Cédula plana + mapeo email→cedula

### Cambios

```sql
-- Migración 18 (parte 3): persistir cédula
ALTER TABLE pqrs_casos
  ADD COLUMN documento_peticionante VARCHAR(20) NULL;

CREATE INDEX pqrs_casos_documento_idx ON pqrs_casos (documento_peticionante)
  WHERE documento_peticionante IS NOT NULL;

-- Mapeo histórico email→cedula (poblado desde Excel)
CREATE TABLE historico_email_cedula (
  email VARCHAR(255) PRIMARY KEY,
  cedula VARCHAR(20) NOT NULL,
  nombre VARCHAR(255),
  primera_vez TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  ultima_vez TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  fuente VARCHAR(50) DEFAULT 'excel-flex-2026-05-26'
);
```

### Backfill

Script `backend/scripts/seed_email_cedula_flexfintech.py`:
- Lee hojas `Mails`, `Reclamos`, `Colombia`, `Viejo_CO`, `CONSOLIDADO BOGOTA`.
- UPSERT en `historico_email_cedula`.

### Detección on-the-fly

Modificar el clasificador / worker para que, al recibir un email:
1. Buscar `historico_email_cedula` por sender email → si existe, asignar `documento_peticionante` automáticamente.
2. Si no existe, extraer con regex del cuerpo (lo que ya hace `clasificar_hibrido`).

---

## F6 — RAG backfill 2.900 históricos (Tier 2, esta semana)

Después del sprint operativo, cuando haya tiempo + Voyage pago:
- Script `backend/scripts/kb_backfill_excel.py` que importa cada caso histórico del Excel como `caso_enviado` virtual al KB de FlexFintech.
- Volumen: ~2900 docs × ~80 tokens promedio = ~232K tokens = $0.028 con Voyage.
- Beneficio: cuando Claude tiene que generar un borrador novedoso, ve 3-5 casos similares REALES con la gestión que el operador hizo → respuestas mucho más afinadas al estilo del cliente.

---

## Migración 18 unificada (estructura completa)

```sql
-- aequitas_infrastructure/database/18_flexfintech_dos_universos_y_destinatario.sql

-- Parte 1: tipo_workflow
ALTER TABLE config_buzones ADD COLUMN tipo_workflow VARCHAR(30) NOT NULL DEFAULT 'PQRS' CHECK (...);
ALTER TABLE pqrs_casos     ADD COLUMN tipo_workflow VARCHAR(30) NOT NULL DEFAULT 'PQRS' CHECK (...);
ALTER TABLE plantillas_respuesta ADD COLUMN tipo_workflow VARCHAR(30) NOT NULL DEFAULT 'PQRS' CHECK (...);
CREATE INDEX pqrs_casos_workflow_idx ON pqrs_casos (cliente_id, tipo_workflow);

-- Parte 2: override destinatario
ALTER TABLE pqrs_casos ADD COLUMN email_respuesta_override TEXT NULL;

-- Parte 3: cédula plana
ALTER TABLE pqrs_casos ADD COLUMN documento_peticionante VARCHAR(20) NULL;
CREATE INDEX pqrs_casos_documento_idx ON pqrs_casos (documento_peticionante) WHERE documento_peticionante IS NOT NULL;

-- Parte 4: histórico email→cedula
CREATE TABLE historico_email_cedula (...);
ALTER TABLE historico_email_cedula ENABLE ROW LEVEL SECURITY;
-- NOTA: esta tabla NO es tenant-scoped (es de FlexFintech pero data privada).
-- Se agrega columna cliente_id para mantener el patrón RLS.
ALTER TABLE historico_email_cedula ADD COLUMN cliente_id UUID NOT NULL REFERENCES clientes_tenant(id);
ALTER TABLE historico_email_cedula FORCE ROW LEVEL SECURITY;
CREATE POLICY historico_email_cedula_tenant_isolation ON historico_email_cedula
  USING (cliente_id::text = current_setting('app.current_tenant_id', true)
         OR current_setting('app.is_superuser', true) = 'true');

-- Grants
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pqrs_backend') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON historico_email_cedula TO pqrs_backend;
  END IF;
END $$;
```

---

## Plan ejecutable (orden propuesto)

| # | Tarea | Tiempo | Dep | Aplica a |
|---|---|---|---|---|
| 1 | Migración 18 (5 cambios DB) — local → staging → prod | 30 min | — | DB |
| 2 | Resolver SP site_id + folder_id de FlexFideicomiso vía Graph | 30 min | — | recon |
| 3 | Verificar/configurar permisos Azure Sites.ReadWrite.All | 15 min | — | (vos en portal) |
| 4 | Obtener Inbox folder_id de FlexFintech vía Graph + insertar 2da fila en config_buzones | 15 min | mig 18 | recon + INSERT |
| 5 | `seed_plantillas_flexfintech.py` (50 plantillas del Excel) | 1.5 h | mig 18 | code + ejecutar |
| 6 | `seed_email_cedula_flexfintech.py` (mapeo histórico) | 1 h | mig 18 | code + ejecutar |
| 7 | Modificar `plantilla_engine.detectar_problematica` con keywords nuevos | 1 h | seed plantillas | code |
| 8 | Endpoint `PATCH /casos/{id}/destinatario` + tests + modify `enviar-lote` | 2 h | mig 18 | code |
| 9 | Modificar `SharePointEngineV2.archivar_caso` + hook en `enviar-lote` | 3 h | sp config + perms | code |
| 10 | Modificar `master_worker_outlook` para iterar buzones por tipo_workflow + flow ATENCION_CLIENTE | 3 h | mig 18 + 2do buzon | code |
| 11 | Tests integración E2E: PQRS recibido → plantilla → enviar → SP archivado | 1.5 h | 8+9+10 | tests |
| 12 | Deploy local → staging → prod | 1 h | todo arriba | deploy |
| 13 | (post-sprint, Tier 2) Backfill RAG 2900 históricos | 2 h | Voyage pago | tarea separada |

**Total estimado:** 14-15 horas de trabajo. **Día completo intenso o 1.5 días normales.**

---

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|---|---|
| Permisos Azure no alcanzan (`Sites.ReadWrite.All`, `Mail.Send`) | Validar antes de codear F4/F9. Si faltan, ajustar en Azure portal — bloqueante. |
| SP archivado lento (~3s) si hay muchos adjuntos grandes | Best-effort: si falla, log warn, no rompe envío. Reproceso vía script batch nocturno. |
| 50 plantillas Excel pueden estar desactualizadas | Marcar todas como `is_active=TRUE` por default; admins desactivan las que no aplican vía dashboard. |
| Migración 18 — agregar 5 cosas en 1 SQL puede ser frágil si algo falla a mitad | DO block transaccional + ROLLBACK automático ante error. Probado en local antes de staging/prod. |
| Inbox del buzón Outlook tiene mucho spam / no-PQRS | El flow ATENCION_CLIENTE igual pasa por detección de problemática — si nada matchea, queda en SIN_PLANTILLA y no se envía solo. Admins revisan. |

---

## Decisiones pendientes del cliente (a confirmar antes de arrancar)

| # | Pregunta | Default sugerido |
|---|---|---|
| D1 | ¿`régimen_sla` FlexFintech → FINANCIERO o queda GENERAL? | GENERAL (no afecta atención al cliente; afecta PQRS si querés plazos SFC 8 días) |
| D2 | ¿El archivado SP aplica para ambos workflows (PQRS + ATENCION_CLIENTE) o solo PQRS? | Ambos (criterio: si se envió respuesta, se archiva) |
| D3 | ¿Las plantillas del Excel `Rtas` se cargan TODAS como `is_active=TRUE` o requieren revisión previa? | TODAS activas; admins desactivan después si hace falta |
| D4 | ¿Formato carpeta SP: `{cedula}_{YYYY-MM-DD}` o `{YYYY-MM-DD}_{cedula}`? | `{cedula}_{YYYY-MM-DD}` (orden alfabético = orden por cliente) |
| D5 | ¿Mail original como `.eml` o renderizado `.html`? | `.eml` (preserva headers, attachments embebidos, fidelidad legal) |
| D6 | ¿Backfill RAG (~2900 históricos) ahora o esperar payment Voyage? | Esperar payment + hacer después del sprint |
| D7 | ¿Los 612 casos viejos en backend FlexFintech se dejan como están (histórico) o se marcan como CERRADO masivo? | Dejar como están — son histórico, no se van a responder. Mañana arranca todo desde cero funcionalmente. |
| D8 | ¿Los códigos de agencia del Excel (15, 21, 64, 108…) tienen mapeo a nombres legibles? | Pendiente — si los conoces, los importamos al sistema como tags |

---

## Siguiente paso

**Esperar tus confirmaciones de D1-D8 (al menos las críticas: D1, D2, D3, D5) + tu OK general de la arquitectura.**

Cuando confirmes → arranco con paso #1 (Migración 18 local) y voy bloque por bloque, reportando al final de cada uno.
