# FlexFintech: reclasificación PQRS⇄AC + imágenes inline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que FlexFintech pueda (1) mover casos entre PQRS y Atención al Cliente en ambos sentidos desde la UI, y (2) ver las imágenes que llegan inline en el cuerpo del correo.

**Architecture:** Cambio B (reclasificación) = endpoint nuevo `PATCH /admin/casos/{id}/workflow` que flipea `tipo_workflow` + `es_pqrs`, deja señal de aprendizaje y audita; el overlay del frontend ramifica los botones por `tieneAC`. Cambio A (imágenes) = helper en el worker que reemplaza `<img src="cid:...">` por `data:base64` usando el `contentBytes` que Graph ya devuelve en `get_attachments_meta`, guardado en una clave aparte para no contaminar la clasificación. Cero migraciones de DB.

**Tech Stack:** FastAPI + asyncpg (backend), Microsoft Graph (worker Outlook), Next.js + React + zustand (frontend), pytest (mock de `conn` + `UserInToken`), Docker Compose local.

**Spec:** `docs/superpowers/specs/2026-06-17-flexfintech-reclasificacion-e-imagenes-inline-design.md`

**Son dos cambios independientes** → dos commits/PRs separados (B primero, A después). Tasks 1-2 = Cambio B; Task 3 = Cambio A; Task 4 = verificación + deploy.

---

### Task 0: Levantar el stack local para TDD

**Files:** ninguno (prep).

- [ ] **Step 1: Arrancar el stack**

Los tests corren dentro del contenedor `pqrs_v2_backend` (`docker exec ... python -m pytest`, igual que `scripts/verify.sh`). El stack está apagado, hay que levantarlo para desarrollar.

Run:
```bash
cd /home/casper/proyectos/AgentePQRS && docker compose up -d
```

- [ ] **Step 2: Esperar a que el backend esté healthy y confirmar el volumen de código**

Run:
```bash
docker compose ps | grep -E "pqrs_v2_backend|pqrs_v2_frontend"
docker exec pqrs_v2_backend python -c "import master_worker_outlook; print('worker import OK')"
grep -nA3 "pqrs_v2_backend\|backend:" /home/casper/proyectos/AgentePQRS/docker-compose.yml | grep -i "volumes\|/app\|./backend" | head
```
Expected: `pqrs_v2_backend` Up; el import imprime `worker import OK`; debe verse un bind mount `./backend:/app` (así los archivos de test nuevos aparecen en el contenedor sin rebuild). Si NO hay bind mount de `./backend`, después de crear cada archivo de test hay que `docker cp` o `docker compose restart backend` antes de correr pytest.

- [ ] **Step 3: Baseline verde**

Run:
```bash
docker exec pqrs_v2_backend python -m pytest -q
```
Expected: PASS (0 fallos) — baseline antes de empezar.

---

## Cambio B — Reclasificación bidireccional PQRS ⇄ ATENCION_CLIENTE

### Task 1: Endpoint backend `PATCH /admin/casos/{id}/workflow`

**Files:**
- Modify: `backend/app/api/routes/admin.py` (imports arriba; nuevo modelo + endpoint después de la línea 250, tras `marcar_feedback`)
- Test: `backend/tests/test_reclasificar_workflow.py` (crear)

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/tests/test_reclasificar_workflow.py`:

```python
"""Tests del endpoint PATCH /admin/casos/{id}/workflow (reclasificación PQRS⇄AC).

Unitarios: mockean conn + current_user. No tocan DB. Espejo de
test_destinatario_override.py.
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.routes.admin import ReclasificarWorkflowRequest, reclasificar_workflow
from app.core.security import UserInToken

TENANT_FF = "f7e8d9c0-b1a2-3456-7890-123456abcdef"
CASO_ID = "11111111-2222-3333-4444-555555555555"
USUARIO_ID = "66666666-7777-8888-9999-aaaaaaaaaaaa"


def _user(rol="admin", tenant=TENANT_FF):
    return UserInToken(usuario_id=USUARIO_ID, email="mica@flexfintech.com",
                       role=rol, tenant_uuid=tenant)


def _conn(caso_existe=True, tipo_actual="PQRS", tiene_ac=True):
    c = MagicMock()
    wf = [{"tipo_workflow": "PQRS"}]
    if tiene_ac:
        wf.append({"tipo_workflow": "ATENCION_CLIENTE"})
    c.fetch = AsyncMock(return_value=wf)
    if caso_existe:
        c.fetchrow = AsyncMock(return_value={
            "id": uuid.UUID(CASO_ID),
            "tipo_workflow": tipo_actual,
            "tipo_caso": "RECLAMO",
            "cliente_id": uuid.UUID(TENANT_FF),
        })
    else:
        c.fetchrow = AsyncMock(return_value=None)
    c.execute = AsyncMock(return_value="OK")
    return c


class TestPermisos:
    @pytest.mark.asyncio
    async def test_analista_403(self):
        body = ReclasificarWorkflowRequest(tipo_workflow="ATENCION_CLIENTE")
        with pytest.raises(HTTPException) as ei:
            await reclasificar_workflow(CASO_ID, body, _user(rol="analista"), _conn())
        assert ei.value.status_code == 403

    @pytest.mark.asyncio
    async def test_tenant_sin_ac_403(self):
        body = ReclasificarWorkflowRequest(tipo_workflow="ATENCION_CLIENTE")
        with pytest.raises(HTTPException) as ei:
            await reclasificar_workflow(CASO_ID, body, _user(), _conn(tiene_ac=False))
        assert ei.value.status_code == 403


class TestValidacion:
    @pytest.mark.asyncio
    async def test_workflow_invalido_400(self):
        body = ReclasificarWorkflowRequest(tipo_workflow="BANANA")
        with pytest.raises(HTTPException) as ei:
            await reclasificar_workflow(CASO_ID, body, _user(), _conn())
        assert ei.value.status_code == 400

    @pytest.mark.asyncio
    async def test_caso_no_encontrado_404(self):
        body = ReclasificarWorkflowRequest(tipo_workflow="ATENCION_CLIENTE")
        with pytest.raises(HTTPException) as ei:
            await reclasificar_workflow(CASO_ID, body, _user(), _conn(caso_existe=False))
        assert ei.value.status_code == 404


class TestReclasificacion:
    @pytest.mark.asyncio
    async def test_pqr_a_ac(self):
        conn = _conn(tipo_actual="PQRS")
        body = ReclasificarWorkflowRequest(tipo_workflow="ATENCION_CLIENTE")
        r = await reclasificar_workflow(CASO_ID, body, _user(), conn)
        assert r["ok"] is True
        assert r["tipo_workflow"] == "ATENCION_CLIENTE"
        # 1er execute = UPDATE pqrs_casos: tipo_workflow + es_pqrs=False
        upd = conn.execute.call_args_list[0]
        assert "UPDATE pqrs_casos" in upd.args[0]
        assert upd.args[1] == "ATENCION_CLIENTE"
        assert upd.args[2] is False
        # 3er execute = audit con metadata {anterior, nuevo}
        audit = conn.execute.call_args_list[2]
        assert "WORKFLOW_RECLASIFICADO" in audit.args[0]
        meta = json.loads(audit.args[3])
        assert meta == {"anterior": "PQRS", "nuevo": "ATENCION_CLIENTE"}

    @pytest.mark.asyncio
    async def test_ac_a_pqr(self):
        conn = _conn(tipo_actual="ATENCION_CLIENTE")
        body = ReclasificarWorkflowRequest(tipo_workflow="PQRS")
        r = await reclasificar_workflow(CASO_ID, body, _user(), conn)
        assert r["tipo_workflow"] == "PQRS"
        upd = conn.execute.call_args_list[0]
        assert upd.args[1] == "PQRS"
        assert upd.args[2] is True  # es_pqrs=True al levantar a PQRS
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `docker exec pqrs_v2_backend python -m pytest tests/test_reclasificar_workflow.py -v`
Expected: FAIL con `ImportError: cannot import name 'ReclasificarWorkflowRequest'`.

- [ ] **Step 3: Implementar el endpoint**

En `backend/app/api/routes/admin.py`, agregar `import json` arriba (junto a `import uuid`, línea 1):

```python
import json
import uuid
```

Después del endpoint `marcar_feedback` (tras la línea 250, antes de `eliminar_caso_no_pqrs`), agregar:

```python
_WORKFLOWS_VALIDOS = {"PQRS", "ATENCION_CLIENTE"}


class ReclasificarWorkflowRequest(BaseModel):
    tipo_workflow: str


@router.patch("/casos/{caso_id}/workflow")
async def reclasificar_workflow(
    caso_id: str,
    body: ReclasificarWorkflowRequest,
    current_user: UserInToken = Depends(get_current_user),
    conn = Depends(get_db_connection),
) -> Dict[str, Any]:
    """Mueve un caso entre PQRS y ATENCION_CLIENTE (bidireccional).

    - "No es PQR" → ATENCION_CLIENTE (es_pqrs=False).
    - "Sí es PQR" → PQRS (es_pqrs=True), "levanta" el caso al flujo legal.

    Solo admin/super_admin. Solo tenants con AC habilitado (mismo criterio que
    /auth/me). Deja señal de aprendizaje en pqrs_clasificacion_feedback y audita
    en audit_log_respuestas (WORKFLOW_RECLASIFICADO). NO regenera borrador.
    """
    if current_user.role not in ('admin', 'super_admin'):
        raise HTTPException(status_code=403, detail="Solo administradores")

    nuevo = (body.tipo_workflow or "").strip().upper()
    if nuevo not in _WORKFLOWS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"tipo_workflow inválido: {body.tipo_workflow!r}")

    es_super = current_user.role == 'super_admin'

    # Guard: el tenant debe tener AC habilitado (config_buzones o plantillas AC).
    # Sin esto, mover a AC en un tenant sin AC dejaría el caso fuera de toda vista.
    if es_super:
        wf_rows = await conn.fetch(
            "SELECT tipo_workflow FROM config_buzones WHERE is_active = TRUE "
            "UNION SELECT DISTINCT tipo_workflow FROM plantillas_respuesta WHERE is_active = TRUE"
        )
    else:
        wf_rows = await conn.fetch(
            "SELECT tipo_workflow FROM config_buzones WHERE cliente_id = $1::uuid AND is_active = TRUE "
            "UNION SELECT DISTINCT tipo_workflow FROM plantillas_respuesta WHERE cliente_id = $1::uuid AND is_active = TRUE",
            uuid.UUID(current_user.tenant_uuid),
        )
    if "ATENCION_CLIENTE" not in {row["tipo_workflow"] for row in wf_rows if row["tipo_workflow"]}:
        raise HTTPException(status_code=403, detail="El tenant no tiene Atención al Cliente habilitado")

    row = await conn.fetchrow(
        "SELECT id, tipo_workflow, tipo_caso, cliente_id FROM pqrs_casos "
        "WHERE id = $1::uuid AND ($2 OR cliente_id = $3::uuid)",
        uuid.UUID(caso_id), es_super, uuid.UUID(current_user.tenant_uuid),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    anterior = row["tipo_workflow"]
    es_pqrs_flag = (nuevo == "PQRS")

    await conn.execute(
        "UPDATE pqrs_casos SET tipo_workflow = $1, es_pqrs = $2, updated_at = NOW() WHERE id = $3::uuid",
        nuevo, es_pqrs_flag, uuid.UUID(caso_id),
    )
    await conn.execute(
        """INSERT INTO pqrs_clasificacion_feedback
              (caso_id, cliente_id, clasificacion_original, clasificacion_correcta, es_pqrs, marcado_por)
           VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::uuid)""",
        uuid.UUID(caso_id), row["cliente_id"], row["tipo_caso"], nuevo,
        es_pqrs_flag, uuid.UUID(current_user.usuario_id),
    )
    await conn.execute(
        """INSERT INTO audit_log_respuestas (caso_id, usuario_id, accion, metadata)
           VALUES ($1::uuid, $2::uuid, 'WORKFLOW_RECLASIFICADO', $3)""",
        uuid.UUID(caso_id), uuid.UUID(current_user.usuario_id),
        json.dumps({"anterior": anterior, "nuevo": nuevo}),
    )
    return {"ok": True, "tipo_workflow": nuevo}
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `docker exec pqrs_v2_backend python -m pytest tests/test_reclasificar_workflow.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Suite completa verde**

Run: `docker exec pqrs_v2_backend python -m pytest -q`
Expected: PASS (baseline + 7 nuevos).

- [ ] **Step 6: Commit**

```bash
cd /home/casper/proyectos/AgentePQRS
git add backend/app/api/routes/admin.py backend/tests/test_reclasificar_workflow.py
git commit -m "feat(backend): PATCH /admin/casos/{id}/workflow — reclasificar PQRS⇄AC con audit y señal de aprendizaje"
```

---

### Task 2: Frontend — botones de reclasificación en el overlay

**Files:**
- Modify: `frontend/src/components/ui/caso-detail-overlay.tsx`

Contexto verificado: `isAdmin` (línea 22), `esAC` (línea 52), `handleNoPQRS` (línea 149), botón "Marcar NO PQRS" (líneas 916-934). El hook `useTenantWorkflows()` devuelve `{ tieneAC }`. **Importante:** el botón "No PQRS" actual existe para TODOS los tenants (Recovery/Demo lo usan para descartar). Hay que ramificar por `tieneAC`: FF mueve a AC, los demás conservan el descarte actual.

- [ ] **Step 1: Importar el hook y agregar estado**

En `frontend/src/components/ui/caso-detail-overlay.tsx`, agregar import tras la línea 7:

```tsx
import { usePlantillas } from "@/hooks/usePlantillas";
import { useTenantWorkflows } from "@/hooks/useTenantWorkflows";
```

Tras la línea 23 (`const canReassign = ...`), agregar:

```tsx
  const { tieneAC } = useTenantWorkflows();
```

Tras la línea 29 (`const [feedbackDone, setFeedbackDone] = useState(false);`), agregar:

```tsx
  const [reclasificando, setReclasificando] = useState(false);
```

- [ ] **Step 2: Agregar el handler de reclasificación**

Justo después de `handleNoPQRS` (tras la línea 162, antes de `handleGenerate`), agregar:

```tsx
  const handleReclasificar = async (nuevoWorkflow: "PQRS" | "ATENCION_CLIENTE") => {
    if (!casoId || reclasificando) return;
    setReclasificando(true);
    try {
      await api.patch(`/admin/casos/${casoId}/workflow`, { tipo_workflow: nuevoWorkflow });
      onStatusChange?.(casoId, { tipo_workflow: nuevoWorkflow });
      onClose();
    } catch (e) {
      console.error("Error reclasificando caso", e);
    } finally {
      setReclasificando(false);
    }
  };
```

- [ ] **Step 3: Reemplazar el bloque de botones del footer (izquierda)**

Reemplazar el bloque actual (líneas 916-934, los dos `{isAdmin && ...}` dentro del primer `<div className="agente gap-3">`) por:

```tsx
                  {/* AC: levantar el caso al flujo PQRS */}
                  {isAdmin && esAC && (
                    <button
                      onClick={() => handleReclasificar("PQRS")}
                      disabled={reclasificando}
                      className="agente items-center gap-2 px-4 py-2 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 hover:bg-emerald-500/15 text-xs font-bold rounded-xl transition-all disabled:opacity-50"
                    >
                      {reclasificando
                        ? <div className="w-3 h-3 border-2 border-emerald-400/50 border-t-emerald-400 rounded-full animate-spin" />
                        : <CheckCircle className="w-4 h-4" />
                      }
                      Sí es PQR
                    </button>
                  )}
                  {/* PQRS + tenant con AC (FF): mover a Atención al Cliente */}
                  {isAdmin && !esAC && tieneAC && (
                    <button
                      onClick={() => handleReclasificar("ATENCION_CLIENTE")}
                      disabled={reclasificando}
                      className="agente items-center gap-2 px-4 py-2 bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/15 text-xs font-bold rounded-xl transition-all disabled:opacity-50"
                    >
                      {reclasificando
                        ? <div className="w-3 h-3 border-2 border-red-400/50 border-t-red-400 rounded-full animate-spin" />
                        : <XCircle className="w-4 h-4" />
                      }
                      No es PQR → Atención al cliente
                    </button>
                  )}
                  {/* PQRS + tenant SIN AC (Recovery/Demo): descarte clásico */}
                  {isAdmin && !esAC && !tieneAC && !feedbackDone && data.es_pqrs !== false && (
                    <button
                      onClick={handleNoPQRS}
                      disabled={feedbackLoading}
                      className="agente items-center gap-2 px-4 py-2 bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/15 text-xs font-bold rounded-xl transition-all disabled:opacity-50"
                    >
                      {feedbackLoading
                        ? <div className="w-3 h-3 border-2 border-red-400/50 border-t-red-400 rounded-full animate-spin" />
                        : <XCircle className="w-4 h-4" />
                      }
                      Marcar NO PQRS
                    </button>
                  )}
                  {isAdmin && !esAC && !tieneAC && (feedbackDone || data.es_pqrs === false) && (
                    <p className="text-xs text-muted-foreground agente items-center gap-2">
                      <XCircle className="w-4 h-4 text-red-400" />
                      Marcado como No PQRS
                    </p>
                  )}
```

(`CheckCircle` y `XCircle` ya están importados en la línea 5 — no agregar imports de íconos.)

- [ ] **Step 4: Typecheck**

Run: `docker exec pqrs_v2_frontend npx tsc --noEmit`
Expected: sin errores en `caso-detail-overlay.tsx`. (Si `tsc` no está disponible en el contenedor, correr `cd frontend && npx tsc --noEmit` en local.)

- [ ] **Step 5: Verificación manual en el browser**

Con el stack arriba (frontend en `:3002`), logueado como admin de FlexFintech:
1. Abrir un caso en bandeja **PQRS** → el footer muestra **"No es PQR → Atención al cliente"**. Click → el caso desaparece de PQRS y aparece en la sección **Atención al cliente**.
2. Abrir un caso en **Atención al cliente** → footer muestra **"Sí es PQR"**. Click → el caso aparece en la bandeja **PQRS**.
3. (Regresión) Logueado como admin de **Abogados Recovery** → el botón sigue siendo **"Marcar NO PQRS"** (descarte clásico), sin botón de mover a AC.

- [ ] **Step 6: Commit**

```bash
cd /home/casper/proyectos/AgentePQRS
git add frontend/src/components/ui/caso-detail-overlay.tsx
git commit -m "feat(frontend): botones reclasificar PQRS⇄AC en el overlay (gateados por tieneAC)"
```

---

## Cambio A — Imágenes inline del cuerpo (base64)

### Task 3: Helper `_inline_images_a_base64` + wiring en el worker

**Files:**
- Modify: `backend/master_worker_outlook.py` (constantes ~línea 242; helper tras `_download_attachments_inline` ~línea 309; call site ~línea 531; INSERT AC línea 375; INSERT PQRS línea 584)
- Test: `backend/tests/test_inline_images.py` (crear)

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/tests/test_inline_images.py`:

```python
"""Tests del helper de imágenes inline del worker (cid: → data:base64).

Unitarios sobre función pura. Corre dentro del contenedor (sys.path /app).
"""
from __future__ import annotations

import sys
sys.path.insert(0, "/app")
from master_worker_outlook import _inline_images_a_base64

# contentBytes "QUJD" == base64 de "ABC"


def test_reemplaza_cid_por_base64():
    em = {
        "body": '<p>Hola</p><img src="cid:logo001"> fin',
        "attachments": [
            {"name": "logo.png", "contentId": "logo001", "isInline": True,
             "contentType": "image/png", "contentBytes": "QUJD"},
        ],
    }
    out = _inline_images_a_base64(em, "OUTLOOK")
    assert "data:image/png;base64,QUJD" in out
    assert "cid:logo001" not in out


def test_contentid_con_angle_brackets():
    em = {
        "body": '<img src="cid:img@x.com">',
        "attachments": [
            {"contentId": "<img@x.com>", "contentType": "image/jpeg",
             "contentBytes": "QUJD", "isInline": True},
        ],
    }
    out = _inline_images_a_base64(em, "OUTLOOK")
    assert "data:image/jpeg;base64,QUJD" in out


def test_cid_sin_match_queda_intacto():
    em = {"body": '<img src="cid:noexiste">', "attachments": []}
    assert "cid:noexiste" in _inline_images_a_base64(em, "OUTLOOK")


def test_zoho_no_se_toca():
    em = {"body": '<img src="cid:x">',
          "attachments": [{"contentId": "x", "contentBytes": "QQ==", "contentType": "image/png"}]}
    assert _inline_images_a_base64(em, "ZOHO") == '<img src="cid:x">'


def test_imagen_sobre_cap_se_saltea():
    big = "A" * 3_000_000
    em = {"body": '<img src="cid:big">',
          "attachments": [{"contentId": "big", "contentBytes": big,
                           "contentType": "image/png", "isInline": True}]}
    out = _inline_images_a_base64(em, "OUTLOOK")
    assert "cid:big" in out
    assert "data:image" not in out


def test_sin_cid_devuelve_igual():
    em = {"body": "<p>sin imagenes</p>", "attachments": []}
    assert _inline_images_a_base64(em, "OUTLOOK") == "<p>sin imagenes</p>"
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `docker exec pqrs_v2_backend python -m pytest tests/test_inline_images.py -v`
Expected: FAIL con `ImportError: cannot import name '_inline_images_a_base64'`.

- [ ] **Step 3: Implementar el helper**

En `backend/master_worker_outlook.py`, tras la definición de `_RE_CEDULA` (línea 242) agregar:

```python
# Imágenes inline: <img src="cid:...">. Cap ~2 MB decodificado (~2.8M chars b64).
_RE_CID = re.compile(r'cid:([^"\'>\s)]+)', re.IGNORECASE)
_INLINE_MAX_B64 = 2_800_000
```

Tras `_download_attachments_inline` (después de la línea 308, antes de `procesar_atencion_cliente`), agregar:

```python
def _inline_images_a_base64(em, prov):
    """Reemplaza <img src="cid:..."> por data:base64 usando el contentBytes que
    Graph ya devuelve en get_attachments_meta. Devuelve el cuerpo reescrito.

    Solo OUTLOOK (FF usa Graph; Zoho fuera de alcance). Best-effort: si una
    imagen no matchea o supera el cap, se deja el cid: intacto. NUNCA propaga.
    Sprint imágenes inline 2026-06-17.
    """
    body = em.get('body') or ''
    if prov != 'OUTLOOK' or 'cid:' not in body.lower():
        return body
    try:
        mapa = {}
        for att in (em.get('attachments') or []):
            cid = (att.get('contentId') or '').strip().strip('<>').strip()
            b64 = att.get('contentBytes')
            if not cid or not b64:
                continue
            if len(b64) > _INLINE_MAX_B64:
                logger.warning(f"inline image {cid} supera cap ({len(b64)} chars b64), se saltea")
                continue
            ctype = att.get('contentType') or 'application/octet-stream'
            mapa[cid] = f'data:{ctype};base64,{b64}'

        if not mapa:
            return body

        def _repl(m):
            cid = m.group(1).strip().strip('<>').strip()
            return mapa.get(cid, m.group(0))

        return _RE_CID.sub(_repl, body)
    except Exception as e:
        logger.warning(f"_inline_images_a_base64 falló, body intacto: {e}")
        return body
```

- [ ] **Step 4: Correr el test del helper y verificar que pasa**

Run: `docker exec pqrs_v2_backend python -m pytest tests/test_inline_images.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Wirear el call site y los dos INSERT**

(a) En el loop `for em in parsed_emails:`, tras el chequeo de cutoff (después de la línea 530 `continue`) y ANTES del comentario del dispatcher (línea 532), agregar:

```python
                    # Imágenes inline (cid:) → base64 embebido para el render del
                    # frontend. En clave aparte: NO contamina em['body'] (que usa
                    # la clasificación / el prompt de Claude). Best-effort.
                    em['cuerpo_html'] = _inline_images_a_base64(em, prov)
```

(b) En el INSERT PQRS (línea 584), cambiar el 4º valor de `em['body']` a `em['cuerpo_html']`:

```python
                        c_id, em['sender'], em['subject'], em['cuerpo_html'], 'ABIERTO', resultado.prioridad.value, dt, resultado.tipo.value, venc, documento, (em['id'] or '').strip() or None, asignado_a, fecha_asignacion
```

(c) En `procesar_atencion_cliente`, el INSERT AC (línea 375), cambiar el 4º valor de `em['body']` a `em.get('cuerpo_html') or em['body']` (el `.get` con fallback porque AC puede llamarse desde un path donde la clave ya esté seteada por el call site; el fallback protege si algún test la invoca directo):

```python
        c_id, em['sender'], em['subject'], em.get('cuerpo_html') or em['body'], dt,
```

(Las líneas 343/352/392 de `procesar_atencion_cliente` siguen usando `em['body']` original — correcto, la clasificación y el borrador NO deben ver el base64.)

- [ ] **Step 6: Suite completa verde**

Run: `docker exec pqrs_v2_backend python -m pytest -q`
Expected: PASS (incluye los 6 nuevos; sin regresiones en `test_procesar_atencion_cliente.py`).

- [ ] **Step 7: Commit**

```bash
cd /home/casper/proyectos/AgentePQRS
git add backend/master_worker_outlook.py backend/tests/test_inline_images.py
git commit -m "feat(worker): embeber imágenes inline (cid:) como base64 en cuerpo para render en plataforma"
```

---

### Task 4: Verificación integral + deploy

**Files:** ninguno (verificación + operación).

- [ ] **Step 1: Loop de verificación local**

Run: `cd /home/casper/proyectos/AgentePQRS && scripts/verify.sh --local-only`
Expected: pytest 0 fallos + backend `/health` ok. Exit 0.

- [ ] **Step 2: Verificación end-to-end manual (imágenes)**

Si hay un caso real de FF con imagen inline (ej. el reportado por Mica), reprocesarlo o esperar un correo nuevo y confirmar en el detalle que la imagen se ve. Si no hay correo a mano, la cobertura unit del helper + el render existente de `data:` URIs en el iframe es suficiente para mergear; dejar nota para confirmar con el próximo correo real.

- [ ] **Step 3: Preflight de deploy frontend**

Run: `cd /home/casper/proyectos/AgentePQRS && scripts/verify.sh --check-package-json`
Expected: diff de `frontend/package.json` local vs container. Decidir reuse vs rebuild de imagen frontend según el resultado (no agregamos dependencias nuevas → debería ser reuse).

- [ ] **Step 4: Deploy (ventana >18:00, lo dispara Nico)**

Regla de la casa: los cambios se aplican **después de las 18:00** para no cortar servicio. Secuencia: **staging** (`15.229.114.148`) → validar → **prod** (`18.228.54.9`). Tras `git pull` en cada host, **restaurar `docker-compose.yml` del backup** (no comitear cambios sobre ese archivo). El backend y el worker (`master_worker`) requieren restart para tomar el código nuevo; el frontend según el preflight (reuse vs rebuild). Correr `scripts/verify.sh --prod-only` después.

- [ ] **Step 5: PRs**

Abrir dos PRs (o uno con dos commits claros) a `main`: Cambio B (reclasificación) y Cambio A (imágenes). Branch desde `main`, no sobre `loop-verificacion`.

---

## Notas de verificación contra el spec

- Reclasificación PQR→AC y AC→PQR: Task 1 (endpoint) + Task 2 (UI). ✅
- Señal de aprendizaje en ambas direcciones: Task 1 Step 3 (INSERT `pqrs_clasificacion_feedback`). ✅
- Audit `WORKFLOW_RECLASIFICADO`: Task 1 Step 3. ✅
- Guard "tiene AC" + no romper descarte de Recovery/Demo: Task 1 (403 backend) + Task 2 (ramificación por `tieneAC`). ✅
- Imágenes inline base64, solo Outlook, sin contaminar clasificación: Task 3 (clave `cuerpo_html` aparte). ✅
- Caps / best-effort: Task 3 Step 3 (`_INLINE_MAX_B64`, try/except). ✅
- Cero migraciones: confirmado, no hay tasks de DB. ✅
- Guard del borrado "No PQRS" scopeado por workflow: **mitigado por diseño** — al mover a AC el caso queda con `tipo_workflow='ATENCION_CLIENTE'`, y la vista/borrado "No PQRS" vive en la bandeja PQRS (filtrada por workflow), así que no lo alcanza. Confirmar visualmente en Task 2 Step 5.
```
