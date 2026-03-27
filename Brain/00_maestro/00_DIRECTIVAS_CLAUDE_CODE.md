---
tags:
  - brain/maestro
---

# Directivas Claude Code -- FlexPQR / Aequitas

## Identidad del Proyecto

- **Nombre comercial:** FlexPQR (antes Aequitas)
- **Dominio:** flexpqr.com (landing), app.flexpqr.com (dashboard)
- **Proposito:** Plataforma enterprise SaaS multi-tenant para gestion de PQRS (Peticiones, Quejas, Reclamos, Solicitudes) y Tutelas bajo normativa colombiana.

## Reglas de Oro

1. **Nunca exponer secretos.** Toda credencial vive en variables de entorno o docker-compose env. Jamas hardcodear API keys, passwords ni tokens en el codigo fuente.
2. **Multitenancy es innegociable.** Toda query a PostgreSQL debe pasar por Row-Level Security (RLS). El `cliente_id` del JWT se inyecta en `app.current_tenant_id` antes de cada conexion.
3. **Arquitectura Event-Driven.** Los emails entrantes no se procesan sincrono. Se encolan a Kafka (`pqrs.raw.emails`) y los workers los clasifican en background.
4. **Clasificacion hibrida.** Primero keywords + scoring engine (rapido, gratis). Si confianza < 0.70, escalar a Claude Haiku via Anthropic API.
5. **Dead Letter Queue obligatoria.** Todo consumer Kafka debe enviar mensajes irrecuperables a `pqrs.events.dead_letter`, nunca bloquear la particion.
6. **SLA Legal Colombiano.** Los plazos (TUTELA=2 dias habiles, PETICION=15, etc.) se calculan automaticamente con triggers de PostgreSQL y tabla de festivos.
7. **Idioma del codigo:** Python (backend/workers), TypeScript (frontend). Comentarios y variables de negocio en espanol. Logs y docstrings pueden ser en espanol.
8. **Branch strategy:** main es la rama principal. Ramas feature/hotfix se crean desde main.

## Stack Tecnologico

| Capa          | Tecnologia                          |
|---------------|-------------------------------------|
| Frontend      | Next.js 14 + TypeScript + Tailwind  |
| Backend API   | FastAPI + asyncpg + Pydantic        |
| Base de datos | PostgreSQL 15 con RLS               |
| Cache/PubSub  | Redis 7                             |
| Message Broker| Apache Kafka (Confluent 7.3)        |
| Storage       | MinIO (S3-compatible)               |
| IA            | Anthropic Claude (Haiku)            |
| Proxy         | Nginx con SSL/TLS                   |
| Contenedores  | Docker Compose                      |

## Roles del Sistema

- `super_admin` -- Ve todos los tenants, bypass RLS via `app.is_superuser`
- `admin` -- Administrador de un tenant especifico
- `coordinador` -- Coordinador de equipo dentro del tenant
- `analista` -- Abogado/analista que trabaja los casos
- `abogado` -- Equivalente funcional de analista (usado por Abogados Recovery)
- `auditor` -- Solo lectura para auditoria
- `bot` -- Cuenta de servicio para workers automaticos

**IMPORTANTE:** En el codigo, comparar SIEMPRE contra ambos roles: `analista` Y `abogado`.
Ejemplo: `WHERE rol IN ('analista', 'abogado')` o `user?.rol === "analista" || user?.rol === "abogado"`.


## Deploy en Produccion (18.228.54.9)

```bash
# Conectar al servidor
ssh -i ~/.ssh/flexpqr-prod.pem ubuntu@18.228.54.9
cd ~/PQRS_V2

# Pull de cambios
git pull origin develop

# Levantar con rebuild — backend y workers
docker compose up -d --build backend_v2
docker compose up -d --build master_worker_v2

# FRONTEND — procedimiento especial obligatorio
# docker compose up --build NO funciona para el frontend porque los volumenes
# de desarrollo (bind mount ./frontend:/app + anonymous volume /app/.next)
# sobrescriben el .next del Dockerfile.
# SIEMPRE usar este procedimiento para deployar cambios de frontend:
docker exec pqrs_v2_frontend sh -c 'cd /app && npm run build'
docker compose restart frontend_v2
# Verificar que levanto correctamente:
docker logs pqrs_v2_frontend --tail=20

# Backup de base de datos (antes de cualquier cambio en DB)
docker exec pqrs_v2_db pg_dump -U pqrs_admin -d pqrs_v2 -F c -f /tmp/backup_$(date +%Y%m%d_%H%M).dump
docker cp pqrs_v2_db:/tmp/backup_*.dump ~/backups/
```

## Modo Multi-Agente — Obligatorio

> **Esta directiva es de cumplimiento obligatorio en TODAS las tareas,
> sin excepcion. Un solo agente secuencial esta prohibido para cualquier
> tarea que tenga mas de un componente.**

### Principio
Claude Code SIEMPRE debe descomponer las tareas en agentes especializados
paralelos o secuenciales segun el tipo de trabajo. Nunca ejecutar todo
en un solo hilo de razonamiento si la tarea tiene partes independientes.

### Cuando usar multiples agentes

| Situacion | Estrategia |
|-----------|-----------|
| Tarea con backend + frontend | Agente DB, Agente Backend, Agente Frontend en paralelo |
| Debug de un bug | Agente Diagnostico → Agente Fix → Agente Verificacion |
| Feature nueva | Agente Diseno → Agente Implementacion → Agente Tests |
| Migracion de DB | Agente Schema → Agente Data → Agente Validacion |
| Deploy | Agente Build → Agente Deploy → Agente Smoke Test |
| Cualquier tarea > 3 pasos | Siempre dividir en agentes especializados |

### Estructura obligatoria de cada sesion

Antes de ejecutar CUALQUIER tarea, Claude Code debe declarar explicitamente:

```
PLAN MULTI-AGENTE
━━━━━━━━━━━━━━━━━━━━
Agente 1 — [NOMBRE]: [responsabilidad]
Agente 2 — [NOMBRE]: [responsabilidad]
Agente 3 — [NOMBRE]: [responsabilidad]
Modo: PARALELO | SECUENCIAL | MIXTO
Dependencias: Agente 2 espera resultado de Agente 1 para [X]
```

### Roles de agentes disponibles en FlexPQR

| Agente | Especialidad |
|--------|-------------|
| **DB Agent** | SQL, migraciones, RLS, backups, seeds |
| **Backend Agent** | FastAPI, endpoints, servicios, workers |
| **Frontend Agent** | Next.js, componentes, hooks, SSE |
| **Infra Agent** | Docker, Nginx, SSH, AWS, variables de entorno |
| **QA Agent** | Tests, verificacion, smoke tests post-deploy |
| **Docs Agent** | Brain/, commits, documentacion, changelog |

### Ejemplo correcto

```
PLAN MULTI-AGENTE — Hotfix reasignacion de casos
━━━━━━━━━━━━━━━━━━━━
Agente 1 — Backend Agent: Agregar asignado_a al PATCH /casos/{id}
Agente 2 — Frontend Agent: Agregar dropdown de reasignacion al overlay
Agente 3 — Infra Agent: Rebuild backend + frontend y verificar
Agente 4 — QA Agent: Smoke test del endpoint y UI
Modo: MIXTO (1+2 en paralelo, luego 3, luego 4)
Dependencias: Agente 3 espera que 1 y 2 terminen
```

### Ejemplo incorrecto

Ejecutar backend + frontend + deploy + tests en un solo bloque de codigo
sin separar responsabilidades ni declarar el plan. Esto esta PROHIBIDO.

### Beneficios

- **Velocidad:** Partes independientes corren en paralelo
- **Calidad:** Cada agente es experto en su dominio
- **Trazabilidad:** El plan declarado queda en el log de la sesion
- **Rollback:** Si un agente falla, los otros no se ven afectados


## Lecciones Aprendidas

### Frontend — Volumenes de desarrollo bloquean rebuild (27/03/2026)
**Sintoma:** Cambios de codigo en el frontend no se reflejan en produccion
despues de `docker compose up -d --build frontend_v2`.
**Causa raiz:** El docker-compose.yml tiene bind mounts de desarrollo:
- `./frontend:/app` — sobrescribe el /app del image con los archivos del host
- `/app/.next` — volumen anonimo persiste el .next viejo entre rebuilds

El build del Dockerfile genera el .next correcto, pero el volumen anonimo
lo reemplaza al iniciar el contenedor.
**Fix operativo:** Buildear dentro del contenedor corriendo:
```bash
docker exec pqrs_v2_frontend sh -c 'cd /app && npm run build'
docker compose restart frontend_v2
```
**Fix definitivo pendiente:** Crear un docker-compose.prod.yml sin los volumenes
de desarrollo y usar `docker compose -f docker-compose.prod.yml up -d --build`.

### Zoho — Bloqueo por actividad inusual (27/03/2026)
**Sintoma:** Envios de email retornan False silenciosamente.
Abogados firman casos pero ciudadanos no reciben respuesta.
**Causa:** Zoho detecta rafagas de envio y bloquea la cuenta (error 550 5.4.6).
**Solucion implementada:**
- Rate limiting: max 15 emails/min, 3s entre cada envio (zoho_engine.py)
- Fallback SMTP: si Zoho falla, reintenta por SMTP configurado en env vars
- Health check: GET /api/v2/admin/zoho/health para verificar estado
**Variables de entorno para SMTP fallback:**
  SMTP_FALLBACK_HOST, SMTP_FALLBACK_PORT, SMTP_FALLBACK_USER, SMTP_FALLBACK_PASS
**Desbloqueo manual:** https://mail.zoho.com/UnblockMe

### Auth — Ciclo infinito de sesion expirada (27/03/2026)
**Sintoma:** Usuarios no pueden iniciar sesion. Quedan atrapados en el modal
"Tu sesion ha expirado" y ni "Cerrar sesion" los saca.
**Causa raiz (4 bugs encadenados):**
1. El interceptor 401 de axios se disparaba en TODAS las rutas, incluyendo /login
2. Un login fallido en /login abria el ReAuth modal encima del login real
3. `clearAuth()` de zustand no limpiaba localStorage sincronicamente
4. `router.push('/login')` no recargaba la pagina, dejando estado viejo en memoria
**Fix implementado:**
- Interceptor 401 excluye endpoints `/auth/` y la ruta `/login`
- La pagina `/login` llama `clearAuth()` en useEffect al cargar
- `clearAuth()` hace `localStorage.removeItem('pqrs-v2-auth')` explicito
- Todos los redirects usan `window.location.href` en vez de `router.push`
**Regla:** NUNCA usar `router.push('/login')` para cerrar sesion. SIEMPRE `window.location.href = '/login'`.

### Cambio de password obligatorio (27/03/2026)
**Feature:** Modal bloqueante `ChangePasswordModal` que aparece cuando
`user.debe_cambiar_password === true` despues del login.
**Backend:** `POST /api/v2/auth/change-password` con `{ new_password }` —
actualiza hash y pone `debe_cambiar_password = FALSE`.
**Frontend:** Componente en `frontend/src/components/ui/change-password-modal.tsx`,
integrado en `page.tsx` del dashboard.
**Uso admin:** Para resetear passwords de un tenant:
```python
# Desde pqrs_v2_backend container:
UPDATE usuarios SET password_hash = '<bcrypt_hash>', debe_cambiar_password = TRUE
WHERE cliente_id = '<tenant_uuid>' AND is_active = TRUE;
```

## Tenant Demo

- **Tenant ID:** 11111111-1111-1111-1111-111111111111
- **Admin:** demo@flexpqr.co / FlexDemo1
- **Email ingesta:** democlasificador@gmail.com (IMAP polling cada 30s)
- **Worker:** demo_worker_v2 — lee Gmail, clasifica, genera borrador IA, envia acuse
- **Reset automatico:** Casos con mas de 30 min se eliminan automaticamente
- **Seed datos:** `scripts/seed_demo_data.py` — 18 casos variados + 5 usuarios demo
- **Ejecucion seed:** `docker cp scripts/seed_demo_data.py pqrs_v2_backend:/tmp/ && docker exec pqrs_v2_backend python3 /tmp/seed_demo_data.py`

## Referencias

- [[01_ARQUITECTURA_MAESTRA]]
- [[09_EXCELENCIA_INGENIERIA_Y_GIT]]
- [[13_EQUIPOS_DE_AGENTES_Y_ORQUESTACION]]
