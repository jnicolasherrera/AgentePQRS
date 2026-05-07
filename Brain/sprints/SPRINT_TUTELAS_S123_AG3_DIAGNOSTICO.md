# Agente 3 — Diagnóstico obligatorio (paso 1)

**Fecha:** 2026-04-24
**Branch:** `develop` @ `5001ff3` (post DT-28 resuelto).
**Estado staging:** 56% disco, ai-worker stopped y removido, Kafka ausente (DT-26).

## Workers inventariados

| Worker | LOC | Estado en staging | Patrón actual |
|---|---|---|---|
| `worker_ai_consumer.py` | 141 | **parado** (container removido 2026-04-24 por DT-28) | `classify_email_event` + `db_inserter.insert_pqrs_caso` — limpio, alineado con el pipeline v3 |
| `master_worker_outlook.py` | 404 | **up** (activo) | `clasificar_hibrido` directo + INSERT manual con campos específicos + lógica de acuse + borrador |
| `demo_worker.py` | 560 | **up** (activo) | `clasificar_hibrido` directo + INSERT manual + dedup Redis + acuse + adjuntos |

## Puntos de inyección del pipeline

### `worker_ai_consumer.py` (líneas 73–76)

```python
# Actual:
result = await classify_email_event(event)
caso_id = await insert_pqrs_caso(event, result, pool)

# Tras integración:
async with pool.acquire() as conn:
    caso_id = await pipeline.process_classified_event(
        result, event, uuid.UUID(tenant_id), conn, pool,
    )
```

Adapter trivial: `result` ya es `ClassificationResult`, `event` tiene `tenant_id` y `correlation_id`. Se agrega un `async with pool.acquire() as conn` para dar la conexión al pipeline (vinculación y extractor la necesitan).

### `master_worker_outlook.py` (líneas 223–252)

Flujo actual:
1. `resultado = await clasificar_hibrido(subject, body, sender)` → retorna `ResultadoClasificacion` (enum-based).
2. Cálculo manual de `venc` con pandas CustomBusinessDay.
3. Round-robin de analistas custom con Redis `rr:{c_id}`.
4. INSERT manual directo (12 columnas).
5. Post-INSERT: acuse de recibo ARC + generación de borrador.

**Adapter necesario** para invocar el pipeline:
- Convertir `ResultadoClasificacion` → `ClassificationResult`:
  ```python
  clasif = ClassificationResult(
      tipo_caso=resultado.tipo.value,
      prioridad=resultado.prioridad.value,
      plazo_dias=resultado.plazo_dias,
      cedula=resultado.cedula, nombre_cliente=resultado.nombre_cliente,
      es_juzgado=resultado.es_juzgado, confianza=resultado.confianza,
      borrador=None,
  )
  ```
- Construir `event` dict compatible con `db_inserter` (espera `tenant_id`, `correlation_id`, `subject`, `body`, `sender`, `date`).
- Reemplazar el INSERT manual por `pipeline.process_classified_event(...)`.
- **Preservar post-INSERT** (acuse + borrador + radicado). El pipeline retorna `caso_id` igual que el INSERT manual, así que la lógica post sigue funcionando con `db_id = caso_id`.

**Cosas que se pierden en master_worker** al migrar al pipeline:
- Cálculo manual de `venc` con pandas CustomBusinessDay → reemplazado por el trigger DB o el sla_engine Python (tutelas).
- Round-robin Redis-based → reemplazado por `_round_robin_analista` de `db_inserter` (menos sofisticado; usa `ORDER BY COUNT`). Esto **puede ser un cambio de comportamiento** que hay que observar; no es regresión crítica pero sí cambio semántico.
- `external_msg_id` y `ON CONFLICT DO NOTHING`: el `db_inserter` actual no tiene la misma dedup. Si se requiere preservar, agregar un pre-check en el worker antes de invocar el pipeline, o extender db_inserter. **Decisión conservadora:** preservar el pre-check en el worker (consulta `SELECT 1 WHERE external_msg_id=...`), antes del pipeline.

### `demo_worker.py` (líneas 405–431)

Mismo patrón que `master_worker_outlook`. Mismo adapter aplicable. Además tiene dedup propia (`dedup:demo:msg:{id}` en Redis con TTL 24h) que se preserva antes del pipeline.

## Mapeo `ResultadoClasificacion` → `ClassificationResult`

| Campo `ResultadoClasificacion` | Campo `ClassificationResult` | Nota |
|---|---|---|
| `tipo: TipoCaso` | `tipo_caso: str` | `.value` del enum |
| `prioridad: Prioridad` | `prioridad: str` | `.value` del enum |
| `plazo_dias: int` | `plazo_dias: int` | igual |
| `cedula: Optional[str]` | `cedula: Optional[str]` | igual |
| `nombre_cliente: Optional[str]` | `nombre_cliente: Optional[str]` | igual |
| `es_juzgado: bool` | `es_juzgado: bool` | igual |
| `confianza: float` | `confianza: float` | igual |
| — | `borrador: Optional[str]` | `None` inicial; se genera después |
| `radicado` | — | se descarta (master/demo lo recalculan después del INSERT con `PQRS-{año}-{id[:8]}`) |

## Decisiones antes de integrar

1. **`pipeline.process_classified_event`** se llama desde los 3 workers con el mismo contrato.
2. **Dedup por `external_msg_id`** se mantiene en el worker (pre-check) porque el `db_inserter` actual no lo implementa. Opción futura: migrarlo al db_inserter para uniformidad.
3. **Round-robin Redis de master_worker**: se deja por ahora el `ORDER BY COUNT` del `db_inserter`. Cambio semántico documentado. Si Paola/Martín reportan desbalance, se revive el RR Redis en db_inserter.
4. **Cálculo manual `venc` con pandas** en master/demo: se reemplaza. Si el caso no es TUTELA, el trigger DB calcula con el SP sectorial (consistente con régimen del tenant). Si es TUTELA con metadata completa, el sla_engine Python lo calcula.
5. **enrichers/ se importa de forma diferida** en el pipeline (ya está), así que los 3 workers funcionan sin cambios si enrichers aún no está listo.

## Qué NO hace el Agente 3

- No modifica `master_worker_outlook.py`/`demo_worker.py` lógica de acuse, borrador ni radicado.
- No modifica `db_inserter.py` de nuevo (ya extendido por Agente 2).
- No deploya a staging server (el server está 38 commits atrás; deploy es tarea del Agente 6).

## DTs abiertos relevantes para Agente 3

- **DT-18**: necesita oficios reales de Paola para validar confianza productiva del extractor. Esperado: fixtures sintéticos darán `_confidence` bajo en algunos casos; es comportamiento correcto.
- **DT-26**: Kafka ausente en staging → smoke E2E usa `master_worker_outlook.py` (per tu instrucción), no `worker_ai_consumer.py`.
- **DT-27**: SQLs legacy siguen en raíz — no afecta Agente 3.
- **DT-28**: resuelta; staging con espacio suficiente para tests.
