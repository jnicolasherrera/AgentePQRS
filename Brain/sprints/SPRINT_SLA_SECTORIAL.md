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
| Staging 18.228.54.9 | APLICADO | 8 abril 2026 |
| Staging 15.229.114.148 | APLICADO | 8 abril 2026 |
| Producción | PENDIENTE | Requiere aprobación |

**NOTA**: Tenant arcsas.com.co permanece en GENERAL — no afectado.

## Para deployar a producción
1. Merge develop → main (ya tiene los commits)
2. `git pull origin main` en servidor
3. Aplicar migración:
   ```bash
   docker exec -i pqrs_v2_db psql -U pqrs_admin -d pqrs_v2 \
     < ~/PQRS_V2/aequitas_infrastructure/database/14_regimen_sectorial.sql
   ```
4. Rebuild backend: `docker compose up -d --build backend_v2`
