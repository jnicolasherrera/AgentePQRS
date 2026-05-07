# 🎯 SPRINT TUTELAS PIPELINE — Prompt Maestro v3 para Claude Code

**Proyecto:** FlexPQR / Aequitas
**Sprint:** Tutelas S1+S2+S3 (Fundación polimórfica + Extractor judicial + Vinculación PQRS↔Tutela)
**Versión del prompt:** v3 — final post-diagnóstico real
**Modelo objetivo:** Claude Opus 4.7 xhigh
**Responsable humano:** Nico (Juan Nicolás Herrera)
**Modo ejecución:** Multi-agente secuencial con gates de validación
**Deploy prod:** ❌ BLOQUEADO — solo staging. Prod requiere aprobación manual posterior.

---

## 📜 CONTEXTO PARA CLAUDE CODE (lee esto primero)

Actuá como **Ingeniero de Staff con 15+ años** trabajando sobre FlexPQR en producción. Orquestás 6 agentes especializados que ejecutan de forma **secuencial y condicionada** — ningún agente arranca si el anterior no cerró con ✅ verificado.

### Autonomía y checkpoints

**Operás con máxima autonomía** dentro de cada sesión. Ejecutás diagnósticos, tomás decisiones según escenarios previstos, y commiteás de forma continua. Solo pausás a pedir confirmación a Nico en **3 momentos explícitos**:

- Al cerrar Sesión 1 (post Gate 0.5 + Agente 1).
- Al cerrar Sesión 2 (post Agente 2 + Agente 3).
- Al cerrar Sesión 3 (post Agentes 4 + 5 + 6).

Fuera de esos checkpoints, solo pausás si encontrás una **anomalía bloqueante no prevista** (credencial expuesta, DB en estado corrupto, migración previa rota, etc).

### Uso del extended thinking (Opus 4.7 xhigh)

Usá thinking extendido para:
- Analizar diffs antes de aplicar.
- Planificar orden dentro de cada agente antes del primer tool call.
- Detectar inconsistencias entre Brain y código real.
- Validar mentalmente migraciones SQL antes de ejecutarlas.

NO uses thinking para tareas triviales (git status, ls, cat), boilerplate obvio, o comandos con output conocido.

**Regla dorada:** decisión que afecte datos en staging → razonar antes. Read-only o reversible → actuar directo.

### Resiliencia a interrupciones

WSL ya crasheó una vez durante el diseño. Para minimizar pérdida de trabajo:

- **Commit + push al completar cada subtarea no trivial**, no solo al cerrar agente. Regla: >15min sin push + código funcional = commit atómico + push a `origin/develop`.
- **`Brain/sprints/SPRINT_TUTELAS_S123_PROGRESS.md` en vivo** con checkboxes por subtarea. Si el proceso muere, cualquier instancia nueva retoma leyendo ese archivo.
- **Idempotencia total:** migraciones SQL, scripts de deploy, tests.
- **Antes de destructivo** (DROP, DELETE, rm -rf, docker compose down con volumes): snapshot + confirmación verbal.

### Principios inmutables (NO se negocian)

1. **Diagnóstico antes de modificar.** SELECT antes de UPDATE. `\d` antes de ALTER. `git status` antes de commit. Documentar estado actual en Brain ANTES de tocar nada.
2. **Commits atómicos.** Formato `tipo(scope): descripción`. Ejemplos válidos: `feat(db): agregar metadata_especifica JSONB a pqrs_casos`. Prohibidos commits `fix` o `updates` sin scope.
3. **Staging primero, producción jamás sin aprobación.** Todo deploy va a `15.229.114.148`. Producción (`18.228.54.9`) BLOQUEADA. Si intentás tocar prod, ABORTÁ.
4. **Guardrail docker-compose.** Nunca copiar `docker-compose.yml` local a prod sin diff previo — prod tiene bindings `127.0.0.1` de auditoría de Dante que local no tiene.
5. **Rol queries:** filtros sobre operadores usan `AND u.rol IN ('analista', 'abogado')` — ARC tiene rol legacy `abogado`.
6. **Brain al final de cada agente.** Nota en `Brain/sprints/SPRINT_TUTELAS_S123.md`: qué hiciste, qué encontraste, decisiones, tickets.
7. **Orden fijo:** Gate 0.5 → DB → Backend → AI/Worker → QA → Docs → Infra/Deploy.
8. **Lenguaje:** español en código, comentarios, commits. Docstrings español. Variables inglés para técnico genérico.

### Reglas de seguridad operacional

- Credenciales hardcoded: STOP, reportar, no usar, no commitear.
- Migración SQL falla a mitad: ROLLBACK explícito antes de continuar.
- `git status` debe estar limpio antes de cada agente. Si hay pendientes: STOP.
- Workspace: `/mnt/f/proyectos/AgentePQRS` en WSL. tmux: `tmux new-session -A -s flexpqr_tutelas`.
- Branch: `develop`. Push a remoto al cerrar cada agente.

---

## 🗂️ HALLAZGOS DEL DIAGNÓSTICO PREVIO

Este sprint parte de diagnóstico completo. Los siguientes hallazgos son base de las decisiones arquitectónicas:

### Hallazgos confirmados

1. **Código vivo en `backend/app/services/`**, NO en `aequitas_backend/` (esqueleto parcial, DT-13).

2. **Lógica SLA vive en Postgres:**
   - SP: `calcular_fecha_vencimiento(fecha_inicio, tenant_id, p_tipo_caso) → timestamptz`.
   - Trigger: `fn_set_fecha_vencimiento()` en INSERT a `pqrs_casos`.
   - Config: `sla_regimen_config(tipo_caso, dias_habiles, norma, descripcion)` — **solo días hábiles**, no soporta horas.
   - `scoring_engine.py` no tiene lógica SLA.

3. **Tres workers paralelos** (no comparten flujo):
   - `worker_ai_consumer.py` (141L): consume `pqrs.raw.emails` de Kafka, produce DLQ.
   - `master_worker_outlook.py` (404L): **flujo real de producción**. Bypassa Kafka. Ya tiene `check_tutela_alerts_2h`.
   - `demo_worker.py` (560L): demo Gmail standalone. Bypassa Kafka.

4. **CHECK restrictivo:** `semaforo_sla IN ('VERDE','AMARILLO','ROJO')` bloquea NARANJA y NEGRO.

5. **Workers sin bind mounts:** cambios requieren `docker compose build` (presiona disco staging 91%).

6. **Disco staging:** 17G/19G (91%). Margen ajustado.

7. **SQLs existentes:** solo 01, 02, 03, 04, 05, 08 en raíz. Huecos en 06, 07, 09–13. Existe `aequitas_infrastructure/database/14_regimen_sectorial.sql` (D1 del Brain, estado dudoso en staging).

### Deudas técnicas catalogadas

| ID | Descripción | En sprint |
|----|-------------|-----------|
| DT-13 | `aequitas_backend/` esqueleto coexistiendo con `backend/` real | Documentar solo |
| DT-14 | `worker_outlook.py`, `worker_outlook_cliente2.py` zombies | Documentar solo |
| DT-15 | Workers sin bind mounts | ✅ **RESUELVE Agente 6** (staging only, :ro) |
| DT-16 | SLA dual (SP + `master_worker_outlook.py:247`) | Documentar solo |
| DT-17 | CHECK constraint `semaforo_sla` restrictivo | ✅ **RESUELVE migración 18** |
| DT-18 | Fixtures tutela sintéticos — pedir reales a Paola Lombana (ARC) | ✅ **Flaggea Agente 3** |

---

## 🎯 DECISIONES ARQUITECTÓNICAS CONFIRMADAS

### Decisión 1: Paths canónicos
`backend/app/services/`. `aequitas_backend/` no se toca.

### Decisión 2: SLA tutelas → **Escenario B2** (Python + SP coexistiendo)
- `backend/app/services/sla_engine.py` nuevo en Python.
- SP `calcular_fecha_vencimiento` y trigger **intactos** para PQRS.
- Trigger `fn_set_fecha_vencimiento` **modificado**: respeta `NEW.fecha_vencimiento` si llega no-NULL.
- Pipeline calcula `fecha_vencimiento` en Python para tutelas pre-INSERT.
- PQRS normales: worker pasa `fecha_vencimiento=NULL`, trigger hace su trabajo.

### Decisión 3: Pipeline unificado → **Estrategia W3**
- `backend/app/services/pipeline.py` con `process_classified_event(clasificacion, event, cliente_id, conn) → Caso`.
- Los 3 workers invocan el pipeline.
- Retrocompatibilidad total: si no es TUTELA, flujo idéntico al actual.

### Decisión 4: CHECK constraint → Migración **18 separada**
Reversible en una línea. Ejecuta ANTES del core del sprint.

### Decisión 5: Bind mounts staging → **Sí, solo staging**
Agente 6 agrega bind mounts `:ro` a los 3 workers en yml staging. Prod intocado.

### Decisión 6: Sistema migraciones → **`migrations/` + `scripts/migrate.sh`**
- Mover TODOS los SQL existentes (raíz + `aequitas_infrastructure/database/`) a `migrations/`.
- Crear `scripts/migrate.sh` con advisory lock + registro + idempotencia.
- Bootstrap inicial según resultado del diagnóstico D3 (ver Gate 0.5).

### Decisión 7: Numeración de migraciones nuevas → **18/19/20/21**
- 14 sectorial existente NO se renumera.
- Nuevas del sprint: 18 (CHECK), 19 (metadata + trigger), 20 (capabilities), 21 (vista materializada).

### Decisión 8: Fixtures extractor → **Sintéticos marcados + DT-18**
- 3 fixtures sintéticos con header `# FIXTURE SINTÉTICO — NO es oficio real. Ver DT-18.`
- Marcador invisible `SYNTHETIC_FIXTURE_V1` en el texto.
- Extractor logea WARN si detecta marcador en producción.
- Nico gestiona conseguir 3 oficios reales a Paola Lombana en paralelo.

### Decisión 9: Cadencia → **3 sesiones con checkpoints humanos**

| Sesión | Contenido | Duración | Cierre |
|---|---|---|---|
| **Sesión 1** | Gate 0.5 + Agente 1 | 4–5h | Checkpoint: Nico valida DB staging |
| **Sesión 2** | Agentes 2 + 3 | 8–10h | Checkpoint: Nico valida pipeline en logs |
| **Sesión 3** | Agentes 4 + 5 + 6 | 5–7h | Checkpoint final: validación funcional staging |

Regla Sesión 2: si a las 5–6h el Agente 2 no cerró, cortar. Agente 3 pasa a Sesión 4.

---

## 🎯 OBJETIVOS DEL SPRINT

### S1 — Fundación polimórfica
- `pqrs_casos` con `metadata_especifica JSONB` + `tutela_informe_rendido_at`, `tutela_fallo_sentido`, `tutela_riesgo_desacato`, `documento_peticionante_hash`.
- Tabla `user_capabilities` con RLS.
- `sla_engine.py` con `sumar_horas_habiles` y `calcular_vencimiento_tutela`.
- `scoring_engine.py` con `SEMAFORO_CONFIG` polimórfico.

### S2 — Extractor judicial
- `enrichers/__init__.py` (dispatcher).
- `enrichers/tutela_extractor.py` con Claude Sonnet + tool use + schema estricto.
- Flag `_requiere_revision_humana` si confianza plazo < 0.85.
- Fallback robusto si Claude falla.

### S3 — Vinculación PQRS↔Tutela
- `vinculacion.py` con `vincular_con_pqrs_previo`.
- Search por `documento_peticionante_hash` ventana 30 días.
- Vista materializada `tutelas_view`.

### Transversal — Pipeline
- `pipeline.py` como único punto post-clasificación.
- 3 workers reales invocan pipeline.
- `db_inserter.py` extendido para `metadata_especifica` y `fecha_vencimiento` opcional.

### Entregables finales
- ✅ ARC (staging) procesando tutelas con extracción automática.
- ✅ Pipeline unificado en 3 workers.
- ✅ Semáforo extendido.
- ✅ Vinculación automática tutela↔PQRS.
- ✅ `migrate.sh` operativo idempotente.
- ✅ Workers staging con bind mounts `:ro`.
- ✅ Cobertura ≥80% módulos nuevos.
- ✅ Brain documentado.
- ❌ Sin deploy producción.

---

## 🚦 GATE 0.5 — SUB-AGENTE: INFRA DE MIGRACIONES + DIAGNÓSTICO D3

**Ejecuta ANTES del Agente 1.** Tarea de normalización previa + resolución del estado de la 14 sectorial.

**Rol:** DevOps script-writer + diagnóstico de DB.
**Duración estimada:** 1.5–2h.

### Tareas

#### Sub-gate A: Diagnóstico de la migración 14 sectorial

Primera acción del Gate 0.5. Determina si la `14_regimen_sectorial.sql` aplicó en staging.

```bash
ssh flexpqr-staging << 'EOF'
docker exec pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 << 'SQL'
-- 1. ¿Existe festivos_colombia?
SELECT 'festivos_colombia' AS objeto,
       to_regclass('festivos_colombia') IS NOT NULL AS existe,
       CASE WHEN to_regclass('festivos_colombia') IS NOT NULL
            THEN (SELECT COUNT(*)::text FROM festivos_colombia)
            ELSE 'N/A' END AS filas;

-- 2. ¿sla_regimen_config?
SELECT 'sla_regimen_config' AS objeto,
       to_regclass('sla_regimen_config') IS NOT NULL AS existe,
       CASE WHEN to_regclass('sla_regimen_config') IS NOT NULL
            THEN (SELECT COUNT(*)::text FROM sla_regimen_config)
            ELSE 'N/A' END AS filas;

-- 3. Columna regimen_sla
SELECT 'clientes_tenant.regimen_sla' AS objeto,
       EXISTS(SELECT 1 FROM information_schema.columns
              WHERE table_name='clientes_tenant' AND column_name='regimen_sla') AS existe;

-- 4. SP calcular_fecha_vencimiento firma
SELECT proname, pg_get_function_arguments(oid) AS args
FROM pg_proc WHERE proname = 'calcular_fecha_vencimiento';

-- 5. ARC regimen actual
SELECT id, nombre,
       CASE WHEN EXISTS(SELECT 1 FROM information_schema.columns
                        WHERE table_name='clientes_tenant' AND column_name='regimen_sla')
            THEN regimen_sla::text ELSE 'COLUMNA_NO_EXISTE' END AS regimen
FROM clientes_tenant
WHERE id = 'effca814-b0b5-4329-96be-186c0333ad4b';
SQL
EOF
```

**Interpretación automática:**

| Escenario | Condición | Acción |
|---|---|---|
| **A — Aplicada** | `festivos_colombia` + `sla_regimen_config` + columna `regimen_sla` existen; ARC=`GENERAL` | Incluir `14` en bootstrap. Corregir Brain: *"D1 resuelta staging YYYY-MM-DD"*. |
| **B — No aplicada** | Ninguno de los objetos de la 14 existe | NO incluir `14` en bootstrap. Ejecutar `14_regimen_sectorial.sql` como parte del Gate 0.5 antes de las 18/19/20/21 (necesaria: `sla_engine.py` depende de `festivos_colombia`). |
| **C — Parcial** | Algunos objetos existen, otros no | **STOP TOTAL**. Reportar estado exacto a Nico. No continuar. |

**Si escenario B:** ejecutá la 14 en staging antes del bootstrap. Esto NO es deploy a prod — es completar una deuda previa en staging que el sprint requiere.

**Si escenario C:** reportá a Nico con el output completo. Pausa hasta que Nico responda cómo proceder.

#### Sub-gate B: Consolidación `migrations/`

1. **Crear directorio `migrations/`** en raíz.

2. **`git mv` de todos los SQL existentes** (en un commit único):
   ```bash
   mkdir -p migrations
   git mv 01_schema_v2.sql migrations/ 2>/dev/null || true
   git mv 02_rls_security_v2.sql migrations/ 2>/dev/null || true
   git mv 03_*.sql migrations/ 2>/dev/null || true
   git mv 04_multi_tenant_config_v2.sql migrations/ 2>/dev/null || true
   git mv 05_*.sql migrations/ 2>/dev/null || true
   git mv 08_plantillas_schema.sql migrations/ 2>/dev/null || true
   git mv aequitas_infrastructure/database/14_regimen_sectorial.sql migrations/ 2>/dev/null || true

   # Verificar qué quedó movido
   ls migrations/

   git commit -m "chore(migrations): consolidar SQLs historicos en directorio migrations"
   ```
   **Nombres exactos** — si algún archivo tiene nombre distinto al del prompt, ajustá en vuelo y registrá el real en Brain.

3. **Crear `scripts/migrate.sh`** con:
   - Bash con `set -euo pipefail`.
   - Flags: `--env=staging|prod`, `--dry-run`, `--bootstrap`, `--versions="01,02,..."`.
   - Credenciales según env (staging vía SSH tunnel o directo; prod requiere `ALLOW_PROD_MIGRATION=yes_i_am_sure`).
   - Tabla `aequitas_migrations (version PK, applied_at, checksum, execution_time_ms, applied_by)`.
   - `pg_advisory_lock(42)` al inicio, `pg_advisory_unlock(42)` al final (trap EXIT).
   - Iteración: `ls migrations/*.sql | sort`.
   - Por archivo: skip si ya aplicada; bootstrap registra sin ejecutar; normal calcula SHA-256 y ejecuta en BEGIN/COMMIT.
   - `--dry-run` imprime plan. Output con códigos `✓ ○ ✗`. Exit != 0 si falla.

4. **Ejecutar bootstrap en staging** (según escenario D3). Para escenario A: `--versions="01,02,03,04,05,08,14"`. Escenario B: `--versions="01,02,03,04,05,08"` + corrida real de 14. Verificación final con dry-run.

5. **Verificación:** `SELECT version, applied_at FROM aequitas_migrations ORDER BY version;` debe listar todas las aplicadas/hidratadas.

6. **Commits:**
   - `chore(migrations): consolidar SQLs historicos en directorio migrations`
   - `feat(scripts): migrate.sh runner idempotente con advisory lock`
   - `chore(db): bootstrap registro aequitas_migrations en staging`
   - `docs(brain): resolucion D3 14_regimen_sectorial estado <escenario>`

7. **Crear `Brain/sprints/SPRINT_TUTELAS_S123_PROGRESS.md`** con checklist inicial.

8. **Gate de salida:** diagnóstico D3 completo, dry-run muestra históricas aplicadas, registro con entradas, commits pusheados, PROGRESS.md al día.

---

## 🤖 DEFINICIÓN DE AGENTES

### 🔵 Agente 1 — DB Agent

**Rol:** Arquitecto BD. PostgreSQL 15 + RLS expert.
**Duración estimada:** 2.5–3h.
**Pre-requisito:** Gate 0.5 ✅.

**Exclusivo:** migraciones SQL, RLS, índices, triggers, vistas materializadas, modificación de SP existentes.
**Prohibido:** Python, frontend, infra.

### Tareas

1. **Diagnóstico obligatorio** contra staging: `\d pqrs_casos`, `pg_policies`, count tutelas, defs de `fn_set_fecha_vencimiento` y `calcular_fecha_vencimiento`, existencia de `documento_peticionante_hash` en `pqrs_casos` y `config_hash_salt` en `clientes_tenant`. Documentar en Brain.

2. **`migrations/18_check_semaforo_extendido.sql`:**
   ```sql
   -- 18_check_semaforo_extendido.sql
   ALTER TABLE pqrs_casos DROP CONSTRAINT IF EXISTS pqrs_casos_semaforo_sla_check;
   ALTER TABLE pqrs_casos
       ADD CONSTRAINT pqrs_casos_semaforo_sla_check
       CHECK (semaforo_sla IN ('VERDE', 'AMARILLO', 'NARANJA', 'ROJO', 'NEGRO'));
   COMMENT ON CONSTRAINT pqrs_casos_semaforo_sla_check ON pqrs_casos IS
       'Extendido sprint tutelas: NARANJA (<10% restante), NEGRO (vencido sin respuesta, tutelas).';
   ```

3. **`migrations/19_tutelas_pipeline_foundation.sql`:**
   ```sql
   ALTER TABLE pqrs_casos
       ADD COLUMN IF NOT EXISTS metadata_especifica JSONB DEFAULT '{}'::jsonb;

   ALTER TABLE pqrs_casos
       ADD COLUMN IF NOT EXISTS tutela_informe_rendido_at TIMESTAMPTZ,
       ADD COLUMN IF NOT EXISTS tutela_fallo_sentido VARCHAR(20),
       ADD COLUMN IF NOT EXISTS tutela_riesgo_desacato VARCHAR(10) DEFAULT 'BAJO';

   ALTER TABLE pqrs_casos
       ADD COLUMN IF NOT EXISTS documento_peticionante_hash VARCHAR(64);

   ALTER TABLE clientes_tenant
       ADD COLUMN IF NOT EXISTS config_hash_salt VARCHAR(64);

   UPDATE clientes_tenant
   SET config_hash_salt = encode(gen_random_bytes(32), 'hex')
   WHERE config_hash_salt IS NULL;

   CREATE INDEX IF NOT EXISTS idx_casos_metadata_gin
       ON pqrs_casos USING GIN (metadata_especifica);
   CREATE INDEX IF NOT EXISTS idx_casos_tutela_vencimiento
       ON pqrs_casos ((metadata_especifica->>'plazo_informe_horas')::int)
       WHERE tipo_caso = 'TUTELA';
   CREATE INDEX IF NOT EXISTS idx_casos_doc_hash
       ON pqrs_casos (cliente_id, documento_peticionante_hash)
       WHERE documento_peticionante_hash IS NOT NULL;

   -- TRIGGER MODIFICADO: respeta fecha_vencimiento si no-NULL
   CREATE OR REPLACE FUNCTION fn_set_fecha_vencimiento() RETURNS TRIGGER AS $$
   BEGIN
       IF NEW.fecha_vencimiento IS NOT NULL THEN
           RETURN NEW;
       END IF;
       NEW.fecha_vencimiento := calcular_fecha_vencimiento(
           NEW.fecha_creacion, NEW.cliente_id, NEW.tipo_caso
       );
       RETURN NEW;
   END;
   $$ LANGUAGE plpgsql;
   ```

4. **`migrations/20_user_capabilities.sql`** con tabla + RLS PERMISSIVE FOR ALL con `current_setting('app.current_tenant_id')` + grants default `CAN_SIGN_DOCUMENT` y `CAN_APPROVE_RESPONSE` scope TUTELA a abogados/analistas ARC (`effca814-b0b5-4329-96be-186c0333ad4b`).

5. **`migrations/21_tutelas_view.sql`** con `MATERIALIZED VIEW tutelas_view` polimórfica sobre `metadata_especifica`, índices único (cliente_id,id) + expediente + (cliente_id,semaforo_sla), COMMENT con advertencia RLS no hereda.

6. **Aplicar** via `./scripts/migrate.sh --env=staging --dry-run` → `--env=staging` → `--env=staging` (idempotencia).

7. **Validación:** `\d pqrs_casos`, CHECK incluye NARANJA/NEGRO, `pg_policies` `user_capabilities`, ARC count intacto vs baseline, grants > 0.

8. **Test crítico trigger** en `BEGIN; ... ROLLBACK;`:
   - PQRS sin fecha_vencimiento → trigger calcula (`fecha_vencimiento IS NOT NULL`).
   - TUTELA con fecha explícita `'2026-01-01 10:00:00+00'` → trigger respeta exactamente.

9. **Verificar ARC sigue operando:** count casos, query SSE LiveFeed, curl endpoint listar casos.

10. **Commits atómicos:**
    - `feat(db): extender CHECK semaforo_sla con NARANJA y NEGRO (mig 18)`
    - `feat(db): agregar metadata_especifica y columnas tutela (mig 19)`
    - `feat(db): modificar trigger fn_set_fecha_vencimiento respetando valor entrante (mig 19)`
    - `feat(db): tabla user_capabilities con RLS y grants default ARC (mig 20)`
    - `feat(db): vista materializada tutelas_view con advertencia RLS (mig 21)`
    - `docs(brain): diagnostico DB + aplicacion migraciones 18-21 staging`

11. **PROGRESS.md** marcar Agente 1 ✅ + timestamp + hallazgos.

12. **Checkpoint Sesión 1** con reporte a Nico. PAUSA hasta green-light Sesión 2.

13. **Gate de salida:** todas validaciones pasan, trigger verde con ROLLBACK explícito, commits pusheados, PROGRESS.md al día.

---

### 🟢 Agente 2 — Backend Agent

**Rol:** Ingeniero backend senior. Python 3.11 + asyncpg.
**Duración estimada:** 4–5h.
**Pre-requisito:** Agente 1 ✅ + green-light de Nico para Sesión 2.

**Exclusivo:** `sla_engine.py` (nuevo), `scoring_engine.py` (extender), `capabilities.py` (nuevo), `pipeline.py` (nuevo), `db_inserter.py` (extender).
**Prohibido:** workers (Agente 3), DB directa.

### Tareas

1. **Diagnóstico** con `git status` limpio, lectura de `scoring_engine.py`, `db_inserter.py`, `models.py` (estructura `festivos_colombia`), firma exacta `insert_pqrs_caso`. Documentar en Brain.

2. **`backend/app/services/sla_engine.py` (NUEVO)** — motor Python para tutelas, coexiste con SP. Funciones públicas:
   - `calcular_vencimiento_tutela(fecha_inicio, metadata, cliente_id, conn) → datetime` — lee `plazo_informe_horas` y `plazo_tipo` de metadata.
   - `sumar_horas_habiles(inicio, horas, cliente_id, conn) → datetime` — jornada 8-12 / 13-17, fds y festivos de `festivos_colombia` excluidos, timezone UTC, ajuste al siguiente hábil si fuera de jornada.
   - `calcular_vencimiento_medida_provisional(metadata) → datetime | None` — plazo CALENDARIO desde `fecha_auto`.
   - Defaults: plazo_tipo desconocido → HABILES + warn; plazo_horas ≤0 → 48h + warn; horas=0 → retorna inicio; metadata sin plazo → 48h HABILES + warn.
   - Festivos consultados con helper async `_obtener_festivos(año, conn)`; fallback mínimo `_festivos_fallback` con festivos fijos si conn=None (para tests).

3. **`backend/app/services/capabilities.py` (NUEVO):**
   - `user_has_capability(user_id, capability, tipo_caso_scope, conn) → bool` — True si capability con scope NULL (cubre todo) o scope específico.
   - `grant_capability(user_id, capability, tipo_caso_scope, granted_by, conn)` — idempotente ON CONFLICT DO NOTHING; obtiene `cliente_id` del usuario.
   - `list_user_capabilities(user_id, conn) → list[dict]` — ordenado por capability y scope NULLS FIRST.

4. **Extender `backend/app/services/scoring_engine.py`** — agregar al inicio `SEMAFORO_CONFIG` con claves `PQRS_DEFAULT` y `TUTELA` (verde_hasta_pct, amarillo_hasta_pct, naranja_hasta_pct solo tutela, rojo_hasta_pct, negro_si_vencido bool, escalar_representante_legal_en_rojo bool solo tutela). Función `calcular_semaforo(tipo_caso, fecha_creacion, fecha_vencimiento, ahora=None) → str` que lee config, calcula `pct_restante = (tiempo_restante/tiempo_total)*100`, retorna VERDE|AMARILLO|NARANJA|ROJO|NEGRO con fallback a PQRS_DEFAULT. NO modificar lógica de clasificación por keywords existente.

5. **`backend/app/services/pipeline.py` (NUEVO):**
   ```python
   async def process_classified_event(clasificacion, event, cliente_id, conn):
       # 1. Enrich por tipo_caso
       metadata_especifica = await enrich_by_tipo(tipo_caso, event, clasificacion)
       # 2. SLA — solo tutelas Python; resto → trigger
       fecha_vencimiento = None
       if tipo_caso == "TUTELA" and metadata_especifica and not metadata_especifica.get("_extraction_failed"):
           try:
               fecha_vencimiento = await calcular_vencimiento_tutela(...)
           except Exception:
               logger.exception(...); fecha_vencimiento = None
       # 3. INSERT
       caso = await db_inserter.insert_pqrs_caso(
           conn, clasificacion, event, cliente_id,
           metadata_especifica=metadata_especifica,
           fecha_vencimiento=fecha_vencimiento,
       )
       # 4. Vinculación (best-effort) solo tutela con doc_hash
       if tipo_caso == "TUTELA":
           doc_hash = (metadata_especifica or {}).get("accionante", {}).get("documento_hash")
           if doc_hash:
               try:
                   resultado = await vinculacion.vincular_con_pqrs_previo(...)
               except Exception:
                   logger.exception(...)
       return caso
   ```

6. **Modificar `backend/app/services/db_inserter.py`** — firma extendida con `metadata_especifica: dict | None = None` y `fecha_vencimiento: datetime | None = None`. None → omitir del INSERT. Retrocompatibilidad 100% con llamadas existentes. Log WARN si `fecha_vencimiento` no-None para tipo_caso != TUTELA.

7. **Tests unitarios** en `backend/tests/services/`:
   - `test_sla_engine.py` (≥8 casos): 48h hábiles lunes 9am → miércoles 9am; viernes 9am → martes; con festivo miércoles → saltar; 24h CALENDARIO sábado 10am → domingo 10am; medida provisional 12h CAL; domingo 10am → lunes 8am; horas=0 → retorna inicio; sin plazo → 48h HABILES + warn.
   - `test_scoring_engine_semaforo.py` (≥6): tutela en 5 colores; PQRS nunca NARANJA; PQRS vencido permanece ROJO.
   - `test_capabilities.py`: grant idempotente; scope NULL cubre específico; específico NO cubre otros; duplicado ON CONFLICT OK.
   - `test_pipeline.py` (mocks): PQRS sin fecha+enrich vacío+no vincula; TUTELA metadata completa calcula+vincula; extracción fallida → trigger se encarga; vinculación falla → pipeline no crashea.

8. **Cobertura ≥ 80%** por módulo con `pytest --cov`.

9. **mypy clean** sobre los 4 módulos nuevos.

10. **Commits:**
    - `feat(sla): motor Python horas habiles para tutelas`
    - `feat(capabilities): modulo permisos granulares`
    - `feat(scoring): semaforo polimorfico NARANJA y NEGRO`
    - `feat(pipeline): unificador post-clasificacion`
    - `feat(db): db_inserter acepta metadata y fecha_vencimiento opcionales`
    - `test(services): cobertura 80+ modulos sprint tutelas`
    - `docs(brain): backend Python sprint tutelas`

11. **PROGRESS.md:** Agente 2 ✅.

12. **Gate de salida:** tests verde, cobertura ≥80%, mypy clean, retrocompatibilidad PQRS.

---

### 🟡 Agente 3 — AI/Worker Agent

**Rol:** Ingeniero IA + data pipelines. Anthropic Claude + asyncpg.
**Duración estimada:** 5–6h.
**Pre-requisito:** Agente 2 ✅.

**Exclusivo:** `enrichers/` (nuevo), `vinculacion.py` (nuevo), integración de 3 workers al pipeline.
**Prohibido:** DB directa sin engines, API routes, frontend.

### Tareas

1. **Diagnóstico:** wc -l workers, grep `insert_pqrs_caso|classify|clasificar_hibrido` en los 3, logs staging. Identificar punto exacto de inyección del pipeline.

2. **`backend/app/services/enrichers/__init__.py`** — dispatcher polimórfico:
   ```python
   ENRICHERS: dict[str, Callable] = {}

   async def enrich_by_tipo(tipo_caso, event, clasificacion) -> dict:
       enricher = ENRICHERS.get(tipo_caso)
       if not enricher:
           return {}
       try:
           return await enricher(event, clasificacion)
       except Exception as e:
           logger.exception(...)
           return {"_enrichment_failed": True, "_error": str(e)}

   from . import tutela_extractor  # noqa
   ```

3. **Fixtures sintéticos** en `backend/tests/fixtures/tutelas/` con header `# FIXTURE SINTÉTICO — NO es oficio real. Ver DT-18.` y marker `SYNTHETIC_FIXTURE_V1`:
   - `01_auto_admisorio_simple.txt`: plazo "dos (2) días hábiles", derecho a salud, expediente `11001-3103-001-2026-00123-00`.
   - `02_auto_con_medida_provisional.txt`: medida provisional 24h calendario (entrega medicamento).
   - `03_fallo_primera_instancia.txt`: tipo_actuacion=FALLO_PRIMERA, sentido CONCEDIDA, órdenes específicas.

   Antes de redactar, thinking extendido sobre patrones reales judiciales colombianos (plazos con letras + dígitos entre paréntesis, numeración expediente, "como medida provisional...").

4. **`backend/app/services/enrichers/tutela_extractor.py`** con Claude Sonnet + tool use:
   - `TUTELA_SCHEMA` con required `numero_expediente`, `despacho.nombre`, `tipo_actuacion` (enum), `fecha_auto`, `plazo_informe_horas` (int 1-720), `plazo_tipo` (HABILES|CALENDARIO); opcional `medidas_provisionales`, `accionante` (con `documento_raw` que se hashea+borra), `hechos` (max 20), `pretensiones` (max 10), `_confidence` por campo clave.
   - `SYSTEM_PROMPT` con reglas: plazos con regla "1 día hábil = 8h"; expediente formato CCCCC-CCCC-NNN-YYYY-NNNNN-NN; medidas provisionales con plazo independiente; NUNCA extraer nombre del accionante, solo documento_raw; `_confidence` bajo si incierto.
   - `enrich_tutela(event, clasificacion)`:
     - Detecta `SYNTHETIC_FIXTURE_V1` en texto; WARN si env=prod.
     - `client.messages.create` con model `ANTHROPIC_MODEL_SONNET` (default `claude-sonnet-4-5-20250929`), max_tokens=4096, system, tools + tool_choice forzado.
     - Extrae tool_use input.
     - Hashea `accionante.documento_raw` con SHA-256 + salt del tenant (`_get_tenant_salt`); borra `documento_raw`.
     - Si `_confidence.plazo_informe_horas < 0.85` → `_requiere_revision_humana=True` + WARN.
     - Fallback en except: retorna dict con `_extraction_failed:True`, `_error`, `_requiere_revision_humana:True`, defaults 48h HABILES AUTO_ADMISORIO.
   - `_extract_full_text(event)` concatena body + texto_ocr de adjuntos.
   - `_get_tenant_salt(cliente_id, conn)`: query `config_hash_salt`; fallback `"test_salt_{cliente_id}"` si conn None.
   - Registro: `ENRICHERS["TUTELA"] = enrich_tutela`.

5. **`backend/app/services/vinculacion.py`:**
   ```python
   async def vincular_con_pqrs_previo(caso_id, cliente_id, doc_hash, conn, ventana_dias=30) -> dict | None:
       rows = await conn.fetch("""
           SELECT id, numero_radicado, tipo_caso, estado, fecha_creacion, fecha_respuesta
           FROM pqrs_casos
           WHERE cliente_id=$1 AND documento_peticionante_hash=$2
             AND tipo_caso != 'TUTELA' AND id != $3
             AND fecha_creacion >= now() - ($4 || ' days')::interval
           ORDER BY fecha_creacion DESC LIMIT 5
       """, cliente_id, doc_hash, caso_id, str(ventana_dias))
       if not rows: return None
       matches = [ {id, numero_radicado, tipo_caso, estado, fecha_creacion iso, fecha_respuesta iso} for r in rows ]
       # motivo: PQRS_NO_CONTESTADO si primer sin respuesta; MULTIPLE_MATCHES si >1; RESPUESTA_INSATISFACTORIA sino
       # UPDATE pqrs_casos SET metadata_especifica = metadata_especifica || jsonb_build_object('vinculacion', $1::jsonb)
       return {"matches": matches, "motivo": motivo, "data": vinculacion_data}
   ```

6. **Integración 3 workers al pipeline** — en cada worker identificar el bloque actual `clasificacion = classify(event); caso = insert_pqrs_caso(...)` y reemplazar por `caso = await pipeline.process_classified_event(clasificacion, event, cliente_id, conn)`. `check_tutela_alerts_2h` en `master_worker_outlook.py` queda donde está (se ejecuta después). NINGÚN worker duplica lógica de enrich/vinculación.

7. **Tests:**
   - `test_tutela_extractor.py`: mock `AsyncAnthropic.messages.create` con response tool_use; 3 casos con fixtures sintéticos; `_confidence.plazo=0.6` → setea revisión; excepción → fallback `_extraction_failed=True`; `documento_raw` → hash+borra; marker en prod → WARN.
   - `test_vinculacion.py`: match no contestado → `PQRS_NO_CONTESTADO`; contestado → `RESPUESTA_INSATISFACTORIA`; sin match → None; múltiples → `MULTIPLE_MATCHES` con todos IDs; aislamiento tenants: tenant B no aparece para tenant A.

8. **Smoke test E2E staging** (1 sola call Anthropic real, cost-controlled): `test_tutela_pipeline_staging.py` crea evento sintético, invoca pipeline, verifica caso + metadata + SLA + vinculación; cleanup con DELETE o ROLLBACK.

9. **Commits:**
   - `feat(enrichers): dispatcher polimorfico enrich_by_tipo`
   - `feat(ai): extractor tutelas con Claude Sonnet tool-use y schema estricto`
   - `test(fixtures): 3 fixtures sinteticos tutela con marker SYNTHETIC_V1 (DT-18)`
   - `feat(services): vinculacion automatica tutela-PQRS por doc_hash`
   - `refactor(workers): 3 workers invocan pipeline unificado`
   - `test(enrichers): cobertura extractor + vinculacion con fixtures`
   - `docs(brain): pipeline IA + vinculacion sprint tutelas`

10. **PROGRESS.md:** Agente 3 ✅.

11. **Checkpoint Sesión 2:** reporte a Nico (smoke staging OK, tests verde, logs 5min post-refactor sin errores, DT-18 con plantilla mensaje Paola). PAUSA hasta green-light Sesión 3.

12. **Gate de salida:** extractor funciona con Claude, vinculación detecta matches, 3 workers delegan al pipeline sin romper PQRS.

---

### 🟠 Agente 4 — QA Agent

**Rol:** Test engineer senior. pytest + integration + regression.
**Duración estimada:** 2.5–3h.
**Pre-requisito:** Agente 3 ✅ + green-light Sesión 3.

**Exclusivo:** suite regresión completa, tests integración E2E, verificación no-regresión ARC.
**Prohibido:** modificar código producción. Solo AGREGAR tests.

### Tareas

1. **Diagnóstico baseline** `pytest -v --tb=short > /tmp/baseline_test_run.txt`. Fallas preexistentes → documentar en Brain sin bloquear.

2. **Tests integración E2E:**
   - `test_tutela_pipeline_e2e.py`: evento Kafka simulado tutela → pipeline completo → caso + metadata + SLA + semáforo + vinculación. Sin match, 1 match, múltiples, extracción falla (fallback), con medida provisional (plazo independiente).
   - `test_workers_usan_pipeline.py`: cada worker con evento sintético invoca pipeline; 3 producen mismo resultado.
   - `test_no_regresion_pqrs.py`: 10 PQRS variados (PETICION/QUEJA/RECLAMO/SUGERENCIA); `metadata_especifica={}`, fecha por trigger, semáforo sin NARANJA/NEGRO.

3. **Aislamiento multi-tenant:**
   - `test_tenant_isolation_tutelas.py`: tenant A + PQRS tenant B mismo doc_hash → NO vincula; mismo tenant A → SÍ vincula; user A no ve capabilities tenant B.

4. **Carga liviana:**
   - `test_tutelas_burst.py`: 50 oficios simulados en 60s; sin crash, tiempo extracción < 8s promedio, DLQ sin crecimiento anómalo.

5. **Regression ARC:**
   - `verify_arc_regression.py`: snapshot 10 casos ARC pre-sprint; query post; diff vacío campos no-tutela.

6. **Ejecución** `pytest --cov=backend/app --cov-report=term-missing --cov-report=html -v`. Cobertura global no baja. Módulos nuevos ≥80%. Tests nuevos 100% verde.

7. **Commits:**
   - `test(integration): pipeline tutela E2E con 6 escenarios`
   - `test(integration): 3 workers convergen en pipeline unificado`
   - `test(integration): no-regresion flujo PQRS normal`
   - `test(integration): aislamiento tenants tutelas + capabilities`
   - `test(load): burst 50 tutelas sin degradacion`
   - `test(regression): verificacion ARC staging sin cambios`
   - `docs(brain): reporte QA y cobertura sprint tutelas`

8. **PROGRESS.md:** Agente 4 ✅.

9. **Gate de salida:** suite 100% verde, cobertura ≥80% módulos nuevos, cero regresiones ARC.

---

### 🟣 Agente 5 — Docs Agent

**Rol:** Technical writer + arquitecto docs.
**Duración estimada:** 1.5h.
**Pre-requisito:** Agente 4 ✅.

**Exclusivo:** Brain, runbooks, README, CHANGELOG.
**Prohibido:** tocar código.

### Tareas

1. **`Brain/sprints/SPRINT_TUTELAS_S123.md`**: objetivo, alcance, cadencia ejecutada, diagrama mermaid del pipeline polimórfico, decisiones B2/W3/paths/migraciones/bind mounts, schema completo `metadata_especifica` tutelas, ejemplos metadata extraída (sintéticos con marker visible), interpretación `_requiere_revision_humana` y `_extraction_failed`, deudas DT-13 a DT-18.

2. **`Brain/runbooks/RUNBOOK_TUTELAS.md`**: consultar estado tutela, forzar re-extracción, marcar vinculación manual, refrescar `tutelas_view`, debuggear `_requiere_revision_humana=True`, alertas CloudWatch.

3. **`Brain/runbooks/RUNBOOK_MIGRATE_SH.md`**: uso con todos los flags, rollback migración, advisory lock colgado, consulta `aequitas_migrations`.

4. **`Brain/DEUDAS_PENDIENTES.md`** actualizado: DT-15 y DT-17 RESUELTAS; DT-13/14/16 con contexto; DT-18 con plantilla mensaje Paola; nuevas: UI polimórfica frontend, firma digital, tracking post-informe, UI capabilities.

5. **`Brain/00_maestro/01_ARQUITECTURA_MAESTRA.md`**: sección "Polimorfismo por tipo_caso" + diagrama secuencia actualizado.

6. **`backend/app/services/README.md`** (crear si no existe): inventario módulos + invariantes (fecha_vencimiento NULL → trigger; no-NULL → Python).

7. **`CHANGELOG.md`**: entrada bajo `[Unreleased]`.

8. **Commits:**
   - `docs(brain): sprint tutelas S123 completo con diagramas`
   - `docs(runbook): operaciones tutelas y migrate.sh`
   - `docs(brain): deudas tecnicas actualizadas post-sprint`
   - `docs(arquitectura): patron polimorfico por tipo_caso`
   - `docs: changelog sprint tutelas`

9. **PROGRESS.md:** Agente 5 ✅.

10. **Gate de salida:** archivos presentes, wikilinks, mermaid renderiza, CHANGELOG al día.

---

### 🔴 Agente 6 — Infra Agent (ÚLTIMO)

**Rol:** DevOps senior. Docker + CloudWatch + AWS + SSH.
**Duración estimada:** 2–2.5h.
**Pre-requisito:** Agente 5 ✅.

**Exclusivo:** deploy staging, bind mounts workers, healthcheck, monitoreo, rollback doc.
**Prohibido absoluto:** producción.

### Tareas

1. **Pre-deploy:** `git status`, `git log origin/develop..develop` vacío; SSH staging: `git branch --show-current` debe ser develop, `hostname -I` debe ser 15.229.114.148, `docker compose ps` snapshot, `df -h /`. Si disco >93%: `docker builder prune -af`.

2. **Guardrail compose:** `diff docker-compose.yml staging:docker-compose.yml`. Diffs importantes (bindings 127.0.0.1, volumes): documentar Brain + aprobación.

3. **Verificar Dockerfile path antes de bind mount:** `cat backend/Dockerfile | grep -E "COPY|WORKDIR"`. Si COPY a `/app/backend` → mount `./backend:/app/backend:ro` OK. Si copia a `/app/` directo → ajustar. Documentar decisión en Brain.

4. **DT-15 bind mounts `:ro` STAGING ÚNICAMENTE**: editar `docker-compose.staging.yml` existente o crear `docker-compose.staging.override.yml`:
   ```yaml
   services:
     ai-worker:
       volumes: ["./backend:/app/backend:ro"]
     demo-worker:
       volumes: ["./backend:/app/backend:ro"]
     master-worker:
       volumes: ["./backend:/app/backend:ro"]
   ```
   NO tocar `docker-compose.yml` genérico si también lo usa prod.

5. **Deploy staging:**
   ```bash
   ssh flexpqr-staging << 'EOF'
   set -euo pipefail
   cd ~/PQRS_V2 && git fetch origin && git checkout develop && git pull origin develop
   ./scripts/migrate.sh --env=staging --dry-run
   ./scripts/migrate.sh --env=staging
   docker compose -f docker-compose.yml -f docker-compose.staging.override.yml \
     up -d --no-deps ai-worker demo-worker master-worker
   docker compose restart backend
   sleep 20 && docker compose ps
   EOF
   ```

6. **Healthcheck:** `docker compose ps` sin caídos; `curl http://15.229.114.148:8001/health`; logs `--since 2m` de los 3 workers + backend; verificar `aequitas_migrations` tiene 18-21.

7. **Smoke funcional:** `pytest backend/tests/integration/test_tutela_pipeline_e2e.py --env=staging -v`.

8. **CloudWatch dashboard `FlexPQR-Monitor`** + nuevas métricas: `TutelasExtractionFailed` (count `_extraction_failed:true`), `TutelasRequireManualReview` (count `_requiere_revision_humana:true`), `TutelasVinculadas` (24h), `MigrationsApplied` (gauge).

9. **Rollback plan documentado** (no ejecutado) en `Brain/sprints/SPRINT_TUTELAS_S123_ROLLBACK.md`: rollback código (`git reset --hard <sha> && docker compose restart`) + migraciones 18-21 en orden inverso.

10. **PROHIBIDO ABSOLUTO:** no SSH a 18.228.54.9; no `git push` a main/staging remotos; no tocar DNS/WAF/secretos prod. Si Nico pide prod: *"Sprint termina en staging. Deploy prod requiere conversación separada."*

11. **Monitoreo 24h post-deploy** con Brain timestamp. CloudWatch alertas: `TutelasExtractionFailed >5/h`, worker restart `>2/6h`, latencia p95 backend `>2s`.

12. **Commits:**
    - `chore(infra): bind mounts workers staging (DT-15 resuelta)`
    - `chore(infra): deploy sprint tutelas staging`
    - `chore(monitoring): metricas CloudWatch tutelas`
    - `docs(brain): registro deploy staging + plan rollback`

13. **PROGRESS.md:** Agente 6 ✅. Sprint ✅.

14. **Gate de salida:** staging todos Up; bind mounts funcionan (editar .py refleja sin rebuild); smoke E2E verde; CloudWatch sin alarmas 15min; rollback doc; **PRODUCCIÓN INTACTA**.

15. **Checkpoint final Sesión 3:** reporte completo a Nico.

---

## 🚦 ORQUESTACIÓN Y GATES

```
Gate 0 (ya completado en diagnóstico) ✅
          ↓
Gate 0.5: Sub-A diagnóstico D3 + Sub-B migrations/ + migrate.sh + bootstrap
          ↓
🔵 Agente 1 — DB (migraciones 18-21)
          ↓ 🛑 CHECKPOINT SESIÓN 1 — Nico valida
🟢 Agente 2 — Backend
          ↓
🟡 Agente 3 — AI/Worker
          ↓ 🛑 CHECKPOINT SESIÓN 2 — Nico valida
🟠 Agente 4 — QA
          ↓
🟣 Agente 5 — Docs
          ↓
🔴 Agente 6 — Infra (deploy staging)
          ↓ 🛑 CHECKPOINT FINAL — Nico valida
         🎯 Reporte final
```

**Si cualquier gate falla**: siguientes NO ejecutan. Reporte: qué agente, qué comando falló, estado actual, plan remediación.

---

## 📊 REPORTE FINAL ESPERADO

```markdown
# ✅ SPRINT TUTELAS S1+S2+S3 COMPLETADO EN STAGING

## Resumen ejecutivo
- Fecha: YYYY-MM-DD HH:MM
- Duración total: X horas (3 sesiones)
- Branch: develop (HEAD: <sha>)
- Deploy staging: ✅ 15.229.114.148
- Deploy prod: ❌ BLOQUEADO (aprobación Nico)

## Gate 0.5 — Diagnóstico D3
- Escenario resuelto: <A|B|C>
- Acción tomada: <bootstrap 14 | ejecutar 14 + bootstrap | STOP>

## Métricas
- Migraciones: 4 nuevas (18, 19, 20, 21) + hidratación histórica
- Archivos nuevos: N
- Modificados: N
- Tests nuevos: N
- Cobertura global: XX% (baseline YY%)
- Cobertura módulos nuevos: XX%

## Verificación staging
- ✅ Oficio de prueba procesado E2E
- ✅ Metadata extraída: <sample>
- ✅ SLA: <horas> hábiles
- ✅ Semáforo: <color>
- ✅ Vinculación: <match | sin match>
- ✅ Bind mounts workers: cambio .py refleja sin rebuild

## Deudas resueltas
- DT-15: bind mounts workers staging ✅
- DT-17: CHECK constraint extendido ✅
- (Escenario A) D1 sectorial: reconciliada con realidad staging ✅

## Deudas deferidas
- DT-13: aequitas_backend/ vs backend/ reorg
- DT-14: workers zombies worker_outlook*
- DT-16: SLA dual SP + master_worker_outlook
- DT-18: fixtures reales pendientes (plantilla Paola en Brain)
- [Nuevas]: UI polimórfica, firma digital, tracking post-informe, UI capabilities

## Brain actualizado
- Brain/sprints/SPRINT_TUTELAS_S123.md
- Brain/sprints/SPRINT_TUTELAS_S123_PROGRESS.md
- Brain/sprints/SPRINT_TUTELAS_S123_ROLLBACK.md
- Brain/runbooks/RUNBOOK_TUTELAS.md
- Brain/runbooks/RUNBOOK_MIGRATE_SH.md
- Brain/DEUDAS_PENDIENTES.md
- Brain/00_maestro/01_ARQUITECTURA_MAESTRA.md
- CHANGELOG.md

## Próxima acción
⏸️ **ESPERANDO APROBACIÓN MANUAL** para deploy producción.
Nico: validá funcional staging. Cuando apruebes, iniciar sprint separado "DEPLOY PROD TUTELAS S123".
```

---

## 🛑 RESTRICCIONES FINALES

- **Idioma:** español código/commits/docs. Logs técnicos inglés OK.
- **Workarounds sin documentar:** prohibido. Parche temporal = tag `DEUDA_TECNICA` Brain.
- **Zero surprises:** algo inesperado → STOP + reporte.
- **Time boxing:** agente >3h sin cerrar → reportar + pedir confirmación.
- **Backup antes destructivo:** `pg_dump` previo a cualquier ALTER con datos.

---

## 📝 NOTA DE VERSIONADO

- v1: prompt maestro inicial (commit `9b9d656`).
- v2: tras diagnóstico de repo (en `archive/SPRINT_TUTELAS_PIPELINE_PROMPT_v2.md`).
- **v3: ACTUAL — final post-diagnóstico real.** Este archivo.

**Este sprint termina en staging. Producción intacta y espera aprobación manual.**
