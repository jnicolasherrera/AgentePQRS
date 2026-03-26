# API Routes: Stats (Estadisticas)

## Archivo
`backend/app/api/routes/stats.py`

## Prefijo
`/api/v2/stats`

## Descripcion
Dashboard de estadisticas, rendimiento de abogados, distribucion por tipos y tendencias temporales.

## Endpoints

### GET /dashboard
- **Acceso:** Todos los autenticados (analista ve solo sus casos)
- **Parametros:** cliente_id (super_admin)
- **Retorna:**
  - **KPIs:** total_casos, casos_criticos, porcentaje_resueltos, abiertos, en_proceso, contestados, cerrados, casos_hoy, casos_semana, vencidos
  - **Trazabilidad:** recibidos, asignados, con_acuse, respondidos
  - **Distribucion:** por estado, por tipo
  - **Ultimos casos:** Top 50 con JOIN a clientes_tenant para nombre del tenant

### GET /rendimiento
- **Acceso:** Solo admin / super_admin
- **Parametros:** periodo (dia/semana/mes), cliente_id (super_admin)
- **Funcion:** Rendimiento por abogado/analista
- **Retorna por abogado:** asignados_periodo, asignados_total, cerrados_total, cerrados_periodo, vencidos, criticos, tasa_resolucion, avg_horas_resolucion
- **SQL:** Usa `FILTER (WHERE ...)` para conteos condicionales en una sola query

### GET /rendimiento/tipos
- **Acceso:** Solo admin / super_admin
- **Funcion:** Distribucion de casos por tipo en el periodo
- **Retorna:** Lista de {tipo, total}

### GET /rendimiento/tendencia
- **Acceso:** Solo admin / super_admin
- **Funcion:** Tendencia diaria de casos recibidos vs cerrados
- **Retorna:** Lista de {fecha, recibidos, cerrados}
- **Timezone:** Convierte a America/Bogota para agrupar por dia local

### GET /rendimiento/{abogado_id}/actividad
- **Acceso:** Admin o el propio abogado
- **Funcion:** Timeline detallado de actividad de un abogado
- **Retorna:** Casos asignados con eventos de audit_log_respuestas, horas_resolucion calculadas
- **Eventos:** ASIGNADO, BORRADOR_EDITADO, ENVIADO_LOTE, etc.
