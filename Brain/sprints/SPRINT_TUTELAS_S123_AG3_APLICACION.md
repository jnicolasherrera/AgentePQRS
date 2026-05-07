# Agente 3 — AI/Worker — Aplicación

**Fecha:** 2026-04-24
**Branch:** `develop` (post DT-28 resuelto).
**Pre-requisito:** Agente 2 ✅.

## Módulos nuevos creados

| Archivo | Responsabilidad |
|---|---|
| `backend/app/services/enrichers/__init__.py` | Dispatcher polimórfico `enrich_by_tipo`. Auto-registro de enrichers. |
| `backend/app/services/enrichers/tutela_extractor.py` | Extractor Claude Sonnet + tool_use + TUTELA_SCHEMA + hash documento + fallback. |
| `backend/app/services/vinculacion.py` | `vincular_con_pqrs_previo` con 4 motivos + UPDATE metadata_especifica. |
| `backend/tests/fixtures/tutelas/01_auto_admisorio_simple.txt` | Fixture HABILES estándar. |
| `backend/tests/fixtures/tutelas/02_auto_con_medida_provisional.txt` | Fixture ambiguo + medida CALENDARIO 24h. |
| `backend/tests/fixtures/tutelas/03_fallo_primera_instancia.txt` | Fixture FALLO_PRIMERA sin plazo informe. |
| `backend/tests/services/enrichers/test_tutela_extractor.py` | Tests del extractor con mocks de AsyncAnthropic. |
| `backend/tests/services/test_vinculacion.py` | Tests de vinculación (4 motivos + aislamiento tenant). |
| `backend/tests/test_tutela_pipeline_staging.py` | Smoke E2E staging (opt-in via `RUN_STAGING_SMOKE=1`). |

## Workers modificados

### `worker_ai_consumer.py` (cambio mínimo)

Reemplazada la llamada directa a `db_inserter.insert_pqrs_caso` por
`pipeline.process_classified_event`. Se toma una conn del pool para que el
pipeline pueda hacer vinculación y eventual DB-touch del extractor.

### `master_worker_outlook.py` (adapter + pool)

- Agregado pool asyncpg mínimo (`min=1, max=2`) porque el worker usaba conn única.
- Adapter `ResultadoClasificacion → ClassificationResult` antes de invocar el pipeline.
- Construcción explícita de `event` dict compatible con `db_inserter`.
- Pre-check de dedup por `external_msg_id` preservado (semántica del `ON CONFLICT DO NOTHING` del INSERT manual previo) — porque `db_inserter` aún no lo implementa como UNIQUE en el INSERT.
- **Reemplazo del INSERT manual** por `process_classified_event`. La lógica post-INSERT (acuse de recibo ARC, generación de borrador, radicado) se mantiene intacta.
- Eliminado el cálculo manual de `venc` con pandas CustomBusinessDay. Ahora:
  - Si es TUTELA con metadata → `sla_engine` Python.
  - Si no → trigger DB con el SP sectorial (respeta régimen por tenant).
- Eliminado el round-robin Redis (`rr:{c_id}`). Ahora usa el `_round_robin_analista` del `db_inserter` (ORDER BY COUNT). Cambio semántico documentado.

### `demo_worker.py` (adapter + pool)

Mismos cambios que `master_worker_outlook`: pool mínimo, adapter, pre-check dedup, INSERT manual → pipeline.

## Decisiones técnicas

1. **Auto-registro**: `tutela_extractor.py` hace `ENRICHERS["TUTELA"] = enrich_tutela` al importarse; el `__init__.py` del paquete provoca ese import una vez.
2. **Fallback robusto del extractor**: en cualquier excepción (API error, rate limit, no tool_use en respuesta, ausencia de API key) retorna `{"_extraction_failed": True, "plazo_informe_horas": 48, "plazo_tipo": "HABILES", "_requiere_revision_humana": True, ...}`. El pipeline continúa sin metadata utilizable y deja que el trigger DB calcule fecha_vencimiento con el SP sectorial default (2 días hábiles para TUTELA).
3. **Hash documento**: SHA-256 hex con `salt || ":" || documento_raw`. El salt viene de `clientes_tenant.config_hash_salt` (migración 19). Cross-tenant SAFE: el mismo documento con dos salts distintos genera dos hashes distintos.
4. **Detección del marker sintético**: si el body contiene `SYNTHETIC_FIXTURE_V1` y el env es `ENV=prod`, se loguea WARN. En staging/dev pasa silencioso. En metadata queda `_synthetic_fixture: "SYNTHETIC_FIXTURE_V1"` para trazabilidad.
5. **Confidence → revisión humana**: si `_confidence.plazo_informe_horas < 0.85`, el extractor marca `_requiere_revision_humana=True`. Esto es **comportamiento esperado con fixtures sintéticos** — los oficios reales darán confidence más alto (DT-18).
6. **Vinculación cross-tenant SAFE**: la query filtra por `cliente_id = $1`, además RLS refuerza a nivel DB. Excluye tutelas previas (`tipo_caso != 'TUTELA'`) para no cascadear. Ventana 30 días por default, parametrizable.
7. **Motivo de vinculación**:
   - `PQRS_NO_CONTESTADO`: match único, sin `enviado_at`.
   - `RESPUESTA_INSATISFACTORIA`: match único con `enviado_at`.
   - `MULTIPLE_MATCHES`: ≥2 matches.
   - `None`: sin matches (no se persiste).
8. **Preservación del dedup `external_msg_id`**: el INSERT manual del master/demo tenía `ON CONFLICT (cliente_id, external_msg_id) DO NOTHING`. El `db_inserter` actual no lo tiene. Para no perder esta protección contra duplicados, cada worker hace un `SELECT 1 WHERE external_msg_id=...` antes del pipeline. **Deuda futura**: migrar esa cláusula al `db_inserter` para uniformar.

## Tests

### Tests unitarios (mocks 100%)

`test_tutela_extractor.py` (9 tests):
- Auto-registro del enricher ✓.
- 3 fixtures: HABILES estándar (confidence alto, sin flag revisión), ambiguo (flag revisión activado), FALLO_PRIMERA (tolera ausencia de plazo real).
- `documento_raw` → hash + borrado.
- Hash determinístico y sensible al salt.
- Excepción Anthropic → fallback con `_extraction_failed`.
- Sin API key → fallback inmediato sin invocar cliente.
- Dispatcher: tipo sin enricher → `{}`; enricher que lanza → `_enrichment_failed`.

`test_vinculacion.py` (6 tests):
- 4 motivos (NO_CONTESTADO, INSATISFACTORIA, MULTIPLE_MATCHES, sin match).
- Query filtra por `cliente_id` (aislamiento tenant).
- UPDATE que falla no propaga excepción (best-effort).

### Smoke E2E staging

`test_tutela_pipeline_staging.py` — evento sintético → `pipeline.process_classified_event` directo → verificación SQL del caso insertado.

**Opt-in** vía `RUN_STAGING_SMOKE=1` para que no corra por defecto en CI local. Deja el caso con asunto `[SMOKE_TEST_AGENTE3]` y `external_msg_id=SMOKE_AGENTE3_{uuid}` para que Agente 4 lo reutilice.

**Presupuesto Claude**: máximo 1 call real durante este smoke (si `ANTHROPIC_API_KEY` está configurada). Sin key, el extractor usa fallback y el pipeline sigue. Alcance aceptado: el test verifica el flujo completo, no el contenido extraído.

## Hallazgo operativo — conftest.py de tests/

El `tests/conftest.py` importa `app.main` que importa todas las rutas que importan `storage_engine`. En env local sin MinIO, `storage_engine` intenta 3 retries de conexión (90s total) al importarse por `client` module-level. Eso hace que pytest con el conftest global **se cuelgue durante collect** por ~90s.

**Workaround aplicado**: tests del sprint Tutelas se corren con `pytest --noconftest`. Los fixtures del conftest global (`test_client`, `mock_db_connection`, `admin_user`, etc.) no son usados por los tests nuevos.

**Deuda futura (DT-29)**: refactorizar `storage_engine` para hacer el reconnect lazy (al primer uso, no al import), o añadir un `conftest.py` en `tests/services/` que patche el bloqueo. Housekeeping del Agente 6 Sesión 3.

## DT-26/DT-28 relación con Agente 3

- `worker_ai_consumer.py` está integrado al pipeline de todos modos, aunque el container esté apagado (DT-28 mitigation). Se reactivará cuando Kafka esté up (DT-26 resolved).
- Smoke E2E usa `master_worker_outlook.py` por instrucción (bypassa Kafka).
- El extractor Claude Sonnet no depende de Kafka → es robusto al estado DT-26.

## Qué NO hizo el Agente 3

- No modificó el `db_inserter.py` (Agente 2).
- No modificó el `pipeline.py` (Agente 2).
- No deployó a staging server (38 commits atrás; tarea del Agente 6).
- No corrió Claude real durante tests unitarios (100% mocks). Smoke E2E queda opt-in.
