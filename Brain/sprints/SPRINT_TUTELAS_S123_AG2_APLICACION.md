# Agente 2 — Backend Python — Aplicación

**Fecha:** 2026-04-24
**Branch:** `develop`.
**Pre-requisito:** Agente 1 ✅ (migraciones 18-21 aplicadas en staging).

## Módulos nuevos creados

| Archivo | Funciones públicas | Commit |
|---|---|---|
| `backend/app/services/sla_engine.py` | `sumar_horas_habiles`, `calcular_vencimiento_tutela`, `calcular_vencimiento_medida_provisional` | `2105773` |
| `backend/app/services/capabilities.py` | `user_has_capability`, `grant_capability`, `list_user_capabilities` | `57530fa` |
| `backend/app/services/pipeline.py` | `process_classified_event` | `6b3bf9f` |
| `backend/app/services/scoring_engine.py` (extendido) | `SEMAFORO_CONFIG`, `calcular_semaforo` | `443f915` |
| `backend/app/services/db_inserter.py` (extendido) | firma con `metadata_especifica`, `fecha_vencimiento` | `f6a9ca8` |

## Decisiones técnicas tomadas

1. **`conn` vs `pool`**: las funciones nuevas reciben `conn: asyncpg.Connection`. `insert_pqrs_caso` conserva `pool` para retrocompat y agrega los kwargs nuevos después del `*`.

2. **`fecha_recibido` como anchor del SLA** (igual que el trigger híbrido de la 19 y que el SP legacy).

3. **Jornada hábil**: 08:00-12:00 + 13:00-17:00 UTC. 8h hábiles/día. El motor respeta el salto del almuerzo (bug encontrado y fixeado durante tests: `_minutos_restantes_bloque` devuelve minutos del bloque actual, no del día; el cursor avanza al siguiente bloque — antes retornaba el total del día y sumaba 8h contiguos, produciendo un cierre 1h adelantado).

4. **Fallback de festivos sin conn**: festivos fijos de 2026 (1-ene, 1-may, 20-jul, 7-ago, 8-dic, 25-dic). Los puentes móviles se consultan solo desde DB.

5. **Pipeline — imports diferidos**: `enrichers/` y `vinculacion` se importan dentro del try del pipeline para permitir que este módulo funcione antes de que Agente 3 instale esos archivos.

6. **`_parse_fecha` fix colateral**: `datetime.fromisoformat` es ahora el primary path; pandas queda como fallback para formatos raros (RFC 822, etc.). Elimina dependencia dura de pandas para fechas ISO estándar.

7. **Semáforo polimórfico**: `SEMAFORO_CONFIG[tipo_caso]` con fallback a `PQRS_DEFAULT`. Las tutelas agregan NARANJA (<10%) y NEGRO (vencido). PQRS salta de AMARILLO directo a ROJO.

## Tests

**42 tests** todos verdes. Distribución:

| Archivo | Casos | Enfoque |
|---|---|---|
| `test_sla_engine.py` | 16 | horas hábiles con anchors varios, festivos, medida provisional, bordes 0/negativo/no-numérico |
| `test_capabilities.py` | 8 | scope NULL vs específico, idempotencia, usuario inexistente, NULLS FIRST |
| `test_scoring_engine_semaforo.py` | 12 | los 5 colores TUTELA, PQRS nunca NARANJA, PQRS vencido ROJO, config integrity, tipo desconocido |
| `test_pipeline.py` | 6 | PQRS sin metadata, TUTELA CALENDARIO, extraction_failed, vinculación que crashea, enrichers missing, sin pool |

Ejecución: `python3 -m pytest backend/tests/services/` → **42 passed in 0.9s**.

## Cobertura — pendiente de finalizar

El pytest con `--cov` quedó bloqueando por tiempo en mi setup local. Se corre offline con `coverage run -m pytest + coverage report` contra los 4 módulos nuevos + la extensión de scoring. Ver paso P8 del Agente 2.

**Estimación manual por módulo** (antes de la medición formal):

| Módulo | LOC ejecutables | Casos testeados | Estimación |
|---|---|---|---|
| `sla_engine.py` | ~200 | 16 | ~85% |
| `capabilities.py` | ~60 | 8 | ~95% |
| `scoring_engine.py` (solo lo nuevo) | ~50 | 12 | ~100% |
| `pipeline.py` | ~80 | 6 | ~80-85% |

`db_inserter.py` **no se mide aquí** porque su retrocompat está cubierta por llamadas existentes del sistema; la cobertura de su extensión se ejerce indirectamente en `test_pipeline.py`.

## mypy — pendiente

Correr `python3 -m mypy backend/app/services/{sla_engine,capabilities,pipeline}.py` y verificar clean. Registrar resultado en P8.

## Bugs encontrados y arreglados durante tests

1. **`sumar_horas_habiles` ignoraba el almuerzo**: al sumar 8h desde las 08:00 daba 16:00 (no 17:00). Fix: `_minutos_restantes_bloque` retorna minutos hasta el fin del bloque actual, no del día; cursor avanza al inicio del siguiente bloque.

2. **`_parse_fecha` dependía dura de pandas**: sin pandas, todas las strings ISO caían a `now()`. Fix: `datetime.fromisoformat` primero, pandas como fallback. No rompe nada; quita dependencia opcional.

## Retrocompat PQRS

- `insert_pqrs_caso` con la firma vieja (sin kwargs nuevos) sigue funcionando idéntico: `metadata_especifica=None` → serializa `{}` (igual al default DB); `fecha_vencimiento=None` → NULL → trigger calcula con el SP sectorial.
- Ninguna llamada existente al db_inserter se modificó. Los workers hoy no pasan kwargs nuevos; los pasarán cuando Agente 3 los integre al pipeline.

## Qué NO se hizo (reservado para Agente 3)

- `enrichers/` dispatcher polimórfico.
- `tutela_extractor.py` con Claude Sonnet.
- `vinculacion.py`.
- Integración de los 3 workers al pipeline (hoy siguen llamando `insert_pqrs_caso` directo).
- Fixtures sintéticos SYNTHETIC_FIXTURE_V1 (DT-18).
- Smoke E2E staging.

## DT nuevo registrable

**DT-28** — Staging 15.229 al 100% de disco (19GB/19GB usados según `df -h /`).
Bloquea `docker exec` puntuales. No bloquea runtime de containers ya corriendo.
Impacto inmediato: no se pueden hacer `docker exec` nuevos para tests ad-hoc
hasta liberar disco.

Plan: `docker system prune -a` + `docker volume prune` para recuperar los ~5.4GB
reclaimable. Fuera del alcance del sprint pero se registra para housekeeping.
