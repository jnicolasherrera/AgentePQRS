# Agente 2 — Diagnóstico obligatorio

**Fecha:** 2026-04-24
**Branch:** `develop` @ `61eb1f4` (Agente 1 cerrado).
**git status:** limpio.

## Inventario relevante de `backend/app/services/`

```
ai_classifier.py       (Sprint 2 - ClassificationResult, retry Anthropic)
ai_engine.py           (clasificar_hibrido)
clasificador.py        (servicio de clasificación agregado)
db_inserter.py         (INSERT en pqrs_casos - a extender)
kafka_producer.py      (producer Kafka)
plantilla_engine.py    (motor de plantillas de respuesta)
scoring_engine.py      (keywords + confidence - a extender con semáforo)
sharepoint_engine.py   (integración SharePoint)
storage_engine.py      (MinIO/S3)
zoho_engine.py         (integración Zoho)
```

Los 4 módulos nuevos del Agente 2 viven bajo `backend/app/services/`:

- `sla_engine.py` (NUEVO)
- `capabilities.py` (NUEVO)
- `pipeline.py` (NUEVO)
- `scoring_engine.py` (EXTENDER — no reescribir)
- `db_inserter.py` (EXTENDER firma)

## Firma actual de `insert_pqrs_caso`

```python
async def insert_pqrs_caso(
    event: dict,
    result: ClassificationResult,
    pool: asyncpg.Pool,
) -> uuid.UUID
```

**Observaciones importantes:**

1. Usa `pool: asyncpg.Pool`, **no** `conn: asyncpg.Connection` como dice el v3. Decisión: las funciones nuevas del sprint (`calcular_vencimiento_tutela`, `user_has_capability`, etc.) recibirán `conn` como arg, coherente con el v3. Para `insert_pqrs_caso` mantengo `pool` en la firma principal y agrego `metadata_especifica` y `fecha_vencimiento` como **kwargs opcionales** al final para preservar retrocompat.

2. El INSERT actual hace referencia a una columna `correlation_id` en `pqrs_casos`. **Esa columna NO existe en el baseline de prod** tomado el 2026-04-23 (verificado en `migrations/baseline/prod_schema_20260423_1600.sql`). Sí existe en `PqrsCaso` de `models.py`. Esto es **drift preexistente al sprint Tutelas**, no causado ni resuelto por él. Si se intenta `insert_pqrs_caso` contra el staging reconstruido, falla. Se registrará en Brain pero no se arregla aquí.

3. El round-robin `_round_robin_analista` busca por `rol IN ('analista', 'abogado') AND is_active`. En staging ARC fake hay 4 elegibles (2 abogados + 2 analistas) — OK para Agente 3 smoke.

## `ClassificationResult` (de `ai_classifier.py`)

```python
@dataclass
class ClassificationResult:
    tipo_caso: str       # TUTELA | PETICION | QUEJA | RECLAMO | SOLICITUD
    prioridad: str       # CRITICA | ALTA | MEDIA | BAJA
    plazo_dias: int
    cedula: Optional[str]
    nombre_cliente: Optional[str]
    es_juzgado: bool
    confianza: float
    borrador: Optional[str]
```

Consumido por `db_inserter.insert_pqrs_caso`. La extensión del Agente 2 agrega parámetros **paralelos** a este dataclass (no lo modifica).

## `scoring_engine.py` — estado actual

Tiene clasificación por keywords y contexto + confidence. **No tiene ningún símbolo relacionado con semáforo.** La extensión del Agente 2 **prepende** al archivo:

- Constante `SEMAFORO_CONFIG: dict[str, dict]` con 2 claves (`PQRS_DEFAULT`, `TUTELA`).
- Función `calcular_semaforo(tipo_caso, fecha_creacion, fecha_vencimiento, ahora=None) → str`.

No se toca la lógica de `SCORING_RULES`, `score_email`, `apply_context_signals`, `compute_confidence`, `score_and_classify`.

## `festivos_colombia` — estructura

**Schema real en staging (del dump + la 14):**

```sql
CREATE TABLE festivos_colombia (
  fecha DATE PRIMARY KEY,
  nombre VARCHAR(100) NOT NULL
);
```

**Schema en `models.py`:**

```python
class FestivosColombia(Base):
    __tablename__ = "festivos_colombia"
    fecha: Mapped[date] = mapped_column(Date, primary_key=True)
    descripcion: Mapped[Optional[str]] = mapped_column(String(100))
```

Drift menor: el ORM nombra `descripcion` pero la tabla real usa `nombre`. Ninguno se usa desde el sprint Tutelas (solo necesitamos `SELECT fecha FROM festivos_colombia`). El helper `_obtener_festivos` del `sla_engine` usa asyncpg directo — inmune al drift del ORM.

## `PLAZOS_DIAS_HABILES` (config.py)

```python
PLAZOS_DIAS_HABILES = {
    "TUTELA": 2,
    "PETICION": 15, "QUEJA": 15, "RECLAMO": 15,
    "SOLICITUD": 10, "CONSULTA": 30, "FELICITACION": 5,
}
```

Coherente con `sla_regimen_config` GENERAL (aplica ignorando régimen). Sirve como default para fallback offline del `sla_engine`.

## `ANTHROPIC_MODEL_SONNET` — no existe en config

`config.py` solo define `anthropic_api_key`. **No hay** `ANTHROPIC_MODEL_SONNET`. El v3 lo cita como default `claude-sonnet-4-5-20250929`. Esto es para el Agente 3 (extractor), no el 2. Voy a agregarlo a config como parte del Agente 3 cuando lo use.

## `conftest.py` — mocks disponibles

```python
@pytest.fixture
def mock_db_connection():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value=None)
    return conn
```

Reutilizable para los tests de `sla_engine`, `capabilities`, `pipeline` cuando necesitan una `conn` simulada.

## Decisiones tomadas antes de escribir código

1. **`conn` vs `pool`**: los módulos nuevos del Agente 2 (`sla_engine`, `capabilities`, `pipeline`) reciben `conn: asyncpg.Connection` (sin pool). Para `db_inserter.insert_pqrs_caso` mantengo `pool` y agrego `metadata_especifica`/`fecha_vencimiento` como kwargs con default None (retrocompat).

2. **Timezone-aware datetimes**: el sprint opera todo en UTC. Los datetimes que no traen tz se asumen UTC (igual que `_parse_fecha` en db_inserter).

3. **Jornada hábil**: 08:00-12:00 + 13:00-17:00 UTC (8 horas hábiles por día; 8h = 1 día hábil).

4. **Fallback de festivos para tests (sin conn)**: al menos los festivos fijos 2026 que sabemos (1-ene, 1-may, 25-dic, etc.). Tests que no quieran conn real usan ese fallback.

5. **Extensibilidad del semáforo**: `SEMAFORO_CONFIG` como dict permite agregar otros tipos de caso en el futuro (SALUD, TELECOM, etc.) sin tocar el motor.

## Lo que NO se resuelve en este sprint

- Drift `correlation_id` en `pqrs_casos` (ya preexiste, requiere sprint separado).
- CHECK de 3 valores en el ORM vs 5 en la DB real (ORM desactualizado — baja prioridad).
- Drift `descripcion` vs `nombre` en `festivos_colombia` (trivial, no se usa).
- Endpoint `/health` del backend (DT-25).
- Kafka contenedor en staging (DT-26, se adapta en Agente 3 según tu instrucción de sesión 2).
