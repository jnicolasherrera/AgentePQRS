# 🎯 SPRINT TUTELAS PIPELINE — Prompt Maestro para Claude Code

**Proyecto:** FlexPQR / Aequitas  
**Sprint:** Tutelas S1+S2+S3 (Fundación polimórfica + Extractor judicial + Vinculación PQRS↔Tutela)  
**Fecha planificada:** _rellenar al iniciar_  
**Responsable humano:** Nico (Juan Nicolás Herrera)  
**Modo ejecución:** Multi-agente secuencial con gates de validación  
**Deploy prod:** ❌ BLOQUEADO — solo staging. Prod requiere aprobación manual posterior.

---

## 📜 CONTEXTO PARA CLAUDE CODE (lee esto primero)

Actuá como mi **Ingeniero de Staff con 15+ años** trabajando sobre el sistema FlexPQR en producción. Vas a orquestar 6 agentes especializados que ejecutan de forma **secuencial y condicionada** — ningún agente arranca si el anterior no cerró con ✅ verificado.

### Principios inmutables (NO se negocian)

1. **Diagnóstico antes de modificar.** Antes de cualquier `UPDATE`, `ALTER`, `git push` o `docker restart`, primero se hace `SELECT`, `\d`, `git status`, `git diff`, `docker ps`. Documentar el estado actual en el log del sprint ANTES de tocar nada.
2. **Commits atómicos y auditables.** Cada commit = un ladrillo lógico con mensaje descriptivo en formato `tipo(scope): descripción`. Ejemplos válidos: `feat(db): agregar metadata_especifica JSONB a pqrs_casos`, `feat(sla): soportar plazo en horas para tutelas`. No se aceptan commits tipo "fix" o "updates".
3. **Staging primero, producción jamás sin aprobación.** Todo deploy va a `15.229.114.148` (staging). Producción (`18.228.54.9`) queda bloqueada. Si un agente intenta tocar prod, ABORTA y me notifica.
4. **Guardrail docker-compose prod.** Nunca copiar `docker-compose.yml` local a prod sin diff previo — prod tiene bindings `127.0.0.1` de la auditoría de seguridad de Dante que el local no tiene. Aplica también para staging si tiene diffs propios.
5. **Rol queries:** cualquier filtro sobre operadores debe usar `AND u.rol IN ('analista', 'abogado')` — ARC tiene rol legacy `abogado`.
6. **Brain al final de cada agente.** Cada agente deja una nota en `Brain/sprints/SPRINT_TUTELAS_S123.md` con: qué hizo, qué encontró, decisiones tomadas, tickets abiertos.
7. **Infra Agent ejecuta último.** Orden fijo: DB → Backend → AI/Worker → Tests → Docs → Infra/Deploy.
8. **Lenguaje de trabajo:** Español en código/comentarios/mensajes de commit. Docstrings en español. Nombres de variables en español cuando el dominio es legal/negocio, inglés cuando es técnico genérico.

### Reglas de seguridad operacional

- Si encontrás credenciales hardcoded, STOP y reportá. No las usés ni las commitees.
- Si una migración SQL fallara a mitad, hacé `ROLLBACK` explícito antes de pasar al siguiente agente.
- Antes de cada agente: `git status` debe estar limpio. Si hay cambios sin commit del agente anterior, STOP y pedí clarificación.
- Workspace: `/mnt/f/proyectos/AgentePQRS` en WSL. Sesión tmux: `tmux new -s flexpqr_tutelas`.
- Branch de trabajo: `develop`. Push a remoto solo al cerrar cada agente con éxito.

---

## 🗂️ OBJETIVOS DEL SPRINT (Sprint 1 + 2 + 3 integrados)

### S1 — Fundación polimórfica
- Extender `pqrs_casos` con `metadata_especifica JSONB` + columnas específicas de tutela.
- Crear tabla `user_capabilities` para permisos granulares (ej: `CAN_SIGN_DOCUMENT:TUTELA`).
- Extender `sla_engine` con `sumar_horas_habiles` y branch TUTELA con plazo variable.
- Extender `scoring_engine` con config `SEMAFORO_CONFIG` por tipo_caso (naranja y negro para tutelas).

### S2 — Extractor judicial con Claude
- Función `enrich_tutela(event, clasificacion) → metadata_dict` que usa Claude Sonnet con tool-use para extracción estructurada.
- Schema JSON estricto con todos los campos de tutela (expediente, despacho, plazo, medidas provisionales, accionante hash, hechos, pretensiones, derechos).
- Flag `_requiere_revision_humana` si confianza en plazo < 0.85.
- Integración al worker existente vía dispatcher `enrich_by_tipo`.

### S3 — Vinculación PQRS↔Tutela
- Función `vincular_con_pqrs_previo(caso, metadata)` que busca hash del accionante en `pqrs_casos` del mismo tenant, ventana 30 días.
- Si match, escribe `pqrs_origen_id` y `vinculacion_motivo` en `metadata_especifica`.
- Requiere que PQRS existentes tengan `documento_peticionante_hash` (si no existe hoy, agregarlo como parte del sprint).
- Nueva vista materializada `tutelas_view` para queries de reportes.

### Entregables funcionales al final del sprint
- ✅ ARC (staging) procesando tutelas con extracción estructurada automática.
- ✅ Semáforo extendido (verde/amarillo/naranja/rojo/negro) visible en API (frontend queda para otro sprint).
- ✅ Vinculación automática cuando llega tutela de un peticionante que ya tuvo PQRS.
- ✅ Cobertura de tests ≥ 80% en módulos nuevos.
- ✅ Brain actualizado con 1 archivo por sprint.
- ❌ Sin deploy a producción (staging únicamente).

---

## 🤖 DEFINICIÓN DE AGENTES

### 🔵 Agente 1 — DB Agent
**Rol:** Arquitecto de base de datos. PostgreSQL 15 + RLS expert.  
**Responsabilidades exclusivas:** migraciones SQL, RLS policies, índices, triggers de auditoría, vistas materializadas.  
**Prohibido:** tocar código Python, tocar frontend, tocar infra.

**Tareas:**

1. **Diagnóstico obligatorio previo:**
   ```bash
   ssh flexpqr-staging "docker exec pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 -c '\d pqrs_casos'"
   ssh flexpqr-staging "docker exec pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 -c \"SELECT tablename, policyname FROM pg_policies ORDER BY tablename;\""
   ssh flexpqr-staging "docker exec pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 -c 'SELECT COUNT(*) FROM pqrs_casos WHERE tipo_caso = '\''TUTELA'\'';'"
   ```
   Documentar en Brain: columnas existentes, policies existentes, volumen actual de tutelas, si existe el campo `documento_peticionante_hash` o hay que agregarlo.

2. **Crear migración `15_tutelas_pipeline_foundation.sql`:**
   - `ALTER TABLE pqrs_casos ADD COLUMN metadata_especifica JSONB DEFAULT '{}'::jsonb`.
   - Columnas específicas tutela: `tutela_informe_rendido_at TIMESTAMPTZ`, `tutela_fallo_sentido VARCHAR(20)`, `tutela_riesgo_desacato VARCHAR(10) DEFAULT 'BAJO'`.
   - Si no existe `documento_peticionante_hash VARCHAR(64)` en `pqrs_casos` → agregarlo (necesario para vinculación S3).
   - Índice GIN: `CREATE INDEX idx_casos_metadata_gin ON pqrs_casos USING GIN (metadata_especifica)`.
   - Índice parcial: `CREATE INDEX idx_casos_tutela_vencimiento ON pqrs_casos ((metadata_especifica->>'plazo_informe_horas')::int) WHERE tipo_caso = 'TUTELA'`.
   - Índice para vinculación: `CREATE INDEX idx_casos_doc_hash ON pqrs_casos (cliente_id, documento_peticionante_hash) WHERE documento_peticionante_hash IS NOT NULL`.

3. **Crear migración `16_user_capabilities.sql`:**
   - Tabla `user_capabilities` con RLS policy idéntica al patrón de `pqrs_casos`.
   - Capabilities iniciales: `CAN_SIGN_DOCUMENT`, `CAN_APPROVE_RESPONSE`, `CAN_REASSIGN`, `CAN_VIEW_SENSITIVE_DATA`, `CAN_EXTRACT_TUTELA_MANUAL`.
   - `UNIQUE (usuario_id, capability, tipo_caso_scope)` — permitir scope NULL y scope específico.
   - Grant default: para ARC, dar `CAN_SIGN_DOCUMENT:TUTELA` a usuarios con rol `abogado` (compatibilidad).

4. **Crear migración `17_tutelas_view.sql`:**
   - Vista materializada `tutelas_view` con campos extraídos del JSONB para queries eficientes (expediente, despacho, plazo_horas, informe_rendido_at, fallo_sentido).
   - Índice único sobre `(cliente_id, id)`.
   - Comentario SQL indicando que debe refrescarse con `REFRESH MATERIALIZED VIEW CONCURRENTLY tutelas_view`.
   - ⚠️ **IMPORTANTE:** RLS no aplica a materialized views. Dejar advertencia explícita en Brain y crear política alternativa vía función `SECURITY DEFINER` si aplica.

5. **Extender `scripts/migrate.sh`** solo si es necesario para que lea los nuevos archivos en orden.

6. **Ejecutar en staging:**
   ```bash
   bash scripts/migrate.sh --env=staging
   ```
   Verificar idempotencia ejecutando dos veces.

7. **Validación post-ejecución:**
   - `\d pqrs_casos` muestra las nuevas columnas.
   - `SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'pqrs_casos' AND column_name IN ('metadata_especifica', 'tutela_informe_rendido_at', 'tutela_fallo_sentido', 'tutela_riesgo_desacato', 'documento_peticionante_hash')` → debe devolver 5.
   - `SELECT * FROM pg_policies WHERE tablename = 'user_capabilities'` → debe existir al menos una policy.
   - Verificar que casos existentes de ARC siguen visibles con `SET LOCAL app.current_tenant_id = 'effca814-b0b5-4329-96be-186c0333ad4b';` + SELECT.

8. **Commits:**
   - `feat(db): agregar metadata_especifica JSONB y columnas tutela a pqrs_casos`
   - `feat(db): crear tabla user_capabilities con RLS`
   - `feat(db): crear vista materializada tutelas_view`
   - `docs(brain): documentar fundacion DB sprint tutelas`

9. **Gate de salida:** ✅ todas las validaciones pasan, commits limpios en `develop`, Brain actualizado con diagnóstico inicial y resultado. Si algo falla → ROLLBACK y STOP.

---

### 🟢 Agente 2 — Backend Agent
**Rol:** Ingeniero backend senior. Python 3.11 + FastAPI + asyncpg.  
**Responsabilidades exclusivas:** `sla_engine.py`, `scoring_engine.py`, nuevas capabilities en el módulo de auth.  
**Prohibido:** tocar worker IA (eso es Agente 3), tocar DB directa (solo a través de engines existentes), tocar infra.

**Tareas:**

1. **Diagnóstico obligatorio previo:**
   ```bash
   cd /mnt/f/proyectos/AgentePQRS
   git status
   grep -rn "def calcular_vencimiento" aequitas_backend/
   grep -rn "def calcular_semaforo\|SEMAFORO" aequitas_backend/
   cat aequitas_backend/app/services/sla_engine.py
   cat aequitas_backend/app/services/scoring_engine.py
   ```
   Documentar firmas actuales de funciones en Brain ANTES de modificar.

2. **Extender `sla_engine.py`:**
   - Agregar parámetro opcional `metadata_especifica: dict | None = None` a `calcular_vencimiento`.
   - Branch: `if tipo_caso == "TUTELA" and metadata_especifica`:
     - Leer `plazo_informe_horas` (default 48).
     - Leer `plazo_tipo` (`HABILES` | `CALENDARIO`, default `HABILES`).
     - Si `CALENDARIO` → sumar timedelta directo.
     - Si `HABILES` → llamar a `sumar_horas_habiles`.
   - **Nueva función** `sumar_horas_habiles(inicio, horas, cliente_id) -> datetime`:
     - Jornada default: 8 horas hábiles por día (configurable por tenant vía `config_tenant.jornada_laboral` si existe, si no hardcoded 8-12 / 13-17).
     - Saltar sábados, domingos, festivos de `festivos_colombia`.
     - Retornar datetime en UTC.
   - **Nueva función** `calcular_vencimiento_medida_provisional(metadata: dict) -> datetime | None`:
     - Retorna None si no hay `medidas_provisionales` en metadata.
     - Plazo siempre CALENDARIO para medidas provisionales.
   - Mantener 100% compatibilidad backward: llamadas existentes sin `metadata_especifica` deben seguir funcionando idénticamente.

3. **Extender `scoring_engine.py`:**
   - Agregar constante:
     ```python
     SEMAFORO_CONFIG = {
         "PQRS_DEFAULT": {
             "verde_hasta_pct": 50, "amarillo_hasta_pct": 25,
             "rojo_hasta_pct": 0, "negro_si_vencido": False
         },
         "TUTELA": {
             "verde_hasta_pct": 50, "amarillo_hasta_pct": 25,
             "naranja_hasta_pct": 10, "rojo_hasta_pct": 0,
             "negro_si_vencido": True,
             "escalar_representante_legal_en_rojo": True
         }
     }
     ```
   - Modificar `calcular_semaforo(caso)` para leer config según `tipo_caso`.
   - Valores de retorno válidos: `VERDE`, `AMARILLO`, `NARANJA`, `ROJO`, `NEGRO`.
   - ⚠️ Revisar que no rompa el CHECK constraint existente en `pqrs_casos.semaforo_sla` — si el CHECK solo acepta VERDE/AMARILLO/ROJO hay que agregarlo como subtarea en DB Agent (o flaggear deuda si quedó fuera).

4. **Nuevo módulo `app/services/capabilities.py`:**
   - `async def user_has_capability(user_id, capability, tipo_caso=None) -> bool`.
   - `async def grant_capability(user_id, capability, tipo_caso_scope, granted_by) -> None`.
   - `async def list_user_capabilities(user_id) -> list[dict]`.
   - Usar `aequitas_worker` rol o `pqrs_admin` con RLS set.

5. **Tests unitarios obligatorios en `tests/services/`:**
   - `test_sla_engine_tutela.py`: al menos 8 casos — plazo 48h hábiles normal, 24h calendario, con festivo en medio, medida provisional, compatibilidad PQRS.
   - `test_scoring_engine_semaforo.py`: al menos 6 casos — tutela en verde, amarillo, naranja, rojo, negro; PQRS normal sin naranja.
   - `test_capabilities.py`: grant, revoke, scope NULL vs específico, RLS isolation entre tenants.
   - Cobertura mínima del módulo nuevo: 80%. Ejecutar `pytest --cov=app.services.sla_engine --cov=app.services.scoring_engine --cov=app.services.capabilities`.

6. **Commits:**
   - `feat(sla): soportar plazo en horas habiles para tutelas`
   - `feat(sla): medidas provisionales con plazo independiente`
   - `feat(scoring): semaforo polimorfico por tipo_caso con naranja y negro`
   - `feat(auth): modulo de capabilities granulares`
   - `test(services): cobertura 80% modulos tutela fundacion`
   - `docs(brain): documentar extensiones backend sprint tutelas`

7. **Gate de salida:** tests pasan al 100%, cobertura ≥ 80%, no hay warnings de mypy en los archivos modificados. Si rompe tests existentes, STOP.

---

### 🟡 Agente 3 — AI/Worker Agent
**Rol:** Ingeniero de IA y data pipelines. Anthropic Claude + Kafka + asyncpg.  
**Responsabilidades exclusivas:** worker consumer, módulos `enrich_*`, prompts de Claude, función de vinculación.  
**Prohibido:** tocar DB directa sin engines, tocar API routes, tocar frontend.

**Tareas:**

1. **Diagnóstico obligatorio previo:**
   ```bash
   grep -rn "async def process_event\|async def process_message" worker_*/
   grep -rn "classify_with_claude\|clasificar_pqrs" .
   cat worker_v2/kafka_consumer.py 2>/dev/null || cat aequitas_worker/consumer.py
   ssh flexpqr-staging "docker logs demo_worker_v2 --tail 100"
   ```
   Documentar flujo actual del worker: qué topic lee, qué clasifica, cómo persiste.

2. **Nuevo módulo `app/services/enrichers/__init__.py`:**
   - Dispatcher `async def enrich_by_tipo(tipo_caso: str, event: dict, clasificacion) -> dict`.
   - Registro de enrichers: `{"TUTELA": enrich_tutela}`. Diseñado para agregar más en el futuro (REQUERIMIENTO_SFC, etc.).
   - Fallback: si no hay enricher para ese tipo, retorna `{}`.

3. **Nuevo módulo `app/services/enrichers/tutela_extractor.py`:**
   - Función `async def enrich_tutela(event: dict, clasificacion) -> dict`.
   - Prompt builder: contexto legal colombiano, instrucciones explícitas sobre plazo en horas, accionante como hash (NO extraer nombre en claro — hash SHA-256 con salt del tenant), derechos invocados, medidas provisionales.
   - Schema JSON con tool-use de Claude Sonnet (model `claude-sonnet-4-20250514` o más reciente — leer `ANTHROPIC_MODEL_SONNET` de env).
   - Schema obligatorio:
     ```python
     TUTELA_SCHEMA = {
         "type": "object",
         "required": ["numero_expediente", "despacho", "fecha_auto", 
                      "plazo_informe_horas", "plazo_tipo", "tipo_actuacion"],
         "properties": {
             "numero_expediente": {"type": "string"},
             "despacho": {
                 "type": "object",
                 "properties": {
                     "nombre": {"type": "string"},
                     "email": {"type": "string"},
                     "juez": {"type": ["string", "null"]},
                     "ciudad": {"type": ["string", "null"]}
                 }
             },
             "tipo_actuacion": {
                 "type": "string",
                 "enum": ["AUTO_ADMISORIO", "MEDIDA_PROVISIONAL", "TRASLADO_PRUEBAS",
                          "FALLO_PRIMERA", "IMPUGNACION", "FALLO_SEGUNDA", 
                          "DESACATO", "REQUERIMIENTO_CUMPLIMIENTO"]
             },
             "fecha_auto": {"type": "string", "format": "date"},
             "plazo_informe_horas": {"type": "integer", "minimum": 1, "maximum": 720},
             "plazo_tipo": {"type": "string", "enum": ["HABILES", "CALENDARIO"]},
             "medidas_provisionales": {
                 "type": ["object", "null"],
                 "properties": {
                     "descripcion": {"type": "string"},
                     "plazo_horas": {"type": "integer"}
                 }
             },
             "accionante": {
                 "type": "object",
                 "properties": {
                     "tipo_documento": {"type": "string"},
                     "documento_hash": {"type": "string"},
                     "derechos_invocados": {"type": "array", "items": {"type": "string"}}
                 }
             },
             "hechos": {"type": "array", "items": {"type": "string"}},
             "pretensiones": {"type": "array", "items": {"type": "string"}},
             "_confidence": {
                 "type": "object",
                 "properties": {
                     "plazo_informe_horas": {"type": "number", "minimum": 0, "maximum": 1},
                     "numero_expediente": {"type": "number", "minimum": 0, "maximum": 1},
                     "tipo_actuacion": {"type": "number", "minimum": 0, "maximum": 1}
                 }
             }
         }
     }
     ```
   - Post-processing obligatorio:
     - Si `_confidence.plazo_informe_horas < 0.85` → agregar flag `_requiere_revision_humana = True`.
     - Hash del documento del accionante con `hashlib.sha256((doc + tenant_salt).encode()).hexdigest()` — leer `tenant_salt` de `clientes_tenant.config_hash_salt` (agregar columna si no existe como mini-migración extra).
     - Nunca persistir el número de documento en claro, solo el hash.
   - Manejo de errores:
     - Si Claude falla → log + retorna `{"_extraction_failed": True}` + mantiene el caso como tutela con plazo default 48h hábiles.
     - Exponential backoff reutilizando patrón de `zoho_engine` (2s/4s/8s).

4. **Nuevo módulo `app/services/vinculacion.py` (S3):**
   - Función `async def vincular_con_pqrs_previo(caso_id: UUID, cliente_id: UUID, doc_hash: str) -> dict | None`.
   - Query:
     ```sql
     SELECT id, numero_radicado, tipo_caso, estado, fecha_creacion, fecha_respuesta
     FROM pqrs_casos
     WHERE cliente_id = :cliente_id
       AND documento_peticionante_hash = :doc_hash
       AND tipo_caso != 'TUTELA'
       AND fecha_creacion >= now() - INTERVAL '30 days'
     ORDER BY fecha_creacion DESC
     LIMIT 5;
     ```
   - Si encuentra match(es), determinar `vinculacion_motivo`:
     - `PQRS_NO_CONTESTADO` si el PQRS previo no tiene `fecha_respuesta`.
     - `RESPUESTA_INSATISFACTORIA` si hay respuesta.
     - `MULTIPLE_MATCHES` si hay más de 1, guardar lista.
   - UPDATE del caso con `metadata_especifica` merged:
     ```sql
     UPDATE pqrs_casos 
     SET metadata_especifica = metadata_especifica || 
         jsonb_build_object('vinculacion', :vinculacion_data)
     WHERE id = :caso_id;
     ```
   - Retorna dict con los casos vinculados para log.

5. **Integración al worker existente:**
   - Localizar la función principal del worker (típicamente `process_event` o similar).
   - Insertar entre la clasificación y la persistencia:
     ```python
     metadata_especifica = await enrich_by_tipo(
         tipo_caso=clasificacion.tipo_caso,
         event=event,
         clasificacion=clasificacion
     )
     # ... persistir caso incluyendo metadata_especifica ...
     if clasificacion.tipo_caso == "TUTELA" and metadata_especifica.get("accionante", {}).get("documento_hash"):
         vinculacion = await vincular_con_pqrs_previo(
             caso_id=caso.id,
             cliente_id=caso.cliente_id,
             doc_hash=metadata_especifica["accionante"]["documento_hash"]
         )
         if vinculacion:
             logger.info(f"Tutela {caso.numero_radicado} vinculada con {len(vinculacion['matches'])} PQRS previos")
     ```
   - Si el worker está duplicado entre `demo_worker_v2` y `ai-worker`, actualizar ambos pero documentar esta deuda en Brain.

6. **Tests obligatorios:**
   - `tests/services/enrichers/test_tutela_extractor.py`:
     - Mock de Claude API con 3 oficios reales anonimizados (pediles a ARC, o usá fixtures sintéticos que simulen autos reales).
     - Caso con plazo ambiguo → debe flaggear `_requiere_revision_humana`.
     - Caso con fallo de Claude → debe retornar fallback sin crashear.
     - Caso con medida provisional → campo poblado correctamente.
   - `tests/services/test_vinculacion.py`:
     - Match con PQRS no contestado → `vinculacion_motivo = PQRS_NO_CONTESTADO`.
     - Match con PQRS contestado → `RESPUESTA_INSATISFACTORIA`.
     - Sin match → None retornado.
     - Multiple matches → lista completa.
     - Aislamiento entre tenants (no matchear PQRS de otro tenant).

7. **Validación end-to-end en staging:**
   - Enviar un oficio de tutela de prueba al buzón de staging.
   - Verificar en DB: `SELECT tipo_caso, metadata_especifica, semaforo_sla FROM pqrs_casos WHERE id = '<caso_nuevo>';`.
   - Confirmar que: extracción pobló metadata, SLA calculó vencimiento en horas correctamente, semáforo usa TUTELA config.

8. **Commits:**
   - `feat(worker): dispatcher enrich_by_tipo para enriquecimiento polimorfico`
   - `feat(ai): extractor judicial de tutelas con Claude Sonnet y schema estricto`
   - `feat(worker): vinculacion automatica tutela con PQRS previos`
   - `test(ai): cobertura extractor tutelas con fixtures reales`
   - `test(services): cobertura vinculacion pqrs-tutela`
   - `docs(brain): documentar pipeline extractor + vinculacion`

9. **Gate de salida:** test E2E pasa en staging, extracción funciona en al menos 1 oficio real anonimizado, vinculación detecta match correctamente en caso simulado.

---

### 🟠 Agente 4 — QA Agent
**Rol:** Test engineer senior. pytest, integration tests, chaos engineering liviano.  
**Responsabilidades exclusivas:** suite de regresión completa, tests de integración, verificación de no-regresión de PQRS normales.  
**Prohibido:** modificar código de producción, modificar tests escritos por otros agentes (solo agregar).

**Tareas:**

1. **Diagnóstico obligatorio:**
   - Ejecutar suite existente: `pytest -v --tb=short > /tmp/baseline.txt`. Documentar fallas preexistentes (si las hay) en Brain como contexto.
   - Confirmar que los tests escritos por Agentes 2 y 3 pasan individualmente.

2. **Tests de integración end-to-end (nuevos):**
   - `tests/integration/test_tutela_pipeline_e2e.py`:
     - Simular un evento Kafka completo de tutela (sin subir a Kafka real, inyectar directo al consumer).
     - Verificar: caso creado, `metadata_especifica` poblado, SLA calculado en horas, semáforo en color esperado, vinculación ejecutada si aplica.
     - Caso sin match de PQRS previo.
     - Caso con 1 match.
     - Caso con múltiples matches.
     - Caso con extracción fallida (Claude mock que tira excepción) → fallback correcto.
   - `tests/integration/test_no_regresion_pqrs.py`:
     - Enviar 10 PQRS de tipos variados (PETICION, QUEJA, RECLAMO, SUGERENCIA) por el worker.
     - Confirmar que el flujo antiguo no rompió: `metadata_especifica` queda `{}`, SLA calcula en días como antes, semáforo no devuelve NARANJA ni NEGRO.

3. **Tests de aislamiento multi-tenant:**
   - `tests/integration/test_tenant_isolation_tutelas.py`:
     - Crear tutela en tenant A, PQRS previo en tenant B con mismo doc_hash → NO debe vincular.
     - Crear tutela en tenant A con PQRS previo en tenant A mismo doc_hash → SÍ vincula.
     - User de tenant A no ve `user_capabilities` de tenant B.

4. **Tests de carga liviana:**
   - Script `tests/load/test_tutelas_burst.py` (pytest-benchmark o similar):
     - 50 oficios simulados en 30 segundos.
     - Verificar no-crash, tiempo promedio de extracción < 8s, no hay dead-letter queue crecimiento anómalo.

5. **Ejecución de suite completa:**
   ```bash
   pytest --cov --cov-report=term-missing --cov-report=html tests/
   ```
   - Cobertura global del proyecto no debe bajar respecto al baseline.
   - Cobertura módulos nuevos ≥ 80%.

6. **Regression check explícito contra ARC staging:**
   - Consultar 10 casos PQRS reales recientes de ARC en staging.
   - Confirmar que sus campos no cambiaron: mismo semáforo, misma fecha_vencimiento, mismo estado.
   - Script: `scripts/verify_arc_regression.py` que hace diff antes/después.

7. **Commits:**
   - `test(integration): pipeline tutela end-to-end con 5 escenarios`
   - `test(integration): no regresion flujo PQRS actual`
   - `test(integration): aislamiento multi-tenant tutelas y capabilities`
   - `test(load): burst de 50 tutelas sin degradacion`
   - `docs(brain): reporte QA y coverage sprint tutelas`

8. **Gate de salida:**
   - Suite completa pasa al 100%.
   - Cobertura módulos nuevos ≥ 80%.
   - Cero regresiones en PQRS existentes de ARC.
   - Si algo falla → STOP y reporta detallado. No aprobar deploy a staging con tests rotos.

---

### 🟣 Agente 5 — Docs Agent
**Rol:** Technical writer + arquitecto documentación. Brain system + runbooks operacionales.  
**Responsabilidades exclusivas:** actualización del Brain, runbook de operaciones, README técnico.  
**Prohibido:** tocar código.

**Tareas:**

1. **Crear `Brain/sprints/SPRINT_TUTELAS_S123.md`:**
   - Objetivo del sprint y alcance.
   - Diagrama mermaid del flujo polimórfico (el mismo que vimos en la conversación).
   - Decisiones arquitectónicas tomadas: por qué JSONB vs tabla satélite, por qué capabilities vs nuevo rol, por qué extractor con Claude tool-use.
   - Schema completo de `metadata_especifica` para tutelas.
   - Ejemplos reales (anonimizados) de metadata extraída.
   - Cómo interpretar el flag `_requiere_revision_humana`.
   - Lista de deudas técnicas identificadas y deferidas (con IDs DT-9, DT-10, etc).

2. **Crear `Brain/runbooks/RUNBOOK_TUTELAS.md`:**
   - Cómo consultar el estado de una tutela específica.
   - Cómo forzar re-extracción si Claude falló.
   - Cómo marcar manualmente una vinculación.
   - Cómo refrescar `tutelas_view` materializada.
   - Cómo debuggear un caso flaggeado como `_requiere_revision_humana`.
   - Alertas esperables y qué significan.

3. **Actualizar `Brain/DEUDAS_PENDIENTES.md`:**
   - Agregar: firma digital (S6 futuro), tracking post-informe (S5 futuro), UI polimórfica frontend (S4 futuro).
   - Marcar como resueltas las deudas que aplicaban (si había algo sobre tutelas mal clasificadas).

4. **Actualizar `Brain/01_ARQUITECTURA_MAESTRA.md`:**
   - Agregar sección "Polimorfismo por tipo_caso" explicando el patrón.
   - Actualizar el diagrama de secuencia con el paso de enriquecimiento.

5. **Actualizar `README.md` de los módulos modificados:**
   - `aequitas_backend/app/services/README.md` si existe, o crearlo.
   - Listar: `sla_engine`, `scoring_engine`, `capabilities`, `enrichers/`, `vinculacion`.

6. **Changelog:**
   - Crear/actualizar `CHANGELOG.md` en raíz con entrada del sprint bajo `[Unreleased]`.

7. **Commits:**
   - `docs(brain): sprint tutelas S123 completo`
   - `docs(runbook): operaciones tutelas en produccion`
   - `docs(arquitectura): patron polimorfico por tipo_caso`
   - `docs: changelog sprint tutelas`

8. **Gate de salida:** archivos presentes, bien formateados, links internos (wikilinks `[[archivo]]`) funcionan, mermaid renderiza.

---

### 🔴 Agente 6 — Infra Agent
**Rol:** DevOps senior. Docker Compose, CloudWatch, AWS, SSH. **EJECUTA ÚLTIMO**.  
**Responsabilidades exclusivas:** deploy a staging, verificación de salud, monitoreo post-deploy, rollback si aplica.  
**Prohibido absoluto:** tocar producción. Si tu instrucción menciona `18.228.54.9` o `flexpqr-prod`, ABORTÁ y pedí clarificación.

**Tareas:**

1. **Diagnóstico pre-deploy obligatorio:**
   ```bash
   # Confirmar que estás en develop y pushed
   cd /mnt/f/proyectos/AgentePQRS
   git status
   git log origin/develop..develop  # debe ser vacío después de push
   
   # Confirmar branch correcto en staging
   ssh flexpqr-staging "cd ~/PQRS_V2 && git branch --show-current"
   
   # Confirmar que NO estás apuntando a prod
   ssh flexpqr-staging "hostname -I"  # debe ser 15.229.114.148, no 18.228.54.9
   
   # Snapshot estado staging antes del deploy
   ssh flexpqr-staging "docker compose ps > /tmp/pre_deploy_$(date +%s).txt && cat /tmp/pre_deploy_*.txt"
   ```

2. **Guardrail docker-compose:**
   ```bash
   # Diff contra staging — si hay bindings diferentes, STOP
   ssh flexpqr-staging "cat ~/PQRS_V2/docker-compose.yml" > /tmp/staging_compose.yml
   diff docker-compose.yml /tmp/staging_compose.yml
   # Si hay diffs, documentar en Brain y pedir aprobación antes de seguir
   ```

3. **Deploy a staging:**
   ```bash
   ssh flexpqr-staging << 'EOF'
     cd ~/PQRS_V2
     git fetch origin
     git checkout develop
     git pull origin develop
     
     # Aplicar migraciones SQL primero
     bash scripts/migrate.sh
     
     # Build + restart solo los servicios afectados
     docker exec pqrs_v2_frontend npm run build || true  # si tocó frontend, si no skip
     docker compose restart backend demo_worker_v2 ai-worker
     
     # Wait for health
     sleep 15
     docker compose ps
   EOF
   ```

4. **Healthcheck post-deploy:**
   ```bash
   # Verificar que servicios levantaron
   ssh flexpqr-staging "docker compose ps | grep -v Up" && echo "⚠️ Servicios caídos detectados" || echo "✅ Todo Up"
   
   # Endpoints de salud
   curl -sS http://15.229.114.148:8001/health
   curl -sS http://15.229.114.148:8001/api/health/detailed
   
   # Logs últimos 2 minutos del worker
   ssh flexpqr-staging "docker logs demo_worker_v2 --since 2m | tail -50"
   ssh flexpqr-staging "docker logs ai-worker --since 2m | tail -50"
   
   # Verificar que las migraciones se aplicaron
   ssh flexpqr-staging "docker exec pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 -c 'SELECT version FROM aequitas_migrations ORDER BY applied_at DESC LIMIT 5;'"
   ```

5. **Smoke test funcional:**
   - Ejecutar el script E2E del Agente 4 directamente contra staging:
     ```bash
     pytest tests/integration/test_tutela_pipeline_e2e.py --env=staging -v
     ```
   - Confirmar que un oficio de prueba real procesa correctamente extremo a extremo.

6. **CloudWatch alerts:**
   - Verificar que no hay spike de errores en el dashboard `FlexPQR-Monitor`.
   - Agregar métricas custom si aplica:
     - `TutelasExtractionFailed` (cuenta de `_extraction_failed: true`).
     - `TutelasRequireManualReview` (cuenta de `_requiere_revision_humana: true`).
     - `TutelasVinculadas` (cuenta de vinculaciones exitosas en últimas 24h).

7. **Rollback plan documentado:**
   ```bash
   # Si algo explota, rollback es:
   ssh flexpqr-staging << 'EOF'
     cd ~/PQRS_V2
     git reset --hard <commit_previo_al_sprint>
     bash scripts/rollback.sh  # revierte las migraciones 15/16/17 en orden inverso
     docker compose restart
   EOF
   ```
   Esto debe estar DOCUMENTADO en Brain antes del deploy, no improvisado después.

8. **NO TOCAR PRODUCCIÓN:**
   - No hacer SSH a `18.228.54.9` por ningún motivo.
   - No ejecutar `git push` a branch `main` o `staging` del remoto.
   - No modificar DNS, WAF, Cloudflare, nada en prod.
   - Si el usuario pide algo que parece ir a prod, responder: *"Este sprint termina en staging. Deploy a prod requiere tu aprobación explícita en conversación separada."*

9. **Monitoreo post-deploy (24h):**
   - Agregar entrada al Brain con: "Staging deploy completado el YYYY-MM-DD HH:MM. Monitoreo activo por 24h."
   - Configurar que CloudWatch alerte si:
     - `TutelasExtractionFailed` > 5 en 1 hora.
     - `demo_worker_v2` restart count > 2 en 6 horas.
     - Latencia p95 del backend > 2s.

10. **Commits:**
    - `chore(infra): deploy sprint tutelas a staging`
    - `chore(monitoring): metricas custom tutelas`
    - `docs(brain): registro de deploy staging sprint tutelas`

11. **Gate de salida:**
    - Staging funcionando con todos los servicios `Up`.
    - Smoke test E2E pasa contra staging real.
    - No hay errores nuevos en CloudWatch en los 15 minutos post-deploy.
    - Brain actualizado con timestamp y estado.
    - ❌ **Producción intacta. Plan de deploy prod documentado pero NO ejecutado.**
    - Reportar al usuario: "Sprint desplegado en staging. Validación manual requerida antes de considerar deploy a prod."

---

## 🚦 ORQUESTACIÓN Y GATES DE VALIDACIÓN

```
┌─────────────────────────────────────────────────────────────┐
│  Gate 0: Diagnóstico inicial del repositorio y staging      │
│  ✓ git status limpio                                        │
│  ✓ staging accesible y con último develop                   │
│  ✓ ARC tenant en regimen GENERAL confirmado                 │
└─────────────────────────────────────────────────────────────┘
          ↓
🔵 Agente 1 — DB Agent
          ↓
┌─────────────────────────────────────────────────────────────┐
│  Gate 1: DB validada                                        │
│  ✓ Migraciones 15/16/17 aplicadas idempotentes              │
│  ✓ RLS policies funcionan con tenant_id de ARC              │
│  ✓ 5 columnas nuevas presentes                              │
│  ✓ Vista materializada creada                               │
│  ✓ Commits limpios en develop, Brain actualizado            │
└─────────────────────────────────────────────────────────────┘
          ↓
🟢 Agente 2 — Backend Agent
          ↓
┌─────────────────────────────────────────────────────────────┐
│  Gate 2: Backend validado                                   │
│  ✓ sla_engine + scoring_engine + capabilities funcionando   │
│  ✓ Tests unitarios ≥ 80% cobertura                          │
│  ✓ Compatibilidad backward: PQRS actuales sin cambios       │
│  ✓ mypy clean en módulos modificados                        │
└─────────────────────────────────────────────────────────────┘
          ↓
🟡 Agente 3 — AI/Worker Agent
          ↓
┌─────────────────────────────────────────────────────────────┐
│  Gate 3: Worker IA validado                                 │
│  ✓ Extractor tutela funcionando con Claude                  │
│  ✓ Vinculación detecta matches correctamente                │
│  ✓ Worker integrado sin romper flujo PQRS existente         │
│  ✓ Tests con fixtures reales pasan                          │
└─────────────────────────────────────────────────────────────┘
          ↓
🟠 Agente 4 — QA Agent
          ↓
┌─────────────────────────────────────────────────────────────┐
│  Gate 4: QA aprobado                                        │
│  ✓ Suite completa 100% verde                                │
│  ✓ Cero regresiones en PQRS reales de ARC                   │
│  ✓ Aislamiento multi-tenant verificado                      │
│  ✓ Load test 50 tutelas sin degradación                     │
└─────────────────────────────────────────────────────────────┘
          ↓
🟣 Agente 5 — Docs Agent
          ↓
┌─────────────────────────────────────────────────────────────┐
│  Gate 5: Docs completos                                     │
│  ✓ Brain/sprints/SPRINT_TUTELAS_S123.md creado              │
│  ✓ Brain/runbooks/RUNBOOK_TUTELAS.md creado                 │
│  ✓ Arquitectura maestra actualizada                         │
│  ✓ Wikilinks funcionando                                    │
└─────────────────────────────────────────────────────────────┘
          ↓
🔴 Agente 6 — Infra Agent (ÚLTIMO)
          ↓
┌─────────────────────────────────────────────────────────────┐
│  Gate 6 FINAL: Staging operativo                            │
│  ✓ Deploy exitoso en 15.229.114.148                         │
│  ✓ Todos los servicios Up                                   │
│  ✓ Smoke test E2E verde                                     │
│  ✓ CloudWatch sin alarmas nuevas                            │
│  ✓ Rollback plan documentado                                │
│  ❌ PRODUCCIÓN NO TOCADA                                    │
└─────────────────────────────────────────────────────────────┘
          ↓
   🎯 Reporte final al humano (Nico)
```

**Regla de orquestación:** si cualquier gate falla, los agentes posteriores NO ejecutan. El orquestador reporta al humano con:
- Qué agente falló.
- Qué test/comando/validación falló específicamente.
- Estado actual del sistema (¿hay commits sin push? ¿migración parcialmente aplicada?).
- Plan de remediación propuesto.

---

## 📊 REPORTE FINAL ESPERADO

Al completar los 6 agentes, el orquestador debe entregar en la consola:

```markdown
# ✅ SPRINT TUTELAS S1+S2+S3 COMPLETADO EN STAGING

## Resumen ejecutivo
- **Fecha:** YYYY-MM-DD HH:MM
- **Duración total:** X horas
- **Branch:** develop (commit HEAD: <sha>)
- **Deploy staging:** ✅ 15.229.114.148
- **Deploy producción:** ❌ BLOQUEADO (requiere aprobación manual de Nico)

## Métricas clave
- Migraciones SQL aplicadas: 3 (15, 16, 17)
- Archivos nuevos creados: N
- Archivos modificados: N
- Líneas agregadas: N
- Tests nuevos: N
- Cobertura global: XX% (antes: YY%)
- Cobertura módulos nuevos: XX%

## Verificación funcional en staging
- ✅ Oficio de prueba procesado extremo a extremo
- ✅ Metadata extraída: <sample>
- ✅ SLA calculado: <valor> horas hábiles
- ✅ Semáforo: <color>
- ✅ Vinculación: <match encontrado | sin match>

## Deudas técnicas abiertas
- DT-9: Frontend polimórfico del detalle tutela (próximo sprint)
- DT-10: Firma digital de memoriales (sprint aparte, requiere certicámara)
- DT-11: Tracking post-informe (estados fallo)
- DT-12: UI para configurar capabilities del Admin Tenant

## Archivos Brain creados/actualizados
- Brain/sprints/SPRINT_TUTELAS_S123.md (nuevo)
- Brain/runbooks/RUNBOOK_TUTELAS.md (nuevo)
- Brain/DEUDAS_PENDIENTES.md (actualizado)
- Brain/01_ARQUITECTURA_MAESTRA.md (actualizado)

## Próxima acción
⏸️ **ESPERANDO APROBACIÓN MANUAL** para deploy a producción.
Nico: ejecutar validación funcional en staging (link: https://staging.flexpqr.co)
Cuando apruebes, iniciar sprint separado "DEPLOY PROD TUTELAS S123".
```

---

## 🛑 RESTRICCIONES FINALES

- **Idioma:** todo el código, commits y documentación en español. Logs técnicos pueden ser en inglés.
- **Sin workarounds sin documentar:** cualquier parche temporal va al Brain con tag `DEUDA_TECNICA`.
- **Zero surprises:** si un agente encuentra algo inesperado (ej: columna ya existe, test roto preexistente, credencial expuesta), STOP y reportar al humano antes de continuar.
- **Time boxing:** si un agente lleva más de 3 horas, reportar progreso y pedir confirmación de continuar.
- **Backup antes de migraciones destructivas:** `pg_dump` del schema previo cualquier ALTER que toque tablas con datos.

---

## 🎬 INSTRUCCIÓN DE ARRANQUE

Cuando estés listo para ejecutar, comenzá con:

> Leé `/mnt/f/proyectos/AgentePQRS/Brain/` completo para contexto. Verificá `git status` y estado de staging con `ssh flexpqr-staging "docker compose ps"`. Luego ejecutá Gate 0 (diagnóstico inicial) y reportame antes de arrancar el Agente 1. No modifiques nada hasta que yo confirme el diagnóstico.

**Este sprint termina en staging. Producción queda intacta y espera aprobación manual de Nico.**
