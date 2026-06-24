# Sesión 2026-06-24 — Cierre RBAC Recovery/Arcas + limpieza de repo

> Bitácora que documenta el **fix RBAC del rol `abogado` (cliente Arcas / tenant
> Abogados Recovery)** —hecho 17–18/06, nunca había quedado en el Brain (solo en
> memorias)— y el **cierre del árbol de git** del 24/06.

## 1. Contexto: el rol `abogado` estaba huérfano

**"Arcas" / "Arcasa" = ARC S.A.S.** (`arcsas.com.co`). Sus usuarios NO tienen tenant
propio: viven dentro del tenant **`Abogados Recovery`**
(`effca814-b0b5-4329-96be-186c0333ad4b`, `abogadosrecovery.com`), provisionados con
rol **`abogado`**.

Gotcha de roles: el schema define `usuarios.rol` con default `'abogado'`, pero el
RBAC/frontend históricamente usaba `'analista'` para "abogado" → dos strings para el
mismo concepto. El rol `abogado` quedó huérfano:
- El frontend lo mandaba a la Bandeja admin (`/admin/casos`)…
- …pero el backend restringía esa ruta a admin/super → **403, "no ven nada"**.
- `/casos/enviados/historial` tampoco lo dejaba ver sus envíos.

Síntoma reportado por los abogados: **"no pueden ver la bandeja de Enviados"** y
después **"en la Bandeja no pueden ver nada"**.

## 2. Modelo decidido (con Nico)

Todo unificado en la **Bandeja** (rediseño `sesion_20260521_rediseno_dashboard_cult_ui.md`).
Cada uno ve **lo suyo**:
- `admin` / `super_admin`: Bandeja completa del tenant + todas las acciones.
- `abogado` (Recovery) = **operador de Bandeja**: ve SOLO su cartera asignada
  (`pqrs_casos.asignado_a = él`), responde casos; sin acciones admin.
- `analista` (Demo): conserva "Mis Casos" (live-feed), NO se toca.

Dato de escala: 1585/1587 casos Recovery están asignados; cada abogado tiene
~230–350 en su cartera. Por eso "Mis Casos"/SSE no servía (solo trae lo nuevo en
vivo; `/casos/borrador/pendientes` no filtra por `asignado_a`). La Bandeja
(paginada/buscable) sí.

## 3. Fix — Fase 1 (backend) — DESPLEGADA en prod

Hotfix quirúrgico sobre la imagen de prod (que está en `cdff3e6`/#16, ~8 commits
detrás de main), aplicado byte-preserving por el CRLF de los archivos de prod.

- **`/admin/casos`** (`admin.py` → `listar_casos_admin`): permite `abogado`/`analista`
  forzando `c.asignado_a = <usuario>` (ignora cualquier `asignado_a` del query: no
  pueden espiar la cartera de otro). admin/super siguen viendo todo el tenant.
- **`/stats/dashboard`** (`stats.py`): `es_abogado` ahora incluye `abogado` (antes
  solo `analista`) → el dashboard scope-a por cartera.
- **`/casos/enviados/historial`** (`casos.py`): revertido — se sacó `abogado` de
  `ROLES_VEN_TODO`, así abogado/analista ven SOLO sus propios envíos.

**Verificación e2e en prod:** abogado → 256 casos (su cartera, antes 403);
admin → 1590; enviados → 29. Sin regresiones (309 passed / ~12 fallos ambientales).

Commits en main: `aecac2d`, `3343d93`. Para ver Fase 1 los abogados solo recargan
(F5), sin re-login (su token ya dice `abogado`).

## 4. Fix — Fase 2a (frontend) — EN MAIN, PENDIENTE DE DEPLOY A PROD

Commit `5ea8c2b`. Build local OK, preflight hecho (`package.json` sin cambios →
reuse de deps).
- `frontend/src/app/page.tsx`: nav de operador `[Dashboard, Bandeja, Enviados]`
  (`esOperador = rol === "abogado"`).
- `frontend/src/components/ui/admin-bandeja.tsx`: oculta al operador los controles
  admin (checkboxes, botón Eliminar, botón "No PQRS").

**Fase 2b** (overlay `caso-detail-overlay.tsx`: ocultar asignar/reclasificar al
operador) → **diferida**; el backend ya lo bloquea con 403.

## 5. Chequeos colaterales

- **Zoho**: verificado healthy.
- **Kafka/Zookeeper**: caídos y vestigiales hace tiempo (`zookeeper_v2` no resuelve);
  el backend arranca "sin producer" y `master_worker` no usa Kafka. NO es regresión.

## 6. Cierre de repo (24/06)

Commit **`009afb5`** (pusheado a `origin/main`): bitácoras del sprint mayo
(`sesion_20260527_*`, `sesion_20260601_*`), updates de CHANGELOG/DEUDAS, y
`.gitignore` para `graphify-out/` (artefacto regenerable). Árbol **limpio**, `main`
a la par con `origin/main`.

## 7. Pendientes (NO de repo — son deploys)

1. **Fase 2a frontend → prod** (rebuild imagen `frontend_v2`). Esperando que los
   abogados confirmen que la Fase 1 ya les anda.
2. **DT-25 `/health` → prod** (resuelto en staging, falta llevarlo).
3. Confirmar con Paola Lombana las 8 plantillas Recovery + duplicado
   `ELIMINACION_CENTRALES_PAZ_SALVO` (ver DEUDAS).

Memorias relacionadas: `project-agentepqrs-arcas-recovery`,
`project-agentepqrs-deploy-preflight`, `project-agentepqrs-prod-kafka-vestigial`.
