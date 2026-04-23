# Baseline PROD Schema — pg_dump schema-only

**Fecha / hora del dump:** 2026-04-23 16:00 UTC
**Autorizado por:** Nico (conversación del sprint Tutelas S1+S2+S3, decisión post-bloqueante).
**Motivo:** cerrar el drift repo ↔ prod documentado en `SPRINT_TUTELAS_S123_BLOQUEANTE_DRIFT_REPO.md` y dar baseline reproducible para la FASE C' de reconstrucción de staging.

## Garantía de no-PII

`pg_dump --schema-only --no-owner --no-acl` **no exporta datos**. No se ejecutó ningún `COPY`, `INSERT`, ni `--data-only`. El archivo contiene únicamente definiciones DDL (tablas, columnas, índices, funciones, triggers, políticas RLS, extensiones).

Verificación posterior al dump:
- `grep -c '^INSERT INTO'` → **0**
- `grep -c '^COPY '` → **0**
- Los 4 hits de `token|secret|password` corresponden a **nombres de columna** (`azure_client_secret`, `zoho_refresh_token`, `password_hash`, `debe_cambiar_password`), no a valores — porque los valores viven en filas que el dump no exporta.

## Comando exacto ejecutado

```
ssh flexpqr-prod "docker exec pqrs_v2_db pg_dump -U pqrs_admin --schema-only --no-owner --no-acl pqrs_v2" > /tmp/prod_schema_20260423_1600.sql
```

Luego se copió a `/mnt/f/proyectos/AgentePQRS/migrations/baseline/prod_schema_20260423_1600.sql`.

## Integridad del archivo

| Campo | Valor |
|---|---|
| Ruta | `migrations/baseline/prod_schema_20260423_1600.sql` |
| Bytes | 18,787 |
| Líneas | 631 |
| SHA256 | `3d0bc89fd69b35819842f3e0db9eacf587cc4935cfce9bf031af339a17c14044` |
| MD5 | `751bccf162946d1285b0a7357b9447f0` |

## Inventario de objetos en el baseline

| Tipo | Cantidad |
|---|---|
| `CREATE EXTENSION` | 2 (`pgcrypto`, `uuid-ossp`) |
| `CREATE TABLE` | 9 |
| `CREATE INDEX` | 15 |
| `CREATE FUNCTION` | 1 |
| `CREATE TRIGGER` | 1 |
| `CREATE POLICY` | 5 |
| `ALTER TABLE` | 33 |

### Tablas

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

### Funciones y triggers

- `public.update_updated_at()` → trigger `trg_casos_updated_at BEFORE UPDATE ON pqrs_casos`.

### Políticas RLS

```
tenant_isolation_usuarios_policy
tenant_isolation_pqrs_policy
tenant_isolation_adjuntos_policy
tenant_isolation_comentarios_policy
tenant_isolation_config_policy
```

### `pqrs_casos` — confirmación de las 30 columnas

Todas las columnas del diagnóstico de prod están presentes:

```
id, cliente_id, email_origen, asunto, cuerpo, estado, nivel_prioridad,
fecha_recibido, created_at, fecha_vencimiento, tipo_caso, external_msg_id,
asignado_a, fecha_asignacion, updated_at, alerta_2h_enviada,
borrador_respuesta, borrador_estado, problematica_detectada, plantilla_id,
aprobado_por, aprobado_at, enviado_at, acuse_enviado, numero_radicado,
es_pqrs, reply_adjunto_ids, texto_respuesta_final, borrador_ia_original,
edit_ratio
```

Notar que **`semaforo_sla` NO aparece** en el baseline (confirmación del bloqueante previo: la columna nunca existió en prod y la 14 la referencia erróneamente). Esto hay que resolverlo en FASE B' antes de aplicar la 14 al staging reconstruido.

## Uso como piedra angular DT-19

Este dump sirve como baseline para comparaciones futuras de drift entre ambientes:

```
diff <(pg_dump --schema-only staging) <(pg_dump --schema-only prod)
```

Propuesta (a concretar en DT-19): cron semestral que compara dump de prod vs repo vs staging y alerta drifts detectados.

## Qué NO está en el baseline

Lo que no aparece en este dump es importante para saber qué hay que suplir en FASE B':

- Los **datos seed** de `sla_regimen_config` (24 filas) y `festivos_colombia` (22 filas) que la 14 introduce — no están porque schema-only no los exporta, pero tampoco están en prod (la 14 nunca corrió ahí).
- Cualquier tenant, usuario, caso, plantilla, adjunto, comentario.
- Los secretos productivos de Zoho/Azure de la 05.
- Las credenciales de `password_hash` de cualquier usuario.
