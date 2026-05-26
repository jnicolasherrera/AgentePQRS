# Sesión 2026-05-21 — Rediseño dashboard frontend con cult-ui + shadcn

Rama: `feature/dashboard-redesign-cult-ui` (creada desde `main`).
Objetivo: rediseñar el `frontend/` (dashboard) alineándolo a la marca FlexLegal,
integrando cult-ui (registry de componentes estilo shadcn).

## Decisiones del usuario
- **Integración cult-ui**: vía init de shadcn + registry CLI (no `git clone`).
- **Rama**: nueva desde `main` (no sobre `release/tutelas-2026-05-07`).
- **Tema dashboard**: CLARO + cabecera navy (como el panel admin de prod
  `flexlegal.com.ar/admin`), no el oscuro actual ni el navy del landing.

## Paleta y tipografía de marca (fuente de verdad)
Extraídas del **fuente del landing** = `pqrs-landing/src/app/globals.css` + `layout.tsx`
(ese repo ES flexlegal.com.ar / flexpqr). No scrape.
- Primary (Persian Blue): `#035aa7`
- Navy / background dark: `#021f59` · Surface: `#011640`
- Cyan accent: `#06b6d4` · Gradient: `#035aa7 → #06b6d4 → #93c5fd`
- Tipografía: **Inter** (300–900) vía `next/font/google`.

## Cambios aplicados en `frontend/`
1. `components.json` — nuevo (shadcn, Tailwind v4, base radix, css=`src/app/globals.css`,
   aliases `@/components`, `@/lib/utils`, etc.). Lo escribió `shadcn init`.
2. `src/lib/utils.ts` — nuevo, helper `cn` (clsx + tailwind-merge).
3. `src/components/ui/button.tsx` — componente base shadcn (prueba del pipeline).
4. `src/app/globals.css` — **reescrito el bloque de tokens**: sistema completo
   `:root` (tema claro de marca) + `.dark` (navy del landing) + `@theme inline`
   mapeando tokens shadcn (--background, --card, --primary, --border, --radius,
   charts, --header navy, etc.). Se preservaron utilidades existentes
   (`glass-panel`, `glow-blob`, scrollbars, skeleton, `agente-*`).
   Body ahora usa `var(--background)`/`var(--foreground)` (antes forzaba oscuro).
   Backup en `/tmp/globals.css.bak`.
5. `src/app/layout.tsx` — Inter con `variable: --font-inter` (pesos 300–900),
   body usa `font-sans antialiased`.
6. `package.json` / `package-lock.json` — +`class-variance-authority`,
   +`tw-animate-css`, +`radix-ui` (clsx/tailwind-merge/lucide-react ya estaban).

Pipeline cult-ui verificado: `npx shadcn view https://www.cult-ui.com/r/<comp>.json`
resuelve OK. Para agregar componentes: `npx shadcn add https://www.cult-ui.com/r/<comp>.json`.

## Quirks del entorno (importante para próximas sesiones)
- `frontend/node_modules` y `frontend/.next` del host eran **stubs root vacíos**
  (los crea el contenedor `pqrs_v2_frontend`, que usa volúmenes anónimos para
  esas rutas). Se apartaron sin sudo a `.node_modules_root_stub` y `.next_root_stub`
  (renombrar funciona porque `frontend/` es de casper). Luego `npm install` local
  como casper poblá node_modules (684M). **No afecta al contenedor** (usa su volumen).
- El contenedor corre `npm start` = `next start` (build de prod, **sin hot-reload**).
  Para iterar el rediseño se usa **`next dev` local** en `localhost:3010`.
- gstack browse necesita `bun` (en `~/.bun/bin`, no en PATH) y los navegadores de
  Playwright (`npx playwright install chromium`).

## Estado de la rama release (para no perder nada)
- Al salir de `release/tutelas-2026-05-07` se stasheó SOLO `.gitignore`
  (diferí­a y bloqueaba el checkout). **Pendiente**: `git stash pop` al volver a
  esa rama para recuperar el ajuste de `.gitignore` (ignora docker-compose.override.yml,
  certs `.key`/`.orig`).

## Migración del shell (page.tsx) — HECHO 2026-05-21
Aclaración: el screenshot del usuario ("Panel admin", nav arriba) es el **panel
superadmin de PROD** (otro codebase). El `frontend/` local es el **dashboard
operativo con sidebar izquierdo**. Adaptación de "claro + cabecera navy":
- Raíz: `bg-background-dark text-white` → `bg-background text-foreground` (claro).
- **Sidebar = banda navy** de marca: `glass-panel` → `bg-header text-white`
  (`--header` = `#021f59`). Nav activo en `bg-primary` (Persian Blue), inactivo
  `text-white/60`. Logo con acento `text-brand-cyan`.
- **Header de contenido = claro**: `text-foreground`, subtítulo `text-muted-foreground`,
  bordes `border-border`, selector cliente y pill usuario sobre `bg-card`.
- Compila limpio (GET / y /login → 200).

## gstack browse (screenshots) — NO funciona en esta máquina; usar workaround
- CachyOS no está soportado por Playwright (baja build fallback ubuntu24.04-x64).
  La descarga del browser llega al 100% pero **la extracción del zip falla**: deja
  solo ABOUT/LICENSE, sin el ejecutable. Probado con chromium full y headless-shell
  rev 1208 (la que pide pw 1.58.2). Skew adicional: el binario `dist/browse` se
  reconstruyó con `./setup` pero igual depende del browser de Playwright roto.
- **WORKAROUND que SÍ funciona**: hay Chrome/Chromium del sistema
  (`/usr/bin/chromium`, `/usr/bin/google-chrome-stable`, `/usr/bin/brave`).
  Script playwright con `executablePath: "/usr/bin/chromium"` saca screenshots OK.
  El script debe correr DESDE `~/.claude/skills/gstack/` para resolver `playwright`
  de su node_modules (node resuelve módulos por ubicación del script, no por cwd).
  `bun` debe estar en PATH (`export PATH="$HOME/.bun/bin:$PATH"`).
- Para screenshot del dashboard (requiere auth): inyectar en localStorage la key
  `pqrs-v2-auth` = `{"state":{"token":"...","isAuthenticated":true,"user":{...rol:"super_admin",debe_cambiar_password:false}},"version":0}`
  vía `context.addInitScript` antes del goto.

## Resultado visual (2026-05-21)
- Login: ya estaba navy on-brand (no requirió cambios). `/tmp/redesign-login.png`.
- Dashboard shell: sidebar navy + contenido claro = OK, según la dirección elegida.
  `/tmp/redesign-dashboard.png`. Centro vacío porque los tabs aún no migrados +
  API 401 con token falso.

## Migración tab Dashboard (dashboard-metrics) — HECHO 2026-05-21
Estrategia clave (reutilizable para los demás tabs):
- **Redefinir las utilidades compartidas `glass-panel`/`glass-kpi` en globals.css a
  superficies CLARAS** (`var(--card)` + `var(--border)` + sombra navy suave). Migra
  todas las superficies de una. Se agregó `.dark .glass-panel`/`.dark .glass-kpi` con
  el glass navy original (para la variante dark).
- En el componente, `replace_all` de clases oscuras → tokens:
  `text-white`→`text-foreground`; `text-slate-300`→`text-foreground/80`;
  `text-slate-400/500`→`text-muted-foreground`; `text-slate-600/700`→`text-muted-foreground/60|40`;
  `bg-white/5`→`bg-muted`; `hover:bg-white/10`→`hover:bg-secondary`;
  `bg-white/[0.02|0.03]`→`bg-muted/30|40`; `border-white/5|10`→`border-border`;
  `divide-white/5`→`divide-border`; `text-{color}-200/80`→`text-{color}-700`.
- Acentos de color (blue/red/orange/... -400/-500) se dejan, leen bien en claro.
- Compila limpio. Screenshot: `_rediseno_shots/03_dashboard_metrics.png` (mockeando
  las 3 APIs: `/stats/dashboard`, `/casos/metricas/respuestas`, `/admin/clientes`).

NOTA: en dev local `NEXT_PUBLIC_API_URL` está undefined (no hay `.env.local` en
frontend/) → las APIs dan 404. Para datos reales habría que apuntar a `localhost:8001`
(backend del contenedor) y resolver CORS, o seguir mockeando para screenshots.

Screenshots en `_rediseno_shots/` (gitignored): 01_login, 02_dashboard_shell,
03_dashboard_metrics.

## Consolidación IA: unificación Casos → Bandeja — HECHO 2026-05-21
Análisis funcional (Casos/live-feed vs Bandeja/admin-bandeja vs Triaje del Dashboard):
había solapamiento en rol admin. Decisión del usuario:
- **Unificar en "Bandeja"**: el `caso-detail-overlay` que Bandeja ya abre al clickear
  una fila YA permite responder (borrador, IA, envío con contraseña). Se eliminó la
  pestaña "Casos" del admin. Tabs admin ahora: Dashboard, Bandeja, Enviados,
  Rendimiento, Configuración. Analista conserva "Mis Casos" (live-feed).
- Triaje del Dashboard: queda como atajo → botón "Ver todos" navega a Bandeja
  (prop `onVerTodos` en DashboardMetrics; en page.tsx va a Bandeja o "Mis Casos" según rol).
- Se quitó import `Radio` sin uso. Se perdió para admin el "responder en lote a 10"
  de live-feed (Bandeja responde de a uno desde el detalle) — acorde a la decisión.

## Migración a CLARO de TODAS las pestañas — HECHO 2026-05-21
Script `/tmp/swap.mjs` aplicó swaps de clases oscuras→tokens en los 14 componentes de
`src/components/ui/` (text-white→text-foreground, text-slate-*→muted/foreground,
bg-white/*→muted|secondary|card, border/divide/ring-white→*-border, hex oscuros→bg-card).
IMPORTANTE: el script NO toca estilos inline. Hubo que arreglar a mano:
- `caso-detail-overlay.tsx` líneas 230 y 490: `style={{background:"rgba(11,14,20,.98)"}}`
  → `var(--background)` (contenedor) y `var(--card)` (panel comentarios).
Se dejaron a propósito:
- Scrims de modales `rgba(0,0,0,0.8)` (admin-bandeja:387, live-feed:519) — backdrops.
- Modales de auth navy `#021f59`/`#035aa7` (change-password, ForceChange, ReAuth) —
  on-brand como el login. Si se quieren claros, es un cambio aparte.

Verificado por screenshot (todo compila, GET / 200):
01_login, 02_dashboard_shell, 03_dashboard_metrics, 04_bandeja, 05_enviados,
06_rendimiento, 07_configuracion, 08_detalle_caso — todos en `_rediseno_shots/`.

## Rediseño DASHBOARD v2 (datos + layout Operacional) — HECHO 2026-05-21

### Hallazgo de datos (clave)
- `tipo_caso` se asigna UNA vez al ingresar (clasificador IA en
  `backend/master_worker_outlook.py:261`, `clasificar_hibrido`) y **NUNCA cambia**.
  No hay UPDATE de tipo_caso, ni endpoint/UI de reclasificar/escalar.
- ⇒ "Conversión PQR→Tutela" NO es un evento real en el sistema. Decisión del usuario:
  mostrar la **métrica real de ingresos** (no inventar conversión). Escalado real
  (botón "Escalar a tutela" + tracking) queda como feature futura si se quiere.

### Backend redeployado y end-to-end verificado — 2026-05-26
- `docker compose up -d --build backend_v2` reconstruyó la imagen con stats.py nuevo.
- CORS en `backend/app/main.py:42` ahora incluye `http://localhost:3010` (dev local).
- `frontend/.env.local` (gitignored) con `NEXT_PUBLIC_API_URL=http://localhost:8001`.
- Login real (`admin@flexpqr.local` / `Admin2026!`) → KPIs reales: 12 activos, 8 vencidos,
  2 por vencer, 19 total, 15.8% resueltos, 3 tutelas (16%). Screenshot: `11_dashboard_real.png`.

### Backend (backend/app/api/routes/stats.py)
- `/dashboard`: +`por_vencer` (vence ≤48h, no cerrado) y +`activos` (ABIERTO+EN_PROCESO).
- `/rendimiento/tendencia`: +`tutelas` por día (tipo_caso='TUTELA', ambas ramas
  super/tenant). Ahora devuelve `{fecha, recibidos, cerrados, tutelas}`.
- OJO: el contenedor `pqrs_v2_backend` corre el código viejo; estos campos solo
  llegan tras rebuild/restart. El frontend degrada bien si faltan (fallbacks:
  activos=abiertos+en_proceso, por_vencer/tutelas=0).

### Frontend (dashboard-metrics.tsx) — REESCRITO completo
Layout Operacional con recharts (ya en deps):
- Selector de período (Hoy/7d/30d) que alimenta la tendencia.
- "Operación actual": Activos · Vencidos · Por vencer | "Histórico": Total · %Resueltos.
- "Entrada de casos": área chart recibidos + líneas cerrados/tutelas; stat
  "tutelas (X% de ingresos)".
- "Composición por tipo": barras por tipo, TUTELA destacada + callout "X% son tutelas".
- Trazabilidad (funnel) y tabla "Casos recientes" (botón Ver todos → onVerTodos).
- Se quitó la sección "Métricas de Respuestas" (vive en tab Rendimiento).
- Compila limpio. Screenshots: `09_dashboard_v2.png`, `10_dashboard_v2_top.png`.

## Pendiente / próximos pasos
- **Redeploy backend** para que `por_vencer`/`activos`/`tutelas` lleguen de verdad
  (rebuild imagen o `docker compose restart backend_v2` con código montado).
- Spot-check visual de: `live-feed` (Mis Casos), `firma-modal`, `borrador-drawer`,
  `virtualized-board`, `toast-urgente`, `reports-tab` (swap aplicado, no verificados).
- Decidir si los modales de auth pasan a claro o quedan navy.
- (Opcional) Feature de escalado real PQR→Tutela para conversión medible.
- Sumar componentes cult-ui donde aporten.
- COMMIT pendiente en la rama feature (nada commiteado todavía).
