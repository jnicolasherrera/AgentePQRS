# C2 — Dimensionamiento de la migración a RLS real

**Fecha:** 2026-06-25 · Relevamiento técnico (sin tocar código) previo a la spec/plan.

## Conclusión ejecutiva
**C2 es MUCHO más chico de lo que parecía.** El andamiaje de RLS ya está construido (código + DB). No es "construir RLS desde cero", es **activarlo y cerrar huecos**. Riesgo principal: que queries que hoy "andan" gracias al bypass de superuser fallen al activar RLS.

## Lo que YA existe (no hay que hacer)
1. **Código ya inyecta el contexto RLS** — `backend/app/core/db.py:64-78`: `get_db_connection` setea en cada request `app.current_tenant_id`, `app.current_user_id`, `app.current_role`, `app.is_superuser` con `set_config`, y los limpia al final (83-87). Hay `execute_in_rls_context` para workers.
2. **El rol destino ya existe** — `pqrs_backend`: `rolsuper=f`, `rolbypassrls=f` (NO superuser, NO bypassa RLS). Es el rol ideal.
3. **`pqrs_backend` ya tiene GRANTs** — SELECT/INSERT/UPDATE/DELETE sobre las 20 tablas. Puede operar.
4. **10/20 tablas ya tienen RLS habilitado con policy** — y las policies usan EXACTAMENTE `current_setting('app.current_tenant_id')` + bypass por `app.is_superuser`, idéntico a lo que el código setea. **100% compatibles.**

Tablas CON RLS+policy (10): `ab_test_borradores`, `config_buzones`, `historico_email_cedula`, `pqrs_adjuntos`, `pqrs_casos`, `pqrs_comentarios`, `respuestas_kb`, `sla_regimen_config`, `user_capabilities`, `usuarios`.

## Lo que FALTA (el trabajo real de C2)
### Bloque DB
1. **Activar RLS + crear policy en las tablas multi-tenant que faltan (4):**
   - `audit_log_respuestas`, `borrador_feedback`, `kb_ingestion_log`, `pqrs_clasificacion_feedback`
   - (copiar el patrón de policy existente: `cliente_id = current_setting('app.current_tenant_id')::uuid OR is_superuser`)
2. **Decidir tablas NO-tenant (dejar sin RLS, correcto):** `aequitas_migrations(_lock)`, `festivos_colombia`, `pqrs_comentarios_bak_*` (borrar).
3. **Casos especiales a analizar:**
   - `clientes_tenant` (tabla de tenants): un usuario necesita leer SU propio tenant → policy especial (`id = current_tenant` no `cliente_id`).
   - `plantillas_respuesta`: ¿compartida global o por-tenant? Definir antes de poner policy.
   - `aequitas_worker` tiene `rolbypassrls=t` → los workers SIGUEN bypasseando. Decidir si está OK (workers confiables) o migrar también.

### Bloque código
4. **Cambiar `config.py:5`** `database_url` de `pqrs_admin` → `pqrs_backend` (vía env `.env`/compose de prod, NO hardcode). 1 línea efectiva.
5. **Verificar GRANTs de secuencias/funciones** que `pqrs_backend` pudiera necesitar (las tablas ya están; faltaría chequear sequences para los INSERT con serial/default).

### Bloque testing (lo más importante — donde está el riesgo)
6. **Auditar cada endpoint** que hoy depende del bypass: los que ya filtran a mano por `cliente_id` seguirán OK; los que NO filtraban (ej. el ex-bug C1 download_adjunto, A3/A4) ahora quedarán protegidos por RLS — pero hay que verificar que NO rompan funcionalidad legítima (super_admin, cross-tenant intencional como `clientes_tenant`).
7. **Probar los 4 roles** (super_admin, admin, abogado/analista, auditor) sobre los flujos clave: bandeja, detalle, envío, stats, plantillas.
8. **Workers:** confirmar que `master_worker` (usa `aequitas_worker`, que bypassa RLS) sigue funcionando — o si se migra, que setea el contexto.

## Riesgos
- **ALTO:** una query que el código NO filtra a mano y que hoy "anda" por el bypass → al activar RLS devuelve 0 filas (no error, datos vacíos). Difícil de detectar sin testing por rol. Esta es la causa típica de "se rompió el dashboard/listado" tras activar RLS.
- **MEDIO:** INSERTs que dependan de secuencias sin GRANT a `pqrs_backend`.
- **MEDIO:** `clientes_tenant` sin policy correcta → usuarios no pueden leer su propio tenant (login/`/auth/me` roto).
- **BAJO:** workers con `aequitas_worker` (bypass) no se ven afectados si no se tocan.

## Estrategia de deploy recomendada
1. **Staging primero** (hay un stack `pqrs_staging_*` en la misma máquina) — activar RLS ahí, testear por rol, antes de prod.
2. **Reversible:** el cambio de rol es 1 env var → revertir = volver a `pqrs_admin` + restart. Las policies nuevas se pueden `DROP`.
3. **Gradual posible:** activar RLS tabla por tabla no es trivial (el rol es global), pero se puede probar el rol `pqrs_backend` con las 10 tablas que YA tienen policy antes de agregar las 4 nuevas.

## Esfuerzo estimado
- DB (4 policies + casos especiales + grants): **chico-medio**, bien acotado.
- Código (1 env var): **trivial**.
- Testing por rol (lo serio): **medio-alto** — es el 70% del trabajo y del riesgo.
- **Veredicto:** es un proyecto de **1 sesión enfocada con spec/plan**, no una refactorización masiva. Ideal para el flujo SDD: la spec define el comportamiento esperado por rol/tabla, el plan desglosa policies + testing, la implementación va por Claude Code con validación en staging.
