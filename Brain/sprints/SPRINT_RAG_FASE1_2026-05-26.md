# SPRINT RAG real — Fase 1 (infra) ✅

**Fecha:** 2026-05-26
**Rama:** `feat/rag-fase1-pgvector-2026-05-26` (local, sin push aún)
**Sprint padre:** "RAG real" — 6 fases (0 baseline → 1 infra → 2 embeddings → 3 retrieval → 4 A/B → 5 ingestion automática)

## Contexto

Análisis previo (en sesión) reveló que el "RAG" prometido en la doc no
existe en código: lo actual es **clasificación + plantillas + Claude
genérico**. El user pidió ir a un **RAG real**. Decisiones tomadas:

| | |
|---|---|
| Embeddings | **Voyage AI** (`voyage-multilingual-2`, 1024d) |
| Qué indexar | Histórico respuestas enviadas + plantillas + normativa CO |
| Scope | Multi-tenant desde día 1 |

Estimación de costos: backfill < $0.02 one-time, recurrente ~$0.02/mes.
Total proyecto post-RAG <$2/mes (vs ~$1.50 hoy). Económicamente trivial.

## Fase 0 — Baseline (ejecutada antes de tocar nada)

| Tenant | Casos totales | **Borradores ENVIADOS** | Plantillas activas |
|---|---|---|---|
| Abogados Recovery | 1.005 | **32** (CERRADO+ENVIADO) + 2 EN_PROCESO | 8 |
| FlexFintech | 612 | 1 | 0 |
| Demo FlexPQR | 18 | 8 | 5 |

**Hallazgo clave**: el flow real es `estado='CERRADO' + borrador_estado='ENVIADO'`,
no `estado='ENVIADO'`. La tabla `borrador_feedback` mencionada en doc/exploración
**no existe en prod** — usaremos `audit_log_respuestas` (1.570 BORRADOR_GENERADO,
58 BORRADOR_EDITADO, 52 ENVIADO_LOTE) para inferir calidad.

## Fase 1 — Infra (✅ HECHA en local)

### Cambios

1. **`docker-compose.yml`**: imagen `postgres:15-alpine` → **`pgvector/pgvector:pg15`**.
   Drop-in compatible (mismo PG 15, solo +extensión). Volume preservado.
   En local: data intacta (14 tablas, 18 casos antes/después).

2. **Migración `aequitas_infrastructure/database/16_kb_rag_pgvector.sql`**:
   - `CREATE EXTENSION vector` (pgvector 0.8.2).
   - Tabla **`respuestas_kb`**:
     - `id, cliente_id, source_type, source_id, problematica, tipo_caso,`
     - `contenido, embedding vector(1024), embedding_model, metadata jsonb,`
     - `created_at, updated_at`
     - CHECK `source_type IN ('caso_enviado', 'plantilla', 'normativa')`
     - UNIQUE `(cliente_id, source_type, source_id)` — evita re-indexar.
     - FK `cliente_id → clientes_tenant ON DELETE CASCADE`.
   - Índices:
     - **HNSW** sobre `embedding` con `vector_cosine_ops` (m=16, ef_construction=64).
     - btree `(cliente_id, source_type)` para filtros pre-retrieval.
     - btree `(cliente_id, problematica) WHERE problematica IS NOT NULL` (partial).
   - **RLS** `ENABLE + FORCE` con policy:
     ```sql
     USING (cliente_id::text = current_setting('app.current_tenant_id', true)
            OR current_setting('app.is_superuser', true) = 'true')
     ```
     Mismo patrón que pqrs_casos post-SEC-2026-05-21.
   - Trigger `trg_respuestas_kb_updated_at` (auto-actualiza `updated_at`).
   - Tabla auxiliar **`kb_ingestion_log`** (id, cliente_id, source_type,
     documentos, tokens_in, embedding_model, status, error_msg, duracion_ms,
     created_at) para tracking de backfill + costos.
   - Grants idempotentes a `pqrs_backend` y `aequitas_worker` (DO block que
     verifica existencia del rol).

3. **Rol `pqrs_backend` en local**: replicado del setup staging+prod
   (NOSUPERUSER NOBYPASSRLS), grants + FORCE RLS en pqrs_adjuntos/comentarios.
   Necesario para validar aislamiento real (con pqrs_admin las policies se
   bypassean — mismo issue de SEC-2026-05-21). Password en `/tmp/pqrs_backend_pass_local`
   (mode 600), NO en .env del backend todavía (backend local sigue con pqrs_admin
   en esta fase de dev; cuando llegue Fase 3 evaluamos).

### Validación

| Check | Resultado |
|---|---|
| pgvector instalado | `0.8.2` ✅ |
| Tabla creada con todas las columnas | ✅ (12 columnas, 5 índices) |
| RLS enable + force | ✅ (`t / t`) |
| Policy creada | ✅ (`respuestas_kb_tenant_isolation`) |
| Trigger updated_at | ✅ |
| EXPLAIN usa el índice HNSW | ✅ (`Index Scan using respuestas_kb_embedding_hnsw_idx`) |
| **Aislamiento RLS con `pqrs_backend` + 3 tenants** | ✅ Demo ve 2/2, Test-B ve 1/1, super ve 3/3 |
| Cleanup post-smoke | ✅ (tabla limpia) |

## Fase 2 — Embeddings + backfill (✅ HECHA en local 2026-05-26)

### Cambios

1. **`backend/app/services/embedding_engine.py`** — wrapper async sobre Voyage:
   - Modelo: `voyage-multilingual-2` (1024d, multilingüe, optimizado retrieval).
   - `input_type` distinguido (`document` vs `query`).
   - Errores tipados (Auth no reintenta, RateLimit con backoff 1.5→3→6→12→24s).
   - Batching defensivo (MAX_BATCH_SIZE=128).
2. **`backend/tests/services/test_embedding_engine.py`** — 20 tests mocked, verde.
3. **`backend/scripts/kb_backfill.py`** — pipeline idempotente:
   - 3 sources: `caso_enviado`, `plantilla` (DB + 5 hardcoded Recovery de ai_engine.py), `normativa` (5 artículos stub).
   - UPSERT por (cliente_id, source_type, source_id).
   - Logs en `kb_ingestion_log` (docs, tokens, duración).
   - Flags: `--tenant`, `--source`, `--limit`, `--dry-run`.
4. **`docker-compose.yml`** — agregado `VOYAGE_API_KEY` al backend_v2.
5. **`backend/requirements.txt`** — `voyageai>=0.3.0` (ya instalado runtime).

### Validación E2E (con API key real, ~$0.00009 total)

| Check | Resultado |
|---|---|
| Smoke embed 1 string corto | ✅ vector(1024d), 12 tokens, norma=1.0 |
| Backfill local tenant Demo (`11111111…`) | ✅ 5 docs normativa, 658 tokens, 787ms, status `ok` en kb_ingestion_log |
| **Retrieval semántico** con 4 queries naturales | ✅ **4/4 top-1 correcto** (TUTELA→Decreto 2591, "datos centrales riesgo"→Ley 1266 Hábeas Data, "petición"→Ley 1755, "queja banco"→Circular SFC) |
| Similaridades observadas | 0.2-0.4 (queries cortas vs artículos formales; con respuestas reales subirán a 0.6-0.8) |

### Decisiones que se confirmaron

- **Threshold de relevancia** se decide en Fase 3 con datos reales (propuesta inicial: top-1 < 0.4 → ignorar, no inyectar al prompt).
- **Voyage normaliza L2** los vectores → la distancia coseno es trivial: `1 - dot(a,b)`. Eficiente.
- Las **5 hardcoded de Recovery** en local fallan FK (tenant no existe acá). En staging/prod sí están — el script las upserta correctamente cuando se corra ahí.

## Fase 3 — Retrieval integrado en `generar_borrador_para_caso` (✅ HECHA en local 2026-05-26)

### Cambios

1. **`backend/app/services/rag_engine.py`** — módulo nuevo, signature única:
   - `buscar_docs_similares(conn, tenant_id, asunto, cuerpo, *, tipo_caso=None, top_k=3, threshold=0.40, engine=None)`
   - Construye query como `{asunto}\n\n{cuerpo[:800]}` (señal alta del asunto + body truncado).
   - Embed con `input_type='query'`, retrieval con `<=>` (coseno) + filtros: `cliente_id`, `(1-sim) >= threshold`, opcional `tipo_caso`.
   - **Degrada elegante**: si Voyage falla, devuelve `[]` y el caller sigue sin RAG (no rompe el worker).
   - `formatear_contexto_para_prompt(docs)` — agrupa por source_type con secciones legibles (NORMATIVA APLICABLE / PLANTILLAS DE REFERENCIA / CASOS RESUELTOS).

2. **`backend/app/services/plantilla_engine.py`** — cambios mínimos sin romper API:
   - `generar_borrador_con_ia` acepta ahora kwargs opcionales `conn`, `tenant_id`.
   - Si ambos están + `VOYAGE_API_KEY` configurada → invoca `buscar_docs_similares` y inyecta el contexto en el user prompt entre cuerpo e instrucciones finales.
   - Si RAG falla, log warning + sigue sin contexto (igual a hoy).
   - Atributo de módulo `_last_rag_docs` para que el caller persista los docs usados en audit.
   - `generar_borrador_para_caso` ahora pasa `conn` + `tenant_id` y registra `metadata.rag_docs` (con source_type, source_id, sim_score) en `audit_log_respuestas`. Devuelve además `rag_docs_usados` en el dict.

3. **`backend/tests/services/test_rag_engine.py`** — 19 tests con mocks: query building (5), happy paths (4), filtros (top-k, threshold, tipo_caso), degradación elegante (5 escenarios: query vacía, embed auth fail, embed generic fail, DB fail, sin docs ≥ threshold), formato del contexto (4).

### Validación E2E real (en local, sin tocar prod)

Test con caso "Quiero presentar una acción de tutela urgente":
- Retrieval recuperó `decreto-2591-91-art-1` (sim **0.591**, vs 0.42 sin filtro/contexto previo).
- Filtro por `tipo_caso='TUTELA'` funcionó (excluyó normativa de otros tipos).
- Prompt final a Claude incluye sección "## NORMATIVA APLICABLE" con el texto completo del Decreto + instrucción "NO copies literal".
- `_last_rag_docs` propaga los docs al caller para audit.

Tests verde: 39/39 (19 rag + 20 embedding). Costo total Voyage sesión: ~770 tokens = $0.000092.

### Política de uso

- Solo se invoca RAG en el camino **B (sin plantilla)** — el camino A (plantilla exacta + variables) sigue como antes.
- Si `_TODO en empresas.json` para MGT/EMSA Recovery fuera análogo aquí, el sistema sigue funcionando: si no hay docs ≥ threshold, no inyecta nada (cae al prompt original sin RAG).

## Lo que sigue

1. **Usuario**: generar API key en https://dash.voyageai.com → guardar en
   `backend/.env` como `VOYAGE_API_KEY=...` (NO pegarla en chat).
2. **Servicio `backend/app/services/embedding_engine.py`**:
   - Wrapper async sobre Voyage SDK con retry exponencial + rate limit.
   - Tracking de tokens consumidos (escribe a `kb_ingestion_log`).
   - Función `embed_texts(textos: list[str]) -> list[list[float]]` batched.
3. **Script `backend/scripts/manual/kb_backfill.py`**:
   - Levanta los 32 enviados de Recovery + 8 plantillas activas + las
     5 plantillas hardcodeadas de `ai_engine.py:64-91`.
   - Para normativa: descargar Decreto 2591/91, Ley 1755/2015, Ley 1266/2008
     y chunkear por artículo.
   - Embedea + INSERT a `respuestas_kb`.
   - Log en `kb_ingestion_log`.
4. **Pendiente staging/prod**: replicar imagen pgvector + aplicar migración 16
   en ventana corta (mismo patrón de los deploys previos).

## Pendientes operativos

- [ ] **Replicar imagen pgvector + migración 16 en staging** (ventana corta).
- [ ] **Replicar idem en prod** (ventana corta, S3 backup previo, mismo runbook que el D3 deploy).
- [ ] **API key de Voyage** (a generar por el user — bloqueante para Fase 2).
- [ ] **Documentar** en `Brain/01_ARQUITECTURA_MAESTRA.md` la nueva pieza RAG.

## Archivos modificados/creados (rama feat/rag-fase1-pgvector-2026-05-26)

```
M docker-compose.yml                                    (1 línea + comentario)
A aequitas_infrastructure/database/16_kb_rag_pgvector.sql  (~120 líneas)
A Brain/sprints/SPRINT_RAG_FASE1_2026-05-26.md             (este archivo)
```

Sin push aún (esperando confirmación del user).
