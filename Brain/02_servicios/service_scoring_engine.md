# Service: Scoring Engine

## Archivo
`backend/app/services/scoring_engine.py`

## Descripcion
Motor de scoring basado en reglas ponderadas para clasificacion de emails PQRS. Es la Capa 1 (rapida y gratuita) del sistema de clasificacion hibrida.

## Estructura de Reglas

```python
@dataclass(frozen=True)
class ScoringRule:
    pattern: str    # Regex pattern
    weight: float   # Peso del match
    category: str   # TUTELA, PETICION, QUEJA, RECLAMO, SOLICITUD, FELICITACION
    zone: str       # "subject", "body", "any"
```

## Reglas Definidas (83 reglas)

### TUTELA (17 reglas)
- "accion de tutela" (6.0 any), "decreto 2591" (5.0 any), "auto admisorio" (5.0 any)
- "tutela" en subject vale 3.0, en body vale 2.0
- Keywords judiciales: providencia, impugnacion, sentencia, fallo, demandante, juzgado, tribunal

### PETICION (11 reglas)
- "derecho de peticion" (6.0 any), "ley 1755" (5.0 any), "articulo 23" (4.0 any)
- "peticion" en subject vale 2.5, en body vale 1.0

### QUEJA (10 reglas)
- "queja formal" (5.0 any), "queja" en subject (3.0), en body (1.5)
- "inconformidad" (3.0), "mal servicio" (3.0), "insatisfecho" (2.0)

### RECLAMO (8 reglas)
- "cobro indebido" (5.0), "cargo no reconocido" (5.0), "error en factura" (4.0)
- "reclamo" en subject (3.0), en body (1.5)

### SOLICITUD (7 reglas)
- "solicitud formal" (4.0), "solicitud" en subject (2.5)

### FELICITACION (6 reglas)
- "felicitacion" (5.0), "excelente servicio" (4.0), "buen trabajo" (3.0)

## Multiplicador por Zona
- Match en `subject`: peso x 1.5 (el asunto es mas relevante)
- Match en `body`: peso x 1.0
- Match en `any`: se busca en ambos, subject tiene prioridad

## Senales Contextuales (apply_context_signals)

1. **Dominio judicial** + keywords de tutela: +4.0 TUTELA
2. **Dominio judicial** sin keywords tutela: +1.0 TUTELA
3. **"urgente"/"inmediata"** en subject: +1.5 TUTELA
4. **"48 horas"** en texto completo: +2.0 TUTELA
5. **"habeas data"** en texto: +2.0 PETICION

## Calculo de Confianza (compute_confidence)

Basado en el score absoluto y el margen entre top-1 y top-2:

| Score >= | Margen >= | Confianza |
|----------|-----------|-----------|
| 10.0     | 5.0       | 0.97      |
| 7.0      | 3.0       | 0.92      |
| 5.0      | 2.0       | 0.85      |
| 3.0      | 1.0       | 0.72      |
| 1.5      | --        | 0.55      |
| < 1.5    | --        | 0.40      |
| Sin match| --        | 0.30 (default PETICION) |

## Optimizacion
- `@lru_cache(maxsize=512)` para compilacion de regex patterns
- Patterns compilados una sola vez por sesion


## Referencias

- [[service_clasificador]]
- [[service_ai_classifier]]
