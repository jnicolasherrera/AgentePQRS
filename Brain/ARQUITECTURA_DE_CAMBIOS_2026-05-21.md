# Arquitectura de Cambios — FlexPQR / ARCSAS

**Fecha:** 2026-05-21
**Objetivo:** mejorar y limpiar el sistema — sacar code smells, "cosas raras", hacks,
drift y deuda. No parches sueltos: un plan estructurado por dominios y fases.
**Método:** barrido en 3 frentes (Brain/deuda documentada · backend+workers · frontend+infra)
+ verificación en vivo contra prod (18.228.54.9) y staging (15.229.114.148).

---

## 0. Resumen ejecutivo

El sistema funciona y opera al cliente piloto (ARC), pero arrastra deuda en 7 dominios.
Lo que más importa, en orden:

1. **Seguridad de secretos** — hay credenciales reales en archivos versionados (SQLs, compose, .py). Rotar + sacar del repo.
2. **Aislamiento multi-tenant (RLS)** — endpoints que confían en RLS sin filtro explícito de `cliente_id`. Hay un cross-tenant leak ya conocido (C1).
3. **Estructura del repo** — ~27 scripts ad-hoc sueltos, SQLs legacy en raíz, sin sistema de migraciones, carpetas vacías/duplicadas, clutter de backups.
4. **Cosas raras de código** — `azure_*` reusado para Zoho, `time.sleep()` en async, `except Exception` que tragan errores, código duplicado, `KeyError 'access_token'` sin manejar (el bug que tuvo ARC 13 días caído).
5. **Infra/deploy** — 3 docker-compose confusos (staging apunta a prod), drift no commiteado, `release/tutelas` sin mergear a main.

Deuda documentada en Brain: **40 DT-, 3 INC-**, de los cuales 8 ya resueltos
(notablemente DT-32/33/34 — el pool reconnect + healthcheck + alerting que causaron
el incidente de 12 días de abril; **NO tocar, ya están bien**).

---

## 1. SEGURIDAD 🔴 (Fase 0 — urgente)

| # | Hallazgo | Dónde | Acción |
|---|---|---|---|
| S1 | Credenciales reales de ARC/FlexFintech en SQLs versionados | `04_multi_tenant_config_v2.sql`, `05_multi_provider_buzones.sql` | Reemplazar por placeholders; mover seed real a fuera del repo (DT-20) |
| S2 | Secretos inline en compose | `docker-compose.yml` / `.staging.yml` (Redis pass, MinIO, IPs prod) | Mover a `.env` + `${VAR}` |
| S3 | Hardcodes en código | `master_worker_outlook.py` (AZURE_CLIENT_ID/TENANT), `zoho_engine.py` | Leer todo de env/DB, sin defaults |
| S4 | Defaults inseguros en config | `backend/app/core/config.py` (`jwt_secret_key="dev-key-change-in-prod"`, `pg_password`) | Sin defaults; fallar al startup si falta la env |
| S5 | Rotaciones pendientes | DT-20 (deadline vencido 2026-04-30) | Rotar: Zoho client_secret (visto en chat hoy), **ANTHROPIC_API_KEY** (visto en chat hoy), Gmail App Password, Redis pass, MinIO |
| S6 | Purga git history | DT-21 (depende de S5) | `git filter-repo` tras rotar, para borrar secretos del histórico |

**Aclaración:** el `.env` **NO** está trackeado (verificado — 0 commits). El riesgo está
en los SQL/compose/py versionados, no en el `.env`.

---

## 2. AISLAMIENTO MULTI-TENANT (RLS) 🔴 (Fase 0/1)

El principio del sistema es "RLS innegociable", pero hay grietas:

- **Endpoints sin filtro explícito de tenant** — ej. `GET /borrador/pendientes` (`casos.py`) y queries en `stats.py` confían 100% en RLS sin enviar/validar `cliente_id`. Si la policy RLS falla o el `set_config('app.current_tenant_id')` no se aplicó, hay fuga cross-tenant silenciosa.
- **Cross-tenant leak conocido** (C1 del tablero, descubierto 14-abril) en `/casos/borrador/pendientes` — hotfix nunca aplicado.
- **Acción:** todo GET multi-tenant debe llevar `WHERE cliente_id = $1` **además** de RLS (defensa en profundidad). Auditar cada endpoint. Tests de aislamiento (ya existe `test_rls_hierarchy.py` — extender).

---

## 3. CÓDIGO — workers y backend ("cosas raras") 🟠 (Fase 2)

| # | Cosa rara | Dónde | Por qué importa |
|---|---|---|---|
| C1 | `azure_client_id`/`azure_client_secret` reusados para Zoho | `config_buzones` + `master_worker_outlook.py:220` | Confunde; ya nos hizo dudar hoy. Renombrar a `oauth_client_id/secret` provider-agnostic (migración) |
| C2 | `time.sleep()` en código async | `zoho_engine.py:_rate_limit_send` (188-205) | Bloquea el event loop → congela otras coroutines. Cambiar a `await asyncio.sleep()` |
| C3 | `KeyError 'access_token'` sin manejo | `zoho_engine.py` (flujo de refresh) | **Es el bug que dejó ARC 13 días caído**: cuando Zoho devuelve error en vez de token, explota y reintenta a lo loco. Manejar el error de OAuth explícitamente |
| C4 | `except Exception` genéricos que tragan errores | `master_worker_outlook.py:397`, `zoho_engine.py:101` | Debugging ciego, bucles de fallo sin backoff inteligente. Excepciones tipadas (`ZohoRateLimitError`, etc.) |
| C5 | Código duplicado `_md_to_html` / `_firma_html` | `zoho_engine.py` + `casos.py` | Drift entre copias. Extraer a `app/services/email_utils.py` |
| C6 | Dedup-check DESPUÉS de llamar a Claude | `master_worker_outlook.py` (DT-35) | Gasta API de Claude en emails ya procesados. Mover el `SELECT 1 ... external_msg_id` antes de clasificar |
| C7 | Constantes de tenant hardcodeadas y duplicadas | `master_worker_outlook.py:36` + `ai_engine.py:61` (mismo UUID, distinto nombre) | Centralizar en `app/constants.py` o leer de DB |
| C8 | Firma inline Zoho no garantiza render en Outlook | `zoho_engine.py:_firma_html` (DT-38) | Flujo oficial Zoho son 2 pasos (uploadAttachment isInline). Hoy SMTP fallback lo salva parcial |

---

## 4. ESTRUCTURA / ORGANIZACIÓN 🟠 (Fase 1 — alto impacto, bajo riesgo)

- **~27 scripts ad-hoc sueltos**: ~15 en `backend/` (`debug_login.py`, `cleanup_master.py`, `list_users.py`, `seed_demo_abogado.py`…) + ~12 en raíz (`seed_*.py`, `analyze_*.py`, `create_admin.py`, `inbound_outlook_v2.py`, `deploy_ubuntu.sh`). → mover a `scripts/{db,onboarding,maintenance,testing}/` con CLI y docstrings.
- **SQLs legacy en raíz** (`01_..08_*.sql`) ya subsumidos por `migrations/00_baseline_schema.sql` (DT-27). → mover a `migrations/legacy/`.
- **Carpetas fantasma**: `aequitas_backend/` vacía, `aequitas_infrastructure/` casi vacía (solo la mig 14). → consolidar o borrar.
- **Clutter de backups**: `Brain_backup_20260420_1233/`, `brain_snapshots/`, `nginx/certs/*.orig`, `brain_completo.tar.gz`, `.env.local-backup-*`. → borrar + reglas en `.gitignore`.
- **Tests dispersos**: raíz de `backend/` vs `backend/tests/`. → consolidar en `backend/tests/`.
- **`storage_engine` import eager cuelga pytest ~90s** (DT-29) → lazy client load.

---

## 5. INFRA / DEPLOY 🟠 (Fase 3)

- **3 docker-compose confusos**: `docker-compose.staging.yml` **apunta a IPs de prod** (engaña). `docker-compose.override.yml` (bump Confluent por bug JDK) no documentado. → renombrar/documentar; crear `docker-compose.prod.yml` real; matriz "dónde corre qué" en README.
- **Puertos de más expuestos en prod** (Kafka 9093, ZK 2182, MinIO 9020/21, Redis 6381). → cerrar en prod (solo backend/frontend/nginx).
- **Guardrail prod vs local** (DT-8): nada impide pisar el hardening de puertos. → `deploy/verify_compose_diff.sh`.
- **Drift no commiteado** (DT-19/INC-2026-04-29): commit `2331581` solo en prod EC2. → cherry-pick formal al repo.
- **`release/tutelas-2026-05-07` corre en prod pero no está en `main`** (72 commits). → mergear; sincroniza la verdad.
- **D3 nunca se hizo**: las imágenes de prod tienen 6 semanas; el código del sprint Tutelas está en DB (migraciones) pero el backend/frontend en runtime es viejo. → build + force-recreate (con cuidado).
- **Nginx**: bloques SSE duplicados, certs `.orig` sin usar, upstreams hardcodeados. → refactor con includes.

---

## 6. DATOS / MIGRACIONES 🟠 (Fase 1/2)

- **Sin sistema de migraciones robusto**: numeración inconsistente (salta 05→08→14→18-22), `migrate.sh` es Bash con `docker cp`+`psql`, mezcla schema+seed. → runner idempotente con tabla `schema_migrations(name, sha, applied_at)` (parcialmente existe `aequitas_migrations` — formalizar).
- **ORM `models.py` desincronizado con la DB** (DT-30): ~13 columnas en DB no declaradas, `semaforo_sla` CHECK con 5 valores en DB / 3 en ORM. → reconciliar (no bloquea hoy porque usan asyncpg directo, sí bloquea código futuro con ORM).
- **`tutelas_view` es MATERIALIZED** → necesita `REFRESH` periódico (cron o trigger). Verificar que esté programado.

---

## 7. OBSERVABILIDAD 🟡 (Fase 4)

- **`last_sync` nunca se popula** en `config_buzones` → métrica clave que hubiera prevenido el bucle de DT-39. Poblarla en cada poll.
- **Backend no expone `/health`** (DT-25) → agregar con `SELECT 1`.
- **DT-39 bridge cron** (restart-bombing en madrugada CO) → **hoy pausado**. No re-habilitar sin hardening (gate horario + detección de rate-limit antes de reiniciar). DT-33 (healthcheck funcional) ya lo reemplaza en gran parte.
- **Logging con emojis** no parseable por agregadores → structured logging (JSON).
- **`console.error` en frontend** (18 ocurrencias) sin centralizar → `lib/logger.ts` → Sentry en prod.
- **Kafka/Zookeeper estuvieron Exited 4+ semanas sin alerta** → decidir deprecar el event bus secundario o monitorearlo.

---

## 8. YA RESUELTO — NO TOCAR

- **DT-32** pool asyncpg reconnect (`_ensure_alive_connection`) ✅
- **DT-33** healthcheck funcional de workers ✅
- **DT-34** alerting de ingesta (`check_ingestion_v2.sh`) ✅
- **Motor SLA Sectorial** (mig 14): verificado HOY que está aplicado en prod (tablas `festivos_colombia`, `sla_regimen_config`, columna `regimen_sla` existen). DEUDAS_PENDIENTES.md desactualizado — corregir.
- **Token Zoho ARC**: resuelto 2026-05-21 con scopes completos.

---

## ARQUITECTURA OBJETIVO (cómo debería quedar)

```
AgentePQRS/
├── backend/
│   ├── app/            # solo código de aplicación
│   ├── tests/          # TODOS los tests acá
│   └── (sin scripts sueltos en root)
├── frontend/
├── scripts/
│   ├── db/             # seeds, migraciones manuales (CLI unificado)
│   ├── onboarding/     # setup local/dev
│   ├── maintenance/    # ops
│   └── testing/        # smoke tests
├── migrations/
│   ├── NNNN_desc.sql   # numeración consistente, idempotentes, schema-only
│   ├── seeds/          # seed separado de schema
│   └── legacy/         # SQLs viejos archivados
├── deploy/
│   ├── docker-compose.yml          # base
│   ├── docker-compose.override.yml # local dev (documentado)
│   ├── docker-compose.prod.yml     # prod real (sin secretos)
│   ├── docker-compose.staging.yml  # staging REAL (no prod)
│   └── verify_compose_diff.sh      # guardrail
├── .env.example        # plantilla (el .env real nunca en git)
└── README.md           # matriz "dónde corre qué" + flujo de deploy
```

**Principios objetivo:**
- Secretos: solo en `.env` (gitignored) / SSM Parameter Store / Secrets Manager. Cero en código, SQL o compose.
- Multi-tenant: filtro explícito `cliente_id` + RLS (defensa en profundidad), con tests de aislamiento.
- Migraciones: idempotentes, versionadas, schema separado de seed, runner con tracking.
- Observabilidad: `/health` real, `last_sync` poblado, logs estructurados, alerting de pipeline (no solo de container).

---

## PLAN DE EJECUCIÓN (fases)

### Fase 0 — Seguridad (días, urgente)
1. Rotar: ANTHROPIC_API_KEY, Zoho client_secret, Gmail App Password, Redis pass, MinIO (S5).
2. Reemplazar credenciales reales en SQLs versionados por placeholders (S1).
3. Sacar secretos inline de compose → `.env` (S2, S3).
4. config.py sin defaults inseguros (S4).
5. (Después) purga git history (S6/DT-21).

### Fase 1 — Limpieza estructural (bajo riesgo, alto orden)
1. Reorganizar scripts → `scripts/{db,onboarding,maintenance,testing}/`.
2. SQLs legacy → `migrations/legacy/`. Borrar carpetas fantasma y clutter de backups.
3. Consolidar tests en `backend/tests/`. Fix `storage_engine` lazy (DT-29).
4. Actualizar `.gitignore` + `DEUDAS_PENDIENTES.md`.

### Fase 2 — Código (refactors de "cosas raras")
1. RLS: filtro explícito de tenant en todos los endpoints + tests (dominio 2).
2. `time.sleep`→`asyncio.sleep` (C2); manejo de error OAuth Zoho (C3); excepciones tipadas (C4).
3. Dedup antes de Claude (C6); deduplicar `_md_to_html`/`_firma_html` (C5); centralizar constantes de tenant (C7).
4. Migración para renombrar `azure_*`→`oauth_*` (C1).

### Fase 3 — Infra/deploy
1. Reorganizar docker-compose (base/override/prod/staging) + README matriz.
2. Cerrar puertos en prod; guardrail `verify_compose_diff.sh` (DT-8).
3. Cherry-pick del drift (DT-19); mergear `release/tutelas` → main; ejecutar D3.

### Fase 4 — Observabilidad + frontend
1. `/health` (DT-25); poblar `last_sync`; logs estructurados.
2. DT-39 hardening → re-habilitar bridge cron.
3. `lib/logger.ts` + Sentry en frontend; decidir Kafka (deprecar o monitorear).
4. Features frontend Tutelas pendientes (DT-31.a–e).

---

## Riesgo y orden

- Fase 0 y 1 son **bajo riesgo / alto valor** — empezar por ahí.
- Fase 2 (RLS + código) toca runtime — hacer en staging primero, con tests.
- Fase 3 (D3 + merge) es la **más delicada** — ventana de inestabilidad real, requiere backup y validación post-deploy.
- Nada de esto bloquea la operación actual de ARC (que ya está ingiriendo de nuevo).
