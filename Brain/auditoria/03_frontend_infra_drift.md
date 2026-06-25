# Auditoría 03 — Frontend (Next.js/React), Infra (Docker/nginx) y Drift main↔prod

**Fecha:** 2026-06-25
**Rama auditada:** `main` (HEAD `38cf03d`)
**Alcance:** `frontend/src/`, `docker-compose.yml`, `docker-compose.staging.yml`, `nginx/`, `backend/app/main.py` (`/health`), Brain (DEUDAS/CHANGELOG).
**Sin acceso SSH a prod** — el drift se documenta por inferencia desde `git log` + Brain.
**No se modificó código.** Kafka/Zookeeper son vestigiales por diseño → NO se reportan como bug.

---

## (a) FRONTEND

### A.1 Lógica de RBAC visual (cómo funciona)

El rol viaja dentro del JWT y se persiste en `localStorage` bajo la clave `pqrs-v2-auth`
(`store/authStore.ts:32`, `persist({name:"pqrs-v2-auth"})`). El frontend deriva TODA la UI
del campo `user.rol`. Roles observados: `admin`, `super_admin`, `coordinador`, `analista`
(=“abogado” interno / cartera), `abogado` (=operador tipo Recovery).

**Navegación por rol** — `app/page.tsx:49-58`:

- `analista` (variable `isAbogado`): `[Dashboard, Mis Casos, Enviados, Configuración]`
- `abogado` (variable `esOperador`): `[Dashboard, Bandeja, Enviados]`
- resto (admin / super_admin / coordinador): `[Dashboard, Bandeja, Enviados, Rendimiento, Configuración]`
- `super_admin`: además ve el selector de cliente (`page.tsx:197`, `isSuperAdmin && clientes.length>0`).

**Controles admin ocultos por rol** — `components/ui/admin-bandeja.tsx`:

- `esOperador = rol === "abogado" || rol === "analista"` (`admin-bandeja.tsx:68`). Con este flag se ocultan:
  - botón/filtro **No PQRS** (`:237`, `!isModoAC && !esOperador`)
  - **barra de acción de borrado en lote** (`:259`)
  - **checkbox de selección** en header y filas (`:293`, `:350`)
- Filtro **Vista PQRS|AC|Ambos**: solo si `tieneAC` (tenant con buzones ATENCION_CLIENTE), `:190`.
  Recovery/Demo no lo ven. Default `"PQRS"` (`:79`).

**Overlay de caso** — `components/ui/caso-detail-overlay.tsx`:

- `isAdmin = rol === "admin" || rol === "super_admin"` (`:23`)
- `canReassign = isAdmin || rol === "coordinador"` (`:24`) → controla dropdown de reasignación (`:416`) y carga `/admin/team` (`:73`).
- Acciones AC / plantillas / feedback “No PQRS” / reclasificar / vincular tutela gateadas por `isAdmin` (`:743`, `:934`, `:948`, `:962`).

> **Nota de modelo de seguridad:** el RBAC visual es **cosmético**; la autoridad real es el
> backend (CHANGELOG 2026-06-24: “backend ya bloquea con 403”). Esto es correcto, pero implica
> que cualquier hallazgo donde la UI deje un control visible se mitiga server-side y baja de severidad.

---

### A.2 Bugs de frontend (archivo:línea + severidad)

#### 🟠 ALTA — `handleUpdate` muta estado optimista sin revertir ante fallo de API
`caso-detail-overlay.tsx:126-134`
```ts
await api.patch(`/casos/${casoId}`, { [field]: value });
setData(prev => ({ ...prev, [field]: value }));   // se ejecuta solo si no lanzó...
```
El `setData` está *después* del `await`, así que el optimismo no se aplica en error.
**El problema real:** el `catch` (`:131`) solo hace `console.error` — **no muestra feedback al
usuario ni revierte**. Si un `abogado`/`analista` intenta mover un caso a “Resuelto” y el backend
responde 403 (RBAC server-side), el botón cambia de color en la UI (el click ya marcó `est` activo
visualmente vía `data.estado`) pero el estado real no cambió, y el usuario cree que cerró el caso.
Mismo patrón silencioso en `handleReassign` (`:147`) y `handleNoPQRS` (`:160`). **Riesgo operativo:
desync UI↔DB sin aviso** (un caso “marcado resuelto” que sigue ABIERTO en la base, con SLA corriendo).

#### 🟠 ALTA — Badge “Resuelto” derivado SOLO de `estado === "CERRADO"`, semánticamente ambiguo
`caso-detail-overlay.tsx:411`
```ts
{est === "CERRADO" ? "Resuelto" : est === "EN_PROCESO" ? "En Proceso" : "Abierto"}
```
La UI renombra `CERRADO`→**“Resuelto”** en el overlay, pero la **Bandeja** (`admin-bandeja.tsx:411`,
`ESTADO_CLS`) y los filtros (`ESTADOS = ["","ABIERTO","EN_PROCESO","CERRADO"]`, `:40`) muestran el
literal **“CERRADO”**. Dos vocabularios para el mismo estado → inconsistencia visible para el usuario.
Peor: un caso puede llegar a `CERRADO` por envío de respuesta (`:215`, `setData({estado:"CERRADO"})`)
o por cierre manual; el badge “Resuelto” no distingue *resuelto satisfactoriamente* de *cerrado por
descarte/No-PQRS*. **Recomendación:** unificar el diccionario de estados en `lib/` y derivar el label
de una sola fuente.

#### 🟡 MEDIA — Token JWT leído crudo de `localStorage`, sin verificar expiración del lado cliente
`lib/api.ts:9-21` + `store/authStore.ts`
El interceptor adjunta el token sin chequear `exp`. El manejo de 401 (`api.ts:25-44`) dispara
`FLEXPQR_SESSION_EXPIRED` y delega en `useSessionGuard`. Funciona, pero: (1) `error.config._retry`
se setea por request, así que múltiples requests 401 concurrentes pueden disparar el evento varias
veces antes de que `isReauthing` (`useSessionGuard.ts:14`) tome efecto — hay ventana de carrera donde
`onSessionExpired` se llama una vez (protegido por `isReauthing`) pero las requests que llegaron 401
**no se encolan** en `pendingQueue` (la cola se llena en `handleSuccess`, no en el interceptor), así que
esas requests originales quedan rechazadas y perdidas tras el re-auth. **Síntoma:** tras re-login por
sesión expirada, la acción que el usuario disparó puede no re-ejecutarse y “no pasar nada”.

#### 🟡 MEDIA — `crypto.randomUUID()` sin guard de disponibilidad
`app/page.tsx:84` (`handleTutelaUrgente`)
`crypto.randomUUID()` no existe en contextos no-seguros (HTTP plano) ni en navegadores viejos.
En prod la app sirve por HTTPS (`app.flexpqr.com`) así que está OK, pero un toast de **tutela urgente
CRÍTICA** (el evento más importante del sistema) lanzaría excepción y **no se mostraría** si alguna vez
se accede por IP/HTTP. Severidad media por el blast radius (tutelas = legal).

#### 🟡 MEDIA — Llamadas API con manejo de error solo `console.error` (silencioso para el usuario)
Patrón sistémico, no un único punto:
- `admin-bandeja.tsx:125-129` (`fetchCasos`) — si falla, la tabla queda vacía con “No se encontraron casos” en lugar de “error de red”.
- `admin-bandeja.tsx:179-183` (`handleDeleteLote`) — borrado en lote falla en silencio; el modal se queda abierto sin explicar por qué.
- `useSSEStream.ts:76` (`/stats/dashboard.catch(console.error)`) — feed inicial vacío sin aviso.
- `caso-detail-overlay.tsx:257` `try { ... } catch {}` — catch **vacío**, traga el error por completo.
**Riesgo:** el usuario no distingue “no hay datos” de “el backend está caído”. Baja la confianza operativa.

#### 🟢 BAJA — Regex de cédula frágil en mapeo de tickets
`useSSEStream.ts:32` y `:115-117`
```ts
asunto.match(/Doc:\s*(\d+)/i) || asunto.match(/(\d{7,10})/)
```
El segundo patrón captura cualquier número de 7–10 dígitos del asunto (ej. un número de radicado,
un monto, una fecha tipo `2026061500`) como si fuera la cédula. Genera “cédulas” incorrectas en el board.
Cosmético pero engañoso.

#### 🟢 BAJA — `data` tipado como `any` en todo el overlay
`caso-detail-overlay.tsx:26` (`useState<any>(null)`) y ~15 usos `(prev: any)`.
Se pierde todo el chequeo de tipos en el componente más crítico (1008 líneas). Bug latente: el badge
de prioridad asume `data.prioridad ∈ {ALTA,CRITICA,…}` (`:385`) sin validar; un valor inesperado cae
silenciosamente al estilo verde “OK”.

#### 🟢 BAJA — Badge “En línea / En vivo” es decorativo, no refleja conexión real
`app/page.tsx:172-176` y `:187-188` muestran “En vivo”/“En línea” fijo, mientras `useSSEStream`
expone `connected` (`page.tsx:90`) que **no se usa** para ese indicador. Si el SSE se cae, el header
sigue diciendo “En vivo”. Inconsistencia de estado derivado (badge no derivado del estado real).

---

## (b) INFRA — `docker-compose.yml`, nginx, healthchecks

### B.1 Servicios (compose de raíz — perfil local/dev, NEXT_PUBLIC_API_URL apunta a prod)
`postgres_v2` (pgvector pg15), `redis_v2`, `zookeeper_v2`+`kafka_v2` (vestigiales), `minio_v2`,
`backend_v2`, `master_worker_v2`, `demo_worker_v2`, `frontend_v2`, `nginx_ssl`.

### B.2 Hallazgos de infra (archivo:línea + severidad)

#### 🔴 CRÍTICA — Secretos en claro hardcodeados en `docker-compose.yml`
- Password Redis literal en **5 servicios**: `NuSvuOWiQtGWkZleg-zwqUZzs6DewuaK`
  (`docker-compose.yml:31, 85, 111, 143` y en `command` de redis `:31`).
- MinIO `adminminio / adminpassword` hardcodeado (`:63-66, 89-90, 113-114`).
- Postgres `POSTGRES_PASSWORD: pg_password` (`:12`).
Estos viven versionados en el repo. Coincide con las deudas **DT-20** (credenciales ARC en SQLs) y
la tabla “Credenciales a rotar” de `DEUDAS_PENDIENTES.md` (Redis y MinIO marcados Alta/Media).
**Acción:** mover a `.env`/secrets manager y rotar (ya está como deuda abierta).

#### 🟠 ALTA — Ports bindeados a `0.0.0.0` en el compose del repo (riesgo de reabrir el hardening de prod)
`docker-compose.yml:14-15 (5434), 28 (6381), 40, 48, 68-69, 96 (8001), 169 (3002), 181-182 (80/443)`.
El compose del repo expone puertos sin prefijo `127.0.0.1:`. **Prod los tiene bindeados a loopback**
(hardening 14-abr, ver DT-8 y DT-19). Esto es exactamente el riesgo documentado en **DT-8** y
**DT-19** (“un `scp docker-compose.yml` apurado borra el hardening sin aviso”). El archivo del repo
NO debe copiarse a prod tal cual. **Falta el guardrail** (`README.DEPLOY.md` / `verify_compose_diff.sh`)
propuesto en DT-8 — sigue sin implementarse.

#### 🟠 ALTA — `frontend_v2` monta el código fuente como volumen (modo dev en un compose “de despliegue”)
`docker-compose.yml:170-173`:
```yaml
volumes:
  - ./frontend:/app
  - /app/node_modules
  - /app/.next
```
Bind-mount del source + `NEXT_PUBLIC_API_URL=https://app.flexpqr.com` (`:167`). Es una mezcla
peligrosa: build de prod servido pero con el FS del host montado encima. Si este compose corre en un
server, el contenedor sirve lo que haya en `./frontend` del host, no la imagen buildeada → drift
silencioso entre imagen y runtime. (Refuerza por qué prod usa un compose distinto y deploy quirúrgico.)

#### 🟡 MEDIA — Healthchecks faltantes en servicios clave
- `backend_v2` **no tiene healthcheck** (`:78-100`) pese a que `/health` ya existe (`main.py:65`, DT-25 resuelta).
  Debería usar `["CMD","curl","-f","http://localhost:8000/health"]` o equivalente.
- `frontend_v2` sin healthcheck (`:161-175`).
- `redis_v2` sin healthcheck (`:24-31`).
- `zookeeper_v2`/`kafka_v2` sin healthcheck (irrelevante — vestigiales).
Sí tienen healthcheck: `postgres_v2` (`:18`), `minio_v2` (`:72`), `master_worker_v2` (`:122`),
`demo_worker_v2` (`:150`). **`depends_on` sin `condition: service_healthy`** (`:97-100`, `:174-175`):
backend/frontend pueden arrancar antes de que Postgres esté listo (mitigado por el retry-de-pool del backend).

#### 🟡 MEDIA — Sin límites de logging por servicio (recurrencia del incidente DT-28)
Ningún servicio define `logging.options.max-size`/`max-file`. **DT-28** documenta que un worker
huérfano en reconnect-loop llenó 6.4 GB de logs y dejó staging al 100% de disco. La “deuda residual
futura” de DT-28 (poner `max-size` por default) sigue sin aplicarse en este compose.

#### 🟡 MEDIA — `master_worker` permite enviar como cualquier buzón del tenant (Mail.Send amplio)
No es del compose en sí, pero el worker recibe `AZURE_CLIENT_*` (`:118-120`) y el permiso Graph
`Mail.Send` está concedido a nivel app sin Application Access Policy (deuda registrada en
`DEUDAS_PENDIENTES.md` punto 3 del fix envío FF). Severidad media por superficie.

#### 🟢 BAJA — `version: "3.8"` obsoleto y `MINIO_ACCESS_KEY`/`SECRET_KEY` duplicados
`docker-compose.yml:1` (`version` ignorado por Compose v2) y `:63-66` (MinIO acepta `ROOT_USER`/
`ROOT_PASSWORD`; las claves `ACCESS_KEY`/`SECRET_KEY` legacy son redundantes/confusas).

### B.3 nginx (`nginx/nginx.conf`)
- **Bien:** security headers completos en `app.flexpqr.com` (`:108-113`: HSTS 2y, X-Frame DENY,
  nosniff, Referrer-Policy, Permissions-Policy). SSE con `proxy_buffering off` + `read_timeout 3600s`
  (`:118-131`). `client_max_body_size 25M` (`:106`). Resolver Docker interno con re-resolución 30s.
- 🟡 **MEDIA — los security headers NO están en el `server` default `_` (`:26-76`)**, solo en el
  vhost `app.flexpqr.com`. El default server (que atiende acceso por IP `app.flexpqr.com` fallback)
  sirve la app **sin HSTS ni X-Frame-Options**. Si alguien entra por IP, el dashboard queda
  clickjackeable / sin HSTS.
- 🟢 **BAJA — TLS:** `ssl_ciphers HIGH:!aNULL:!MD5` es razonable pero no es una suite moderna
  curada (Mozilla intermediate). Acepta TLSv1.2 (OK). Sin `ssl_prefer_server_ciphers`.
- 🟢 **BAJA — certs self-signed** en `nginx/certs/server.crt` (default server) vs certs reales para
  los vhosts con nombre. Esperado para el fallback por IP.

### B.4 `/health` (backend)
`backend/app/main.py:65-81` — correcto: `SELECT 1` vía pool, 200 `{status:ok,db:up}` / 503
`{status:degraded}`. Resuelve DT-25. **Pero ningún healthcheck del compose lo consume** (ver B.2).

---

## (c) DRIFT main ↔ PRODUCCIÓN

> **Regla de oro del proyecto:** prod NO se actualiza con `git pull`. Va ~8 commits detrás de `main`.
> Todo deploy a prod es **quirúrgico** (backup `.bak` + copiar archivos puntuales + preservar CRLF +
> rebuild del servicio). Los fixes recientes ya fueron aplicados quirúrgicamente.
> **Sin SSH a prod desde aquí** → lo siguiente es inferencia desde `git log -30` + CHANGELOG + DEUDAS.

### C.1 Estado conocido (qué SÍ está en prod, aplicado quirúrgicamente)
Según `DEUDAS_PENDIENTES.md` y `CHANGELOG.md`:
- ✅ **Envío FlexFintech por Graph** (`d8a08fc`, PR #20 / rama `fix/ff-envio-outlook-graph`) —
  desplegado quirúrgicamente a prod (backend_v2 rebuild, HTTP 200). *Falta validación e2e + merge de PR #20.*
- ✅ **Firma por tenant** (`60f279c`, FF texto / Recovery imagen) — fix aplicado.
- ✅ **Fix loop infinito de seguimientos** (`f021d63`, INC-2026-06-25) — aplicado.
- ✅ **RBAC backend abogado/analista** (`aecac2d`, `3343d93`) — “hotfix en prod”, verificado e2e
  (abogado→256 casos, admin→1590).

### C.2 Commits de `main` que prod PROBABLEMENTE NO tiene (drift vivo)

Top de `git log --oneline -30 main` (HEAD `38cf03d`):

| Commit | Descripción | ¿En prod? | Riesgo si se deploya “a ciegas” |
|---|---|---|---|
| `38cf03d` | Merge PR #22 fix/firma-por-tenant | parcial (fix sí, merge no) | Bajo — ya aplicado quirúrgico |
| `b3b8d3c` | Merge PR #21 fix/seguimiento-loop | parcial | Bajo — ya aplicado |
| `9b483cf` | docs(brain) | N/A (solo docs) | Nulo |
| `ad22a13` | feat(seguimiento): borrador nuevo al recibir mail ciudadano | ❓ probable | **MEDIO** — cambia comportamiento del worker; si no se rebuildeó master_worker exacto, divergencia |
| `60f279c` | fix(firma) por tenant | ✅ aplicado | Bajo |
| `8a05a78` | docs(brain) | N/A | Nulo |
| `f021d63` | fix(worker) corta loop + idempotencia + reapertura | ✅ aplicado | Bajo |
| `48957ee` | docs(brain) | N/A | Nulo |
| `d8a08fc` | fix(envio) FF por Graph | ✅ aplicado | Bajo (falta e2e) |
| `f023ffb` | docs(brain) | N/A | Nulo |
| `009afb5` | docs(brain) + .gitignore graphify-out | N/A | Nulo |
| **`5ea8c2b`** | **feat(frontend): vista operador rol abogado (Bandeja con su cartera)** | ❌ **PENDIENTE** | **ALTO** — el CHANGELOG 2026-06-24 lo marca explícito: *“Fase 2a frontend (`5ea8c2b`, en main): Deploy a prod PENDIENTE (rebuild `frontend_v2`)”*. **Prod corre el frontend viejo**: los abogados NO tienen aún la nav `[Dashboard,Bandeja,Enviados]` ni la Bandeja sin controles admin. Backend ya bloquea con 403, así que es seguro funcionalmente, pero **UX rota para abogados en prod hoy** (pueden ver controles admin que el backend rechaza). |
| `3343d93`/`aecac2d` | fix(rbac) abogado ve su cartera (backend) | ✅ aplicado | Bajo |
| `c5722fc` | Feat/ff reclasificacion imagenes (#19) | ❓ | MEDIO — si toca worker/backend y no se aplicó, drift |
| `87c7df7` | feat(backend): `/health` (DT-25) (#18) | ❌ **PENDIENTE en prod** | **MEDIO** — DT-25 dice: resuelta en **staging** 2026-06-01; *“Pendiente: deploy a prod (18.228.54.9)”*. Prod aún responde 404 en `/health`. Bajo impacto runtime, pero monitoring externo falla. |
| `eb090a4` | feat(rag) cierre-de-loop + Recovery plantillas a DB | ❓ | MEDIO — toca RAG/plantillas; ver deuda “seed plantillas Recovery” (prod ya tiene 8 plantillas, NO correr seed) |
| `ec0d1a7`/`03c7d12`/`7d94124` | F1/F2 borradores: visión PDFs+imágenes, leer adjuntos | ❓ probable parcial | MEDIO — features de worker; verificar imagen master_worker en prod |
| `cdff3e6`/`dcada2a` | flexfintech /auth/me + clasificador AC gateado por tenant | ❓ | MEDIO |

**Resumen del drift:** los **dos commits con drift confirmado y de mayor riesgo** son:
1. **`5ea8c2b` (frontend operador)** — ALTO: prod sirve frontend desactualizado; abogados ven UI
   admin que el backend rechaza con 403 (mitigado pero confuso). Requiere rebuild `frontend_v2`.
2. **`87c7df7` (`/health` DT-25)** — MEDIO: prod sin `/health` (404); afecta probes de monitoring.

El resto del bloque RAG/borradores/reclasificación de imágenes (`eb090a4`, `ec0d1a7`, `03c7d12`,
`c5722fc`, `cdff3e6`) **no tiene confirmación de deploy en el Brain** → drift probable de
backend/worker. Cualquier deploy debe ser quirúrgico y, para RAG, respetar que **prod ya tiene las
8 plantillas Recovery buenas** (NO correr `seed_plantillas_recovery.py`, deuda OBSOLETA) y que la
**migración 14 (SLA sectorial) NUNCA corrió en prod** (motor SLA dormido — rebuild de backend a ciegas
→ `500 column regimen_sla does not exist`).

### C.3 Riesgo transversal del proceso de deploy
- **DT-8 / DT-19 (ALTA):** no existe guardrail que impida que un `docker-compose.yml` del repo
  (ports `0.0.0.0`, sin env vars de prod) sobrescriba el de prod (loopback + `DEMO_*` + `MINIO_*`).
  Un sync apurado **reabre puertos y rompe demo** sin aviso. Guardrail propuesto sin implementar.
- **Migración 14 sin aplicar (Media-alta):** endpoints `/admin/regimen-sla/*` existen en disco/main
  pero las tablas no existen en `pqrs_v2`. Rebuild de backend sin migrar primero → 500 al primer click.

---

## TOP 5 hallazgos (frontend + infra)

1. 🔴 **Secretos en claro versionados en `docker-compose.yml`** (Redis pass ×5, MinIO `adminminio/adminpassword`, Postgres `pg_password`) — `docker-compose.yml:12,31,63-66,85,111,143`. Rotar + mover a secrets (DT-20).
2. 🟠 **`handleUpdate`/`handleReassign`/`handleNoPQRS` no revierten ni avisan ante fallo de API** — `caso-detail-overlay.tsx:126-165`. Un caso “marcado Resuelto” por un abogado puede quedar ABIERTO en DB con SLA corriendo y sin feedback de error (RBAC 403 silencioso).
3. 🟠 **Compose del repo con ports `0.0.0.0` + bind-mount del frontend** — `docker-compose.yml:14-15,96,169-173`. Reabre el hardening de prod (loopback) si se copia tal cual. Guardrail DT-8/DT-19 sin implementar.
4. 🟠 **Badge “Resuelto” derivado solo de `estado==='CERRADO'` con vocabulario inconsistente** — overlay dice “Resuelto” (`caso-detail-overlay.tsx:411`), Bandeja dice “CERRADO” (`admin-bandeja.tsx:411`). No distingue resuelto-OK de cerrado-por-descarte.
5. 🟡 **Healthchecks faltantes en `backend_v2`/`frontend_v2`/`redis_v2` + sin `condition: service_healthy` + sin límites de logging** — `docker-compose.yml:78-100,161-175,24-31`. `/health` existe (`main.py:65`) pero nadie lo consume; recurrencia del incidente de disco DT-28.

## Resumen del drift main↔prod
- Prod va **~8 commits detrás** de `main` (HEAD `38cf03d`). Fixes recientes **ya aplicados quirúrgicamente**: envío FF por Graph (`d8a08fc`), firma por tenant (`60f279c`), loop seguimientos (`f021d63`), RBAC backend abogado (`aecac2d`/`3343d93`).
- **Drift de mayor riesgo confirmado:** `5ea8c2b` (frontend operador — **PENDIENTE**, abogados en prod ven UI admin que el backend rechaza) y `87c7df7` (`/health` DT-25 — **prod responde 404**, deploy a prod pendiente).
- **Drift probable no confirmado:** bloque RAG/borradores/reclasificación de imágenes (`eb090a4`, `ec0d1a7`, `03c7d12`, `c5722fc`, `cdff3e6`) — features de backend/worker sin sello de deploy en el Brain.
- **Trampas de deploy a evitar:** migración 14 (SLA sectorial) NUNCA corrió en prod → rebuild backend a ciegas = `500 regimen_sla`; NO correr `seed_plantillas_recovery.py` (prod ya tiene las 8 plantillas buenas); NO sincronizar `docker-compose.yml` del repo sobre prod (reabre puertos).
