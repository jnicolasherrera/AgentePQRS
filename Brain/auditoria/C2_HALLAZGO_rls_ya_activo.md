# C2 — HALLAZGO durante ejecución: RLS YA está activo en prod (reconciliación)

**Fecha:** 2026-06-25 (Fase 1 de ejecución del plan C2)

## Qué descubrí
Al arrancar la Fase 1, verifiqué con qué rol corre realmente el backend de prod:
- **El backend de prod YA se conecta como `pqrs_backend`** (`rolbypassrls=false`), NO como `pqrs_admin`.
- La env var `DATABASE_URL` del contenedor `pqrs_v2_backend` apunta a `pqrs_backend`; pydantic la prioriza sobre el default `pqrs_admin` de `config.py:5`.
- **RLS YA ESTÁ ACTIVO Y FILTRANDO**: como `pqrs_backend` sin contexto → `pqrs_casos` da 0 filas; con contexto de tenant → filtra correctamente (FF=848 casos).

## Reconciliación con la auditoría
La auditoría (hallazgo C2) leyó `config.py` y asumió que el backend corría como `pqrs_admin` (BYPASSRLS). **Era incorrecto para el estado DESPLEGADO**: el env de prod ya sobreescribe a `pqrs_backend`. La premisa central de C2 ("el backend bypassa RLS") **ya estaba resuelta en prod**.

## Impacto sobre C1 (fuga de adjuntos)
- El "fix" C1 (`download_adjunto` con filtro `cliente_id`) **sigue siendo válido como defensa en profundidad**, pero **la fuga NO era explotable en prod**: RLS sobre `pqrs_adjuntos` (relrowsecurity + relforcerowsecurity) ya bloqueaba el acceso cross-tenant a través del backend real.
- La "fuga" que se demostró al validar C1 fue un **artefacto de testear con `psql -U pqrs_admin`** (superuser que bypassa RLS), no el rol del backend. **Lección: validar seguridad multi-tenant SIEMPRE con `pqrs_backend`, nunca con `pqrs_admin`.**

## Qué queda REALMENTE pendiente de C2 (medido con pqrs_backend, fugas reales)
De las tablas sin policy, probadas desde contexto de un tenant (Recovery):
- 🔴 `borrador_feedback` — FUGA: ve 173 filas de otros tenants.
- 🔴 `pqrs_clasificacion_feedback` — FUGA: ve 193 de otros.
- 🔴 `plantillas_respuesta` — FUGA: ve 54 de otros (62 totales).
- ⚠️ `audit_log_respuestas` — sin policy: un SELECT directo ve las 3203 filas de todos (necesita policy por JOIN a `pqrs_casos`).
- ✅ `kb_ingestion_log` — sin policy pero hoy no fuga (solo 6 filas del propio tenant); igual conviene policy preventiva.

## Conclusión
C2 deja de ser "migrar el backend a RLS" (ya hecho) y pasa a ser **"cerrar las policies faltantes en 4-5 tablas que SÍ fugan hoy a través del backend real"**. Mucho más chico y enfocado. El riesgo de "romper queries que dependían del bypass" es BAJO porque el backend ya vive bajo RLS hace tiempo sin romperse — solo agregamos policies a tablas que hoy no la tienen.

## Ajuste al plan
- Fase 0 (backup) ✅ hecha.
- Fase 1 staging: ya NO hace falta "crear rol pqrs_backend en prod" (existe). Sigue siendo útil validar las 5 policies nuevas en staging antes de prod, PERO staging está vacío → o se siembra, o se valida directo en prod con cuidado (las policies son aditivas y reversibles con DROP POLICY).
- El núcleo ahora: escribir y aplicar las 5 policies (4 directas + audit por JOIN), validar con pqrs_backend que cada tabla deja de fugar, sin romper el acceso legítimo.
