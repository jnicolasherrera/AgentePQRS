---
tags:
  - brain/frontend
---

# Frontend: Tablas Interactivas

## Estado Actual

Las tablas del dashboard usan paginacion server-side con los siguientes parametros:

### Parametros de Listado (GET /api/v2/admin/casos)
- `page` -- Numero de pagina (1-based)
- `page_size` -- Registros por pagina (default 50)
- `tipo` -- Filtro por tipo de caso
- `estado` -- Filtro por estado
- `asignado_a` -- Filtro por analista asignado
- `es_pqrs` -- Filtro booleano PQRS vs no-PQRS
- `q` -- Busqueda de texto en asunto y email_origen (ILIKE)
- `sort_by` -- Columna de ordenamiento
- `sort_dir` -- Direccion (asc/desc)
- `cliente_id` -- Filtro por tenant (super_admin)

### Columnas Ordenables
- radicado, asunto, tipo, estado, prioridad, recibido, vencimiento, asignado

### Respuesta
```json
{
  "items": [...],
  "total": 1234,
  "page": 1,
  "page_size": 50
}
```

## Mejoras Planificadas (No Implementadas)

### Virtualizacion
- `tanstack/react-virtual` o `react-window` para listas de 50,000+ casos
- Solo renderizar filas visibles en el viewport
- Target: < 150MB de memoria de navegador

### Cache Client-Side
- TanStack Query con stale-while-revalidate
- Cache por query key (tipo, estado, pagina)
- Re-fetch on focus / background poll

### Busqueda Debounced
- 300ms debounce en el campo de busqueda
- Evita saturar PostgreSQL con cada keystroke
