# C2 — Validación en STAGING exitosa (2026-06-25)

## Preparación de staging (estaba roto/desalineado)
Staging tenía un esquema MUY viejo: 10 tablas (vs 19 prod), `pqrs_casos` con 16 columnas (vs 41), trigger `fn_set_fecha_vencimiento` referenciando `tipo_caso` inexistente → cualquier INSERT de caso fallaba. Le faltaban 3 de las 5 tablas de C2.

**Cómo se alineó:**
1. Backup completo de staging → `/home/ubuntu/staging_full_backup_20260625.sql` (staging estaba casi vacío: 1 tenant, 0 casos, sin datos valiosos).
2. Creados roles `pqrs_backend` (NOSUPERUSER NOBYPASSRLS) y `aequitas_worker` en staging.
3. `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` + aplicar el dump de esquema de prod (`schema_pre_c2_20260625.sql`). Resultado: 19 tablas, `pqrs_casos` con 41 cols, triggers consistentes.
   - **Único error esperado e irrelevante para C2:** extensión `vector` (pgvector) no instalada en staging → `respuestas_kb` no se creó. NO afecta a C2 (esa tabla no es de las 5).
4. Re-aplicados GRANTs a `pqrs_backend`/`aequitas_worker` (el DROP SCHEMA los borró): CRUD sobre 19 tablas + USAGE en secuencias + ALTER DEFAULT PRIVILEGES.
5. Seed de 2 tenants (A `1111...`, B `2222...`) con datos en las 5 tablas de C2 + casos/usuarios.
   - Gotchas del seed: `pqrs_casos` necesita `tipo_caso` (trigger); `pqrs_clasificacion_feedback` necesita `caso_id`; `kb_ingestion_log` necesita `source_type/documentos/status`, y `status` ∈ {ok,partial,error} (minúscula).

## Resultado de la validación (pqrs_backend, contexto Tenant A)

| Tabla | ANTES (visible/de_B) | DESPUÉS | super_admin |
|---|---|---|---|
| borrador_feedback | 2 / 1 FUGA | 1 / 0 ✅ | ve 2 ✅ |
| pqrs_clasificacion_feedback | 2 / 1 FUGA | 1 / 0 ✅ | ve 2 ✅ |
| plantillas_respuesta | 2 / 1 FUGA | 1 / 0 ✅ | ve 2 ✅ |
| kb_ingestion_log | 2 / 1 FUGA | 1 / 0 ✅ | ve 2 ✅ |
| audit_log_respuestas | 2 / 0 | 1 / 0 ✅ | ve 2 ✅ |

- **Fugas cerradas:** tenant A ya NO ve datos de B en ninguna tabla.
- **Acceso legítimo intacto:** A sigue viendo su propia plantilla (control = 1).
- **super_admin (is_superuser=true) ve ambos tenants** en las 5 tablas → bypass OK.

## Conclusión
Las 5 policies (`docs/superpowers/plans/c2_policies.sql`) están **probadas y validadas** en un staging que ahora es espejo fiel de prod. Listas para deploy a prod con el mismo SQL. El patrón (directa por `cliente_id` + JOIN para `audit_log_respuestas` + bypass `is_superuser`) funciona y no rompe acceso legítimo.

## Pendiente para prod (Fase 2)
1. Aplicar `c2_policies.sql` en prod (`pqrs_v2`).
2. Validar con el mismo método (medir fuga antes/después con `pqrs_backend` y datos reales de Recovery/FlexFintech).
3. Documentar en informe maestro: C2 cerrado.
4. (Recordar) RLS ya estaba activo en prod — ver `C2_HALLAZGO_rls_ya_activo.md`.
