# Sprint SLA Sectorial — Régimen Financiero SFC (8 abril 2026)

## Objetivo
Diferenciar los plazos SLA por sector regulatorio del tenant.
Brecha crítica #1 del análisis Bancolombia.

## Normativa implementada

| Régimen | QUEJA/RECLAMO | TUTELA | PETICION | SOLICITUD | CONSULTA | Norma base |
|---------|---------------|--------|----------|-----------|----------|------------|
| GENERAL | 15 días | 2 días | 15 días | 10 días | 30 días | Ley 1755/2015 |
| FINANCIERO | **8 días** | 2 días | 15 días | 10 días | 30 días | SFC Circular Básica Jurídica |
| SALUD | 15 días | 2 días | 15 días | 10 días | 30 días | Ley 1438/2011 |

## Archivos creados
- `aequitas_infrastructure/database/14_regimen_sectorial.sql`
- `scripts/test_sla_sectorial.py`

## Archivos modificados
- `backend/app/api/routes/admin.py` (3 endpoints nuevos)

## Cambios en base de datos

### Tabla nueva: `sla_regimen_config`
- Columnas: id, regimen, tipo_caso, dias_habiles, norma, descripcion, created_at
- Datos: 24 registros (8 tipos x 3 regímenes)
- Constraint UNIQUE: (regimen, tipo_caso)
- RLS: SELECT abierto para todos

### Columna nueva en `clientes_tenant`: `regimen_sla`
- Tipo: VARCHAR(50) NOT NULL DEFAULT 'GENERAL'
- Check: IN ('GENERAL','FINANCIERO','SALUD','SERVICIOS_PUBLICOS','TELECOMUNICACIONES')

### Tabla nueva: `festivos_colombia`
- 22 festivos colombianos 2026
- Usada por calcular_fecha_vencimiento() para contar días hábiles

### Función actualizada: `calcular_fecha_vencimiento(fecha_inicio, tenant_id, tipo_caso)`
- Lee regimen_sla del tenant dinámicamente
- Fallback a GENERAL si no encuentra config para el régimen
- Fallback a 15 días si no encuentra tipo_caso
- Excluye fines de semana y festivos de Colombia

### Trigger actualizado: `tg_set_fecha_vencimiento`
- Pasa NEW.cliente_id como tenant_id a la función

## Endpoints nuevos

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /api/v2/admin/tenant/regimen | Régimen actual del tenant |
| PATCH | /api/v2/admin/tenant/regimen | Cambiar régimen (solo admin) |
| GET | /api/v2/admin/tenant/sla-config | Tabla de plazos aplicables |

## Tests QA — 7/7 PASS

| Test | Resultado | Detalle |
|------|-----------|---------|
| 1. Tabla poblada | PASS | 24 registros |
| 2. FINANCIERO/QUEJA = 8 días | PASS | |
| 3. GENERAL/QUEJA = 15 días | PASS | |
| 4. Columna regimen_sla existe | PASS | |
| 5. Cálculo GENERAL/QUEJA | PASS | Vence 29/abr (21 días cal.) |
| 6. Cálculo FINANCIERO/QUEJA | PASS | Vence 20/abr (12 días cal.) |
| 7. TUTELA = 2 días hábiles | PASS | Vence 10/abr |

**Diferencia clave**: GENERAL vence 29/abr vs FINANCIERO vence 20/abr = **9 días menos para banco**

## Estado de deploy

| Entorno | Estado | Fecha |
|---------|--------|-------|
| PROD 18.228.54.9 | **PENDIENTE** (deploy en sprint aparte post-tutelas) | — |
| Staging 15.229.114.148 (esqueleto original) | APLICADO sobre schema incompleto | 8 abril 2026 |
| Staging 15.229.114.148 (reconstruido con baseline) | APLICADO limpio | 23 abril 2026 |

> **Corrección documental (2026-04-23):** La versión previa de esta tabla decía "Staging 18.228.54.9 APLICADO 8 abril 2026". Esa línea contenía dos errores:
>
> 1. **18.228.54.9 es PRODUCCIÓN**, no staging. El host de staging es 15.229.114.148.
> 2. **La migración 14 nunca corrió en prod** — verificado en sesión del 23-abr-2026 con `to_regclass('festivos_colombia') = f` y ausencia del SP `calcular_fecha_vencimiento`.
>
> Ver `Brain/sprints/SPRINT_TUTELAS_S123_ANALISIS_DRIFT.md` para el análisis completo del drift y `Brain/sprints/SPRINT_TUTELAS_S123_STAGING_REBUILD.md` para la reconstrucción de staging con baseline.

**NOTA**: Tenant arcsas.com.co permanece en GENERAL — no afectado.

## Para deployar a producción (cuando se autorice — sprint separado post-tutelas)

1. **Usar `migrations/14_regimen_sectorial.sql`, NO** `aequitas_infrastructure/database/14_regimen_sectorial.sql`. La versión de `migrations/` remueve la asignación `NEW.semaforo_sla := 'VERDE'` que rompería el trigger al primer INSERT (columna inexistente en prod). Ver `Brain/sprints/SPRINT_TUTELAS_S123_BLOQUEANTE_DRIFT_REPO.md` §Bloqueante 2.
2. Backup pre-deploy: `docker exec pqrs_v2_db pg_dump -F c pqrs_v2 > backup.dump`.
3. Ventana + aprobación explícita.
4. Aplicar con `./scripts/migrate.sh --env=prod` (agregar flag `--confirm-prod` si se incorpora posteriormente).
5. Verificación post-deploy: `to_regclass('festivos_colombia')`, `to_regclass('sla_regimen_config')`, columna `regimen_sla`, SP, trigger.
6. Rebuild backend: `docker compose up -d --build backend_v2`.
