# Frontend: UI Kanban

## Estado Actual

El Kanban board esta planificado pero no implementado como componente visual drag-and-drop. Actualmente los casos se visualizan como tabla paginada.

## Modelo de Estados del Caso

Los estados forman un pipeline natural para Kanban:

```
ABIERTO -> EN_PROCESO -> CONTESTADO -> CERRADO
                    \-> PENDIENTE_INFO -/
```

### Estados Validos (enums.py)
- **NUEVO** -- Recien ingresado
- **EN_PROCESO** -- Analista trabajando
- **PENDIENTE_INFO** -- Se requiere informacion adicional
- **RESPONDIDO** -- Borrador enviado
- **CERRADO** -- Caso resuelto
- **VENCIDO** -- Paso el plazo legal

## Datos Disponibles para Kanban

El endpoint `GET /api/v2/stats/dashboard` retorna:
```json
{
  "distribucion": {
    "ABIERTO": 45,
    "EN_PROCESO": 12,
    "CERRADO": 238,
    ...
  },
  "ultimos_casos": [...]
}
```

## Actualizacion de Estado

`PATCH /api/v2/casos/{caso_id}` permite actualizar estado y prioridad:
```json
{ "estado": "EN_PROCESO" }
```

## Vision de Implementacion

- Columnas por estado (drag and drop)
- Cards con: radicado, asunto, tipo (badge color), prioridad, vencimiento, asignado
- SSE para nuevas cards que aparecen en tiempo real
- Filtros por tipo, prioridad, asignado
- Contador por columna
