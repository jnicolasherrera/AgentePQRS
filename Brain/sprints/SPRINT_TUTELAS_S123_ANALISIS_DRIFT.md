# Análisis de drift — Staging 15.229 vs Prod 18.228 vs Brain documentado

**Fecha:** 2026-04-23
**Fuentes:**
- Staging 15.229.114.148 → `SPRINT_TUTELAS_S123_PROGRESS.md` sección "Gate 0.5 Sub-A: Diagnóstico D3".
- Prod 18.228.54.9 → `SPRINT_TUTELAS_S123_DIAG_PROD_READONLY.md` (este sprint, sesión 2026-04-23).
- Brain documentado → `SPRINT_SLA_SECTORIAL.md` + `DEUDAS_PENDIENTES.md`.

## Leyenda de veredictos

- **match** → los tres coinciden.
- **drift-doc** → Brain documenta algo distinto de lo que realmente existe (documento desalineado con la realidad).
- **drift-env** → staging y prod difieren entre sí de forma significativa.
- **unknown** → no hay información suficiente en alguna de las 3 columnas.

---

## Tabla comparativa

### Inventario / schema base

| Objeto | Staging 15.229 | Prod 18.228 | Brain documentado | Veredicto |
|---|---|---|---|---|
| # tablas `public` | 5 | 9 | Implícito: schema prod completo (sin conteo exacto) | **drift-env** (staging es esqueleto) |
| Tablas base (`audit_log_respuestas`, `config_buzones`, `plantillas_respuesta`, `pqrs_adjuntos`, `pqrs_clasificacion_feedback`, `pqrs_comentarios`) | NO existen | Existen | Asume que existen en ambos ambientes | **drift-env** |
| Tablas presentes en ambos (`clientes_tenant`, `pqrs_casos`, `usuarios`) | Existen | Existen | Asume existencia | **match** |
| Columnas de `pqrs_casos` | Esqueleto: sin `tipo_caso`, `fecha_vencimiento`, `fecha_creacion`, `semaforo_sla`, `numero_radicado`, `fecha_respuesta` | 30 columnas: `tipo_caso`, `fecha_vencimiento`, `numero_radicado`, `borrador_*`, etc. presentes | Asume schema prod maduro | **drift-env** (staging está roto estructuralmente) |
| Tabla de control de migraciones (`aequitas_migrations` / `schema_migrations`) | Inferido: no existe (migrate.sh aún no existe tampoco) | NO existe | `SPRINT_TUTELAS_PIPELINE_PROMPT.md` v3 pide crearla (Gate 0.5 Sub-B) | **match** (coincide: hay que crearla) |

### Migración 14 sectorial (objetos creados)

| Objeto | Staging 15.229 | Prod 18.228 | Brain documentado | Veredicto |
|---|---|---|---|---|
| tabla `festivos_colombia` | Existe, 22 filas | **NO existe** | `SPRINT_SLA_SECTORIAL.md` dice: "Staging 18.228.54.9 APLICADO 8-abril" y "Staging 15.229 APLICADO 8-abril"; `DEUDAS_PENDIENTES.md` dice "nunca corrió en prod" y flagea inconsistencia | **drift-doc** serio (Brain se contradice; la verdad es: aplicado solo en 15.229, NO en prod) |
| tabla `sla_regimen_config` | Existe, 24 filas | **NO existe** | Mismo que arriba | **drift-doc** serio |
| columna `clientes_tenant.regimen_sla` | Existe, default `'GENERAL'`, NOT NULL | **NO existe** | Mismo que arriba | **drift-doc** serio |
| función `calcular_fecha_vencimiento(timestamptz, uuid, varchar)` | Existe | **NO existe** (0 rows en `pg_proc`) | Documentada como "actualizada en ambos stagings" | **drift-doc** serio |
| trigger `tg_set_fecha_vencimiento` en `pqrs_casos` | Existe (pero apunta a función que referencia columnas inexistentes de la tabla — roto en runtime) | **NO existe** (solo `trg_casos_updated_at`) | Documentado como "actualizado en ambos stagings" | **drift-doc** + **drift-env** (doc miente; staging lo tiene roto; prod no lo tiene) |

### Tenants / datos productivos

| Objeto | Staging 15.229 | Prod 18.228 | Brain documentado | Veredicto |
|---|---|---|---|---|
| Cantidad de tenants | 1 (dummy "Organizacion Default V2" `a1b2c3d4-...`) | 3 (FlexFintech `f7e8...`, ARC `effca814-...`, Demo `11111111-...`) | Brain asume presencia de ARC (`effca814-...`) y FlexFintech productivos | **drift-env** grave (staging no tiene ARC) |
| Casos totales (`pqrs_casos`) | 0 (tabla sin columnas; el conteo ni siquiera se pudo hacer) | 562 | Brain asume prod con datos históricos | **drift-env** |
| Tenant ARC presente | NO | SÍ (135 casos) | Brain asume ARC en prod | **match** prod↔Brain; **drift-env** staging↔prod |

### Usuarios / roles

| Objeto | Staging 15.229 | Prod 18.228 | Brain documentado | Veredicto |
|---|---|---|---|---|
| Total usuarios | 1 | 19 | Brain asume usuarios reales productivos | **drift-env** |
| Roles distintos | 1 (solo `admin`) | 5 (`abogado 7`, `analista 5`, `admin 5`, `super_admin 1`, `coordinador 1`) | Sprint Tutelas v3 asume existencia de rol `abogado_tutelas` (user_capabilities). Los roles base existen en prod | **drift-env** (staging no tiene el reparto); **match** prod↔Brain para roles base |

### RLS / multi-tenancy

| Objeto | Staging 15.229 | Prod 18.228 | Brain documentado | Veredicto |
|---|---|---|---|---|
| Policy RLS en `pqrs_casos` | No verificado en diagnóstico staging (tabla sin columnas hace RLS irrelevante) | `tenant_isolation_pqrs_policy` activo (filtra por `app.current_tenant_id` + bypass `app.is_superuser`) | Brain asume RLS activo en prod; Sprint v3 pide extender con `abogado_tutelas` | **match** prod↔Brain; **unknown** staging (probablemente sin policy útil) |

### Índices / preparación para tutelas

| Objeto | Staging 15.229 | Prod 18.228 | Brain documentado | Veredicto |
|---|---|---|---|---|
| `idx_pqrs_tutela_alerta` (por `tipo_caso='TUTELA'`) | Inferido: no existe (tabla sin `tipo_caso`) | Existe | No documentado explícitamente, pero es pre-requisito implícito del Sprint Tutelas | **drift-env** |

### Deploy de la 14 documentado vs realidad

| Afirmación del Brain | Realidad observada | Veredicto |
|---|---|---|
| "Staging 18.228.54.9 — APLICADO 8 abril 2026" (SPRINT_SLA_SECTORIAL.md tabla de estado de deploy) | 18.228 es **prod**, y la 14 **NO** está aplicada ahí | **drift-doc** grave |
| "Staging 15.229.114.148 — APLICADO 8 abril 2026" | La 14 SÍ está aplicada en 15.229 | **match** (la nota sobre staging 15.229 es correcta) |
| "Producción — PENDIENTE, Requiere aprobación" | Consistente con realidad (14 no está en prod) | **match** |
| DEUDAS_PENDIENTES: "La migración 14 nunca corrió contra la DB de producción `pqrs_v2`" | Confirmado en este diagnóstico | **match** |
| DEUDAS_PENDIENTES nota 16-abril: "o el doc tiene typo, o se aplicó a prod y la deuda está mal descrita" | Resuelto: el doc tiene un error de etiqueta (llamó "Staging 18.228" a prod) + la 14 nunca corrió ahí | **drift-doc** resuelto hoy |

---

## Síntesis

### Qué dice la evidencia

1. **Prod 18.228 ↔ Brain documentado:** casi totalmente coherente para el schema base (tablas, columnas, RLS, índices, tenants, usuarios). El único drift real es la etiqueta errónea en `SPRINT_SLA_SECTORIAL.md` que llama "Staging" al host productivo.

2. **Staging 15.229 ↔ Brain documentado:** drift severo. Lo que el Brain asume como "staging (~ prod)" no es cierto: 15.229 es un ambiente esqueleto de 5 tablas con tablas base ausentes y `pqrs_casos` sin columnas centrales. La única parte de 15.229 que coincide con el Brain es que la 14 sí se aplicó ahí el 8-abril (pero sobre un schema roto, así que el trigger quedó apuntando a columnas inexistentes).

3. **Migración 14 en prod:** **NO aplicada.** Evidencia directa: `to_regclass('festivos_colombia') = f`, `to_regclass('sla_regimen_config') = f`, columna `regimen_sla` ausente, SP y trigger ausentes. Esto cierra la duda documental que llevaba abierta desde 16-abril.

4. **Tabla de control de migraciones:** no existe en prod. No hay forma automatizada de reproducir la lista de migraciones aplicadas. Solo existe el registro humano + git log.

### Escenarios evaluables (del prompt original)

- **ALFA** — "Prod con schema completo + 14 aplicada + ARC activo": **descartado** (14 NO está aplicada en prod).
- **BETA** — "Prod con schema completo pero 14 NO aplicada": **coincide con la evidencia.** Schema completo ✓, ARC presente ✓, 14 ausente ✓. El Brain mezcló hosts al documentar "aplicado staging 18.228" — en realidad ese 18.228 es prod y la 14 jamás corrió ahí.
- **GAMMA** — "Drift serio más allá de la 14 en prod": **descartado.** No se encontraron tablas desconocidas, owners raros, ni extensiones sospechosas. Todos los objetos tienen owner `pqrs_admin`, las 3 extensiones son las estándares, los tenants son los 3 esperados (FlexFintech, ARC, Demo).
- **DELTA** — "Prod también inconsistente": **descartado.** Prod está sano y coherente, es staging el que está en estado esqueleto.

**Escenario identificado: BETA.**

---

## Evidencia clave que soporta BETA

Tomado directamente del diagnóstico de prod (sección 3):

```
to_regclass('festivos_colombia')   → f
to_regclass('sla_regimen_config')  → f
clientes_tenant.regimen_sla        → existe = f
calcular_fecha_vencimiento (oid)   → 0 rows
trigger tg_set_fecha_vencimiento   → ausente (solo existe trg_casos_updated_at)
```

Y el schema prod es claramente productivo y maduro:
- 9 tablas (incluye `audit_log_respuestas`, `pqrs_adjuntos`, `pqrs_comentarios` con 286 MB).
- `pqrs_casos` con 30 columnas, incluyendo las claves para tutelas (`tipo_caso`, `fecha_vencimiento`, `numero_radicado`, `alerta_2h_enviada`).
- 3 tenants reales (FlexFintech 407 casos, ARC 135 casos, Demo 20 casos).
- 19 usuarios con roles bien distribuidos (7 abogados, 5 analistas, 5 admin, 1 super_admin, 1 coordinador).
- RLS `tenant_isolation_pqrs_policy` activo.
- Índice `idx_pqrs_tutela_alerta` ya creado (sistema preparado para tutelas a nivel de índice).
