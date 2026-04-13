# Deudas técnicas registradas

## Motor SLA sectorial — deploy pendiente

**Estado:** dormido en `main` desde 2026-04-13
**Commits involucrados:**
- `c26bcee` — feat(sla): motor SLA sectorial — régimen FINANCIERO 8 días SFC
- `0713f74` — fix(sla): agregar tabla `festivos_colombia` 2026 a migración 14

### Por qué está dormido

La migración `aequitas_infrastructure/database/14_regimen_sectorial.sql` (169 líneas) **nunca corrió** contra la DB de producción `pqrs_v2`. El código en main hace queries a estructuras que no existen:

| Objeto | Tipo | Dónde se usa |
|---|---|---|
| `festivos_colombia` | tabla | `backend/app/core/models.py:259` (clase ORM huérfana, sin queries) |
| `sla_regimen_config` | tabla | `backend/app/api/routes/admin.py:487` |
| `clientes_tenant.regimen_sla` | columna | `backend/app/api/routes/admin.py:437, 462, 481` |

Ninguna existe en `pqrs_v2` hoy (verificado 2026-04-13 via `information_schema`).

### Endpoints afectados (en disco, NO en runtime)

4 rutas nuevas en `backend/app/api/routes/admin.py` (+227 líneas respecto al runtime actual `97f239e`):

- `GET /admin/regimen-sla/{cliente_id}` → línea ~430
- `POST /admin/regimen-sla/{cliente_id}` → línea ~444
- Otros 2 endpoints auxiliares de config

**Estado protegido**: los containers `pqrs_v2_backend` corriendo hoy están en commit `97f239e` que NO tiene estas rutas. Los endpoints existen solo en disco. Rebuildear `backend` sin aplicar migración primero → `500 column "regimen_sla" does not exist` al primer click.

### Plan de deploy futuro (cuando se aborde)

Orden obligatorio:

1. **Leer migración 14 completa** (169 líneas) y validar que no tiene `DROP`, `TRUNCATE`, `UPDATE` masivo, ni `FOREIGN KEY` contra tablas grandes.
2. **Backup DB pre-deploy** (`docker exec pqrs_v2_db pg_dump -F c`).
3. **Aplicar migración 14 contra `pqrs_v2`** manualmente:
   ```bash
   docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 < aequitas_infrastructure/database/14_regimen_sectorial.sql
   ```
4. **Verificar que las 2 tablas y la columna nueva existen**:
   ```sql
   SELECT count(*) FROM festivos_colombia;
   SELECT count(*) FROM sla_regimen_config;
   SELECT column_name FROM information_schema.columns WHERE table_name='clientes_tenant' AND column_name='regimen_sla';
   ```
5. **Smoke test de queries directas** de `admin.py` contra la DB real.
6. **Recién entonces rebuild de `pqrs_v2_backend`** con `docker compose up -d --no-deps --build backend`.
7. **Smoke test funcional** de los endpoints admin vía curl con JWT de super_admin.
8. **Comunicar a Paola (Recovery)** que hay tab nuevo de "Régimen SLA" disponible en admin.
9. **Ideal**: correr todo el ciclo primero en staging EC2 (`15.229.114.148`) con datos clonados de Recovery.

### Complejidad

**Medio-alta.** No es urgente — hoy nadie usa la feature. El bloqueo principal es validar que el SQL no tiene sorpresas (lo único que leí confirmado es la sección de `festivos_colombia` del commit `0713f74`, líneas 7-36). El resto del archivo (líneas 38-168) requiere lectura previa.

### Referencia cruzada

- Análisis forense completo del drift: ver `Brain/CHANGELOG.md` entrada `2026-04-13 (deploy nocturno)`.
- Regla anti-drift que previno este deploy en caliente: `Brain/00_DIRECTIVAS_CLAUDE_CODE.md` sección 3.5.
- Bug separado pendiente: visualización de `borrador_respuesta` en frontend pestaña Casos (tipo TS `Caso` no declara el campo).
