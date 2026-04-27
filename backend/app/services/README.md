# `app/services/` — Inventario de módulos

Servicios de dominio del backend. Todos consumibles por las rutas FastAPI (`app/api/routes/`) y por los workers (`worker_ai_consumer.py`, `master_worker_outlook.py`, `demo_worker.py`).

Para arquitectura completa ver `Brain/00_maestro/01_ARQUITECTURA_MAESTRA.md`. Para sprint Tutelas ver `Brain/sprints/SPRINT_TUTELAS_S123.md`.

## Inventario

| Módulo | Responsabilidad | Sprint origen |
|---|---|---|
| `ai_classifier.py` | Clasificador híbrido + retry exponencial Anthropic + ClassificationResult dataclass. | Sprint 2 ("El Cerebro") |
| `ai_engine.py` | `clasificar_hibrido` keywords + Claude Haiku para casos confidence-bajo. | Sprint 2 |
| `clasificador.py` | `parece_pqrs(subject, body, sender)` — filtro pre-clasificación. | Sprint 2 |
| `db_inserter.py` | INSERT en `pqrs_casos` con asyncpg pool. **Extendido en Sprint Tutelas:** kwargs `metadata_especifica` + `fecha_vencimiento`, propaga `external_msg_id` y `documento_peticionante_hash`. | Sprint 2 + Tutelas |
| `kafka_producer.py` | Producer Kafka para eventos del pipeline. | Sprint 2 |
| `plantilla_engine.py` | Genera borrador de respuesta usando plantillas del tenant. | Sprint plantillas |
| `scoring_engine.py` | Reglas keywords + contexto + confidence. **Extendido en Sprint Tutelas:** `SEMAFORO_CONFIG` polimórfico + `calcular_semaforo`. | Sprint 2 + Tutelas |
| `sharepoint_engine.py` | Integración SharePoint para storage de adjuntos. | Sprint integraciones |
| `storage_engine.py` | Cliente MinIO/S3 + retry. ⚠️ Hace 3 retries de conexión al import (DT-29). | Sprint 1 |
| `zoho_engine.py` | Integración Zoho Mail (auth + send). | Sprint integraciones |
| **`sla_engine.py`** ⭐ | **NUEVO Tutelas.** Motor Python horas hábiles. `sumar_horas_habiles`, `calcular_vencimiento_tutela`, `calcular_vencimiento_medida_provisional`. Coexiste con SP sectorial. | Sprint Tutelas |
| **`capabilities.py`** ⭐ | **NUEVO Tutelas.** `user_has_capability`, `grant_capability` idempotente, `list_user_capabilities`. RLS reforzado por policy DB. | Sprint Tutelas |
| **`pipeline.py`** ⭐ | **NUEVO Tutelas.** `process_classified_event(clasif, event, cliente_id, conn, pool)` — orquestador post-clasificación. Imports diferidos de enrichers/vinculacion. | Sprint Tutelas |
| **`vinculacion.py`** ⭐ | **NUEVO Tutelas.** `vincular_con_pqrs_previo` — busca PQRS previos del mismo `documento_peticionante_hash` en ventana 30d. 4 motivos. | Sprint Tutelas |
| **`enrichers/`** ⭐ | **NUEVO Tutelas.** Paquete con dispatcher polimórfico por `tipo_caso`. | Sprint Tutelas |
| `enrichers/__init__.py` | `ENRICHERS` dict + `enrich_by_tipo`. Auto-registro al importar. | Sprint Tutelas |
| `enrichers/tutela_extractor.py` | Claude Sonnet + tool_use + `TUTELA_SCHEMA`. Hash documento + fallback defensivo. | Sprint Tutelas |

⭐ = creado o re-tocado en sprint Tutelas (2026-04).

## Invariantes del pipeline

Reglas que el código asume y mantiene. Romperlas requiere actualizar este README.

### `db_inserter.insert_pqrs_caso`

- **`fecha_vencimiento` kwarg `None` → INSERT pasa `NULL` → trigger `fn_set_fecha_vencimiento` calcula via SP sectorial.**
- **`fecha_vencimiento` kwarg con datetime → trigger respeta el valor entrante (capa 1 del trigger híbrido).**
- **`metadata_especifica` kwarg `None` → INSERT pasa `'{}'::jsonb` (default DB).**
- **`external_msg_id` se lee de `event["external_msg_id"]` con fallback a `message_id` / `id`. Strip whitespace → `None` si vacío.**
- **`documento_peticionante_hash` se extrae de `metadata_especifica["accionante"]["documento_hash"]`. `None` si no existe o no es dict.**
- Retrocompat 100%: llamada legacy `insert_pqrs_caso(event, result, pool)` sin kwargs sigue funcionando idéntico al pre-sprint.

### `pipeline.process_classified_event`

- **Solo invoca `enrich_by_tipo` si está disponible (try/except ImportError).** Permite que el pipeline funcione antes que los enrichers se instalen.
- **SLA Python solo se dispara para `tipo_caso = 'TUTELA'` con metadata utilizable** (sin `_extraction_failed` ni `_enrichment_failed`). Para todo lo demás, deja `fecha_vencimiento = None` y el trigger DB se encarga.
- **Vinculación best-effort:** si lanza excepción, se loguea y el pipeline continúa. El caso se inserta igual.

### `enrich_tutela`

- **Si `ANTHROPIC_API_KEY` no está seteada → fallback inmediato sin invocar al cliente.**
- **Si Claude lanza excepción de cualquier tipo → fallback `_extraction_failed=True` con defaults 48h HABILES + AUTO_ADMISORIO + `_requiere_revision_humana=True`.**
- **`accionante.documento_raw` se hashea con `salt = clientes_tenant.config_hash_salt` y se borra del dict antes de retornar.**
- **`_confidence.plazo_informe_horas < 0.85` → seta `_requiere_revision_humana = True`.**

### `sla_engine.sumar_horas_habiles`

- **Jornada hábil: 08:00-12:00 + 13:00-17:00 UTC. 8h/día.**
- **Salta fines de semana (sáb/dom) y festivos de `festivos_colombia`.**
- **Inicio fuera de jornada → ajusta al siguiente momento hábil antes de empezar a sumar.**
- **`horas = 0` → retorna `inicio` sin tocar.**
- **`horas < 0` → `ValueError`.**

### `vinculacion.vincular_con_pqrs_previo`

- **Filtra por `cliente_id = $1` (cross-tenant safe + reforzado por RLS DB).**
- **Excluye `tipo_caso = 'TUTELA'` (no cascadea entre tutelas).**
- **Excluye el caso actual (`id != $3`).**
- **Ventana default 30 días.**
- **`UPDATE` falla silenciosamente** (logger.exception); el resultado se retorna igual.

### Auto-registro de enrichers

- **Cada enricher se registra en `ENRICHERS[<tipo_caso>]` al importarse.**
- **`enrichers/__init__.py` hace `from . import tutela_extractor` para gatillar el side-effect.**
- **Al agregar un enricher nuevo, agregar la línea `from . import <archivo>` al `__init__.py` del paquete.**

## Convenciones de error

- **Excepciones del extractor:** capturadas en `enrich_tutela` → fallback dict.
- **Excepciones del SLA:** loggeadas en `pipeline`; cae al trigger DB.
- **Excepciones de vinculación:** loggeadas en `pipeline`; el INSERT del caso ya ocurrió y se preserva.
- **Excepciones de `db_inserter`:** propagadas hasta el worker. El worker decide DLQ / reintento.

## Tests

- **Unit tests (mocks 100%):** `backend/tests/services/` y `backend/tests/services/enrichers/`.
- **Integration tests (mocks asyncpg + AsyncAnthropic):** `backend/tests/integration/`.
- **Smoke E2E real** (Claude API + staging DB via tunnel): `backend/tests/test_tutela_pipeline_staging.py` (opt-in `RUN_STAGING_SMOKE=1`).
- **ARC regression** contra staging real: `backend/tests/integration/test_arc_regression.py` (opt-in `RUN_STAGING_REGRESSION=1`).

Correr todo el sprint en local con `--noconftest` (DT-29 storage_engine eager):
```bash
cd backend && MINIO_ENDPOINT="127.0.0.1:1" \
  python3 -m pytest tests/services/ tests/integration/ --noconftest -q
```
