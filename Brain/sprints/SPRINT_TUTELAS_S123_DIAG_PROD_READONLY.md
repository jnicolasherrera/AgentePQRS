# Diagnóstico read-only PROD — 18.228.54.9

**Fecha:** 2026-04-23
**Autorización:** Nico explícita (solo SELECT / information_schema / pg_*; cero INSERT/UPDATE/DELETE/ALTER/DROP).
**Host:** `flexpqr-prod` (EC2 18.228.54.9), container `pqrs_v2_db`, DB `pqrs_v2`, usuario `pqrs_admin`.
**Relacionado:** anomalía A1 documentada en `SPRINT_TUTELAS_S123_PROGRESS.md` (staging 15.229 es esqueleto).

Las queries completas viven en `/tmp/prod_diag_readonly.sql` y `/tmp/prod_diag_readonly_2.sql` (en la máquina del agente). Este doc solo contiene los resultados relevantes para la decisión.

---

## 1. Inventario de tablas (9 tablas, vs 5 en staging 15.229)

```
audit_log_respuestas
clientes_tenant
config_buzones
plantillas_respuesta
pqrs_adjuntos
pqrs_casos
pqrs_clasificacion_feedback
pqrs_comentarios
usuarios
```

No existen `festivos_colombia` ni `sla_regimen_config`.

## 2. Columnas de `pqrs_casos` (30 columnas — schema maduro productivo)

Todas las columnas centrales del sistema PQRS están presentes:

- Identidad / routing: `id, cliente_id, email_origen, external_msg_id, asunto, cuerpo`.
- Estado y SLA: `estado, nivel_prioridad, fecha_recibido (NOT NULL), fecha_vencimiento, tipo_caso, created_at, updated_at`.
- Asignación: `asignado_a, fecha_asignacion`.
- Alertas: `alerta_2h_enviada`.
- Borrador y respuesta: `borrador_respuesta, borrador_estado ('SIN_PLANTILLA' default), problematica_detectada, plantilla_id, aprobado_por, aprobado_at, enviado_at, acuse_enviado, texto_respuesta_final, borrador_ia_original, edit_ratio`.
- Radicado: `numero_radicado`.
- Clasificación: `es_pqrs`.
- Adjuntos: `reply_adjunto_ids (uuid[])`.

**Nota:** NO hay columnas nuevas que la 14 sectorial podría haber agregado sobre esta tabla (la 14 toca clientes_tenant, no pqrs_casos — pero sí habría agregado el trigger que aquí no está).

## 3. Objetos de la migración 14 sectorial — estado en prod

| Objeto | ¿Existe en prod? |
|---|---|
| tabla `festivos_colombia` | **NO** |
| tabla `sla_regimen_config` | **NO** |
| columna `clientes_tenant.regimen_sla` | **NO** |
| función `calcular_fecha_vencimiento(...)` | **NO** (0 rows en `pg_proc`) |
| trigger `tg_set_fecha_vencimiento` en `pqrs_casos` | **NO** (solo existe `trg_casos_updated_at → update_updated_at()`) |

**Veredicto inequívoco:** la migración 14 nunca corrió contra `pqrs_v2` en prod 18.228. El Brain decía "Staging 18.228.54.9 APLICADO 8-abril" — eso es falso (además 18.228 es prod, no staging).

## 4. Triggers activos en `pqrs_casos`

```
trigger_name         | event     | action
trg_casos_updated_at | UPDATE    | EXECUTE FUNCTION update_updated_at()
```

Un único trigger de housekeeping. No hay triggers de SLA.

## 5. Funciones tipo SLA / vencimiento / festivo

```
proname    | args
translate  | text, text, text   ← builtin de PostgreSQL, no relevante
```

No existe ninguna función custom de SLA.

## 6. Tabla de control de migraciones

| Tabla | ¿Existe? |
|---|---|
| `aequitas_migrations` | NO |
| `schema_migrations` | NO |
| `migrations` | NO |

**Implicación:** prod no tiene rastro formal de qué migración se aplicó. El registro histórico está solo en memoria humana y commits.

## 7. Tenants existentes (3 reales, con datos productivos)

| ID | Nombre | Casos | Notas |
|---|---|---|---|
| `effca814-b0b5-4329-96be-186c0333ad4b` | Abogados Recovery | 135 | ARC — tenant productivo crítico |
| `f7e8d9c0-b1a2-3456-7890-123456abcdef` | FlexFintech | 407 | Productivo |
| `11111111-1111-1111-1111-111111111111` | Demo FlexPQR | 20 | Demo |

**Ninguno tiene `regimen_sla`** (la columna no existe).

## 8. Usuarios por rol (19 totales, producción real)

| Rol | Cantidad |
|---|---|
| abogado | 7 |
| analista | 5 |
| admin | 5 |
| super_admin | 1 |
| coordinador | 1 |

## 9. Totales de salud

| Entidad | Filas |
|---|---|
| pqrs_casos | 562 |
| usuarios | 19 |
| clientes_tenant | 3 |

## 10. Índices en `pqrs_casos` (9 índices bien diseñados)

Destaca `idx_pqrs_tutela_alerta` que ya filtra por `tipo_caso='TUTELA' AND alerta_2h_enviada=false` — el sistema ya está preparado para tutelas a nivel de índice, aunque falte la lógica de motor.

Otros: `idx_casos_asignado`, `idx_casos_dedup_natural` (UNIQUE por cliente+email+hora), `idx_casos_external_msg` (UNIQUE por cliente+external_msg_id), `idx_pqrs_borrador_estado`, `idx_pqrs_cliente_id`, `idx_pqrs_estado`, `idx_pqrs_radicado`.

## 11. RLS en `pqrs_casos`

Existe policy `tenant_isolation_pqrs_policy` (polcmd=`*`, aplica a todas las operaciones) que filtra por `current_setting('app.current_tenant_id')` AND NOT `app.is_superuser=true`. Multi-tenancy activo por RLS.

## 12. Extensiones instaladas

`pgcrypto 1.3`, `plpgsql 1.0`, `uuid-ossp 1.1`. Esperado.

## 13. Tamaños (datos productivos reales)

| Tabla | Tamaño |
|---|---|
| pqrs_comentarios | 286 MB |
| pqrs_casos | 10 MB |
| audit_log_respuestas | 416 kB |
| pqrs_adjuntos | 320 kB |
| usuarios | 96 kB |
| plantillas_respuesta | 80 kB |
| clientes_tenant | 48 kB |
| config_buzones | 32 kB |
| pqrs_clasificacion_feedback | 24 kB |

Todos los objetos son del owner `pqrs_admin` (correcto).

---

## Conclusiones del diagnóstico de prod

1. **Prod tiene schema completo y maduro.** 9 tablas, 30 columnas correctas en `pqrs_casos`, RLS activo, índices optimizados (incluso preparados para tutelas).
2. **Prod tiene datos productivos reales.** 562 casos, 3 tenants (FlexFintech 407, ARC 135, Demo 20), 19 usuarios con roles distribuidos.
3. **La migración 14 sectorial NO está aplicada en prod.** Ni la tabla `festivos_colombia`, ni `sla_regimen_config`, ni la columna `regimen_sla`, ni el SP `calcular_fecha_vencimiento`, ni el trigger asociado.
4. **El Brain tenía mal documentado el deploy de la 14.** La línea "Staging 18.228.54.9 APLICADO 8-abril" en `SPRINT_SLA_SECTORIAL.md` (y replicada en `DEUDAS_PENDIENTES.md` como nota de inconsistencia) es falsa en doble sentido: 18.228 es **prod**, no staging, **y** la migración no corrió ahí.
5. **No hay tabla de control de migraciones.** Se navega por convención, no por registro.
6. **El staging pobre (15.229) nunca fue clon de prod.** El schema de prod es completamente distinto.

Ningún comando destructivo fue ejecutado contra prod. Todo fue `SELECT` / `information_schema` / `pg_*`.
