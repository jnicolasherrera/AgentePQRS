# Agente 1 — Diagnóstico obligatorio (paso 1)

**Fecha:** 2026-04-23
**Host:** `flexpqr-staging` (15.229.114.148), `pqrs_v2_db`, `pqrs_v2`.
**Estado previo:** staging reconstruido con baseline prod + 14 + seed (commit `100b6de`). aequitas_migrations = 3 filas.

Este doc responde el paso 1 del Agente 1 y lista los gaps entre el spec del sprint v3 + la spec del trigger híbrido de Nico y el schema real. Sin resolverlos, las migraciones 18 y 19 no se pueden escribir tal cual están diseñadas.

## 1. Estado del schema actual (pqrs_casos, 30 columnas)

Columnas que **existen** — relevantes para el sprint:

| Columna | Tipo | Nullable | Default |
|---|---|---|---|
| `fecha_recibido` | timestamptz | **NO** | — |
| `created_at` | timestamptz | YES | CURRENT_TIMESTAMP |
| `fecha_vencimiento` | timestamptz | YES | — |
| `tipo_caso` | varchar(100) | YES | — |
| `numero_radicado` | varchar(30) | YES | — |
| `alerta_2h_enviada` | boolean | YES | false |
| `asignado_a` | uuid | YES | — |
| `fecha_asignacion` | timestamptz | YES | — |

Columnas que **no existen** (hay que crearlas en 18 o 19):

| Columna esperada | Dónde aparece en specs |
|---|---|
| `semaforo_sla` | Migración 18 (CHECK constraint lo asume) |
| `fecha_creacion` | Trigger híbrido de Nico (`NEW.fecha_creacion`) |
| `metadata_especifica` | Migración 19 |
| `tutela_informe_rendido_at` | Migración 19 |
| `tutela_fallo_sentido` | Migración 19 |
| `tutela_riesgo_desacato` | Migración 19 |
| `documento_peticionante_hash` | Migración 19 |

En `clientes_tenant`:
- `config_hash_salt` — **no existe**. Migración 19 lo crea + seedea 32 bytes hex por tenant.

## 2. CHECK constraints sobre `pqrs_casos`

**Ninguno.** La tabla no tiene ningún CHECK. La migración 18 hace `DROP CONSTRAINT IF EXISTS pqrs_casos_semaforo_sla_check` (OK, ese nombre no existe) y luego `ADD CONSTRAINT ... CHECK (semaforo_sla IN (...))`.

## 3. Policies RLS

Solo existe `tenant_isolation_pqrs_policy` (polcmd=*, permissive). El sprint v3 no modifica esa policy; sí agrega una nueva en `user_capabilities` (migración 20).

## 4. Tabla `user_capabilities`

**No existe.** Se crea en la migración 20.

## 5. Función `fn_set_fecha_vencimiento` — definición actual

```sql
CREATE OR REPLACE FUNCTION public.fn_set_fecha_vencimiento()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF NEW.tipo_caso IS NOT NULL AND NEW.fecha_recibido IS NOT NULL THEN
    NEW.fecha_vencimiento := calcular_fecha_vencimiento(
      NEW.fecha_recibido,
      NEW.cliente_id,
      NEW.tipo_caso
    );
  END IF;
  RETURN NEW;
END;
$function$
```

Esta versión usa `NEW.fecha_recibido` (columna que sí existe y es NOT NULL).

## 6. Función `calcular_fecha_vencimiento` — firma actual

```
calcular_fecha_vencimiento(fecha_inicio timestamptz, tenant_id uuid, p_tipo_caso varchar) → timestamptz
```

STABLE. Lógica: lee `clientes_tenant.regimen_sla`, lee `sla_regimen_config(regimen, tipo_caso)`, cuenta días hábiles saltando fines de semana y `festivos_colombia`. Fallback a GENERAL y 15 días si no encuentra config.

## 7. Distribución de casos por tipo (bajo `app.is_superuser=true`)

| tipo_caso | count |
|---|---|
| PETICION | 5 |
| QUEJA | 5 |
| RECLAMO | 5 |
| SUGERENCIA | 5 |
| TUTELA | 5 |

Todos con marker `FIXTURE_V1_*`. Ninguno es dato real.

## 8. Triggers actuales sobre `pqrs_casos`

| trigger | evento | función |
|---|---|---|
| `trg_casos_updated_at` | UPDATE | `update_updated_at()` |
| `tg_set_fecha_vencimiento` | INSERT | `fn_set_fecha_vencimiento()` |

## 9. Materialized view `tutelas_view`

**No existe.** Se crea en migración 21.

---

## Gaps a resolver antes de escribir 18/19

### Gap A — Columna `semaforo_sla` no existe, pero la migración 18 pide un CHECK sobre ella

**Propuesta:** la 18 debe primero `ALTER TABLE pqrs_casos ADD COLUMN IF NOT EXISTS semaforo_sla VARCHAR(20) DEFAULT 'VERDE'`, y **después** aplicar el CHECK. Orden final dentro de la 18:

```sql
ALTER TABLE pqrs_casos ADD COLUMN IF NOT EXISTS semaforo_sla VARCHAR(20) DEFAULT 'VERDE';
ALTER TABLE pqrs_casos DROP CONSTRAINT IF EXISTS pqrs_casos_semaforo_sla_check;
ALTER TABLE pqrs_casos
    ADD CONSTRAINT pqrs_casos_semaforo_sla_check
    CHECK (semaforo_sla IN ('VERDE', 'AMARILLO', 'NARANJA', 'ROJO', 'NEGRO'));
```

Alternativa: migración nueva `17_add_semaforo_sla.sql` antes de la 18. Menos cohesión.

**Decisión requerida.**

### Gap B — Trigger híbrido referencia `NEW.fecha_creacion`, que no existe

El trigger que propusiste dice:

```sql
NEW.fecha_vencimiento := NEW.fecha_creacion + (v_plazo_horas || ' hours')::INTERVAL;
...
NEW.fecha_vencimiento := calcular_fecha_vencimiento(
    NEW.fecha_creacion, NEW.cliente_id, NEW.tipo_caso
);
```

La columna no existe en pqrs_casos. Dos candidatas:

- `fecha_recibido` (NOT NULL, semánticamente es *cuando la entidad recibió el PQRS* — disparador natural del SLA). Es la que el trigger actual ya usa.
- `created_at` (NULLABLE con default CURRENT_TIMESTAMP, es *cuando la fila entró a la DB* — puede ser ≫ fecha_recibido si hay rezagos de ingest).

**Propuesta:** reemplazar los 2 `NEW.fecha_creacion` por `NEW.fecha_recibido`. Razones:
1. Es lo que el trigger actual ya usa — cambiar el criterio de inicio del SLA sería un cambio semántico no deseado y no documentado.
2. Es NOT NULL (defensivo: no hace falta branch por null).
3. Semánticamente: "plazo_informe_horas desde cuándo" es una decisión que debe anclarse al hecho jurídico (recepción), no al hecho técnico (insert).

**Decisión requerida.**

### Gap C — Impacto en TESTS A/B/C/D del paso 8

Tus 4 tests asumen que se pueden hacer INSERTs sin `fecha_recibido` (porque hablan de "INSERT sin fecha_vencimiento ni metadata"). Pero `fecha_recibido` es NOT NULL. Los tests tienen que proveer una `fecha_recibido` aunque el foco del test sea `fecha_vencimiento` y `metadata_especifica`.

**Propuesta:** en los 4 tests, fijar `fecha_recibido = '2026-04-23 10:00:00+00'` como constante conocida. Los cálculos esperados se derivan de esa base. No es un cambio de spec — es una aclaración operativa.

### Gap D — TEST A: tenant específico

El TEST A dice "fecha_vencimiento debe ser la que el SP calcularía para GENERAL QUEJA (15 días hábiles)". Pero el régimen depende del tenant que use el INSERT. En staging tenemos:
- ARC (FINANCIERO) → QUEJA = 8 días hábiles
- Demo (GENERAL) → QUEJA = 15 días hábiles

**Propuesta:** TEST A usa tenant `00000000-0002-0002-0002-000000000002` (Demo GENERAL) para que el resultado esperado sea 15 días hábiles como decís.

**Decisión requerida.**

---

## Qué se puede escribir sin decisiones nuevas

- Migración 20 (`user_capabilities`) — no depende de los gaps A/B.
- Migración 21 (`tutelas_view`) — depende de `metadata_especifica` (creada en 19), pero no de A/B directamente.
- Migración 19 parte 1 (ADD COLUMN metadata_especifica + columnas tutela + documento_peticionante_hash + config_hash_salt + índices GIN) — no depende de A/B.
- Migración 19 parte 2 (el trigger) — **depende de Gap B**.
- Migración 18 — **depende de Gap A**.

## Qué NO hice

- No escribí ninguna de las 4 migraciones.
- No toqué el trigger actual.
- No apliqué nada a staging.
- No empecé el paso 2 del Agente 1.
