# Service: Clasificador (Keywords)

## Archivo
`backend/app/services/clasificador.py`

## Descripcion
Clasificador basado en keywords y reglas de negocio. Es la Capa 1 del sistema de clasificacion hibrida. Rapido y sin costo de API.

## Funcion Principal: clasificar_texto(asunto, cuerpo, remitente)

### Flujo
1. Verifica si es remitente de juzgado (dominios .gov.co judiciales)
2. Llama `score_and_classify()` del scoring_engine
3. Convierte resultado a `ResultadoClasificacion`
4. Extrae radicado, cedula, nombre del texto usando regex

### ResultadoClasificacion
```python
@dataclass
class ResultadoClasificacion:
    tipo: TipoCaso
    prioridad: Prioridad
    plazo_dias: int
    radicado: str | None
    cedula: str | None
    nombre_cliente: str | None
    es_juzgado: bool
    confianza: float
```

## Funciones de Extraccion

### extraer_radicado(texto)
Regex patterns:
- `\d{2,4}[-/]\d{2,4}[-/]\d{2,8}` (formato fecha-like)
- `RAD[ICADO]*[:\s]*(\d{10,25})`
- `No\.\s*(\d{10,25})`
- `(\d{23})` (radicado de 23 digitos)

### extraer_cedula(texto)
Regex: `(?:c\.c\.|cedula|cc|nit)[:\s#]*(\d{6,12})`

### extraer_nombre(texto)
Regex: `(?:senor|sra\.|accionante|demandante|cliente)[:\s]*([a-z]{5,50})`

## Anti-Spam

### Dominios spam
litigando.com, hablame.co, noreply@, no-reply@, newsletter@, marketing@

### Asuntos spam
"generacion de demanda", "marketing", "newsletter", "publicidad", "webinar", etc.

### parece_pqrs(subject, body, sender)
Combina anti-spam + scoring para determinar si el email es PQR real:
1. Si es spam -> False
2. Si es de juzgado -> True
3. Si scoring tiene algun valor > 0 -> True

## Dominios de Juzgado
@cendoj.ramajudicial.gov.co, @notificacionesrj.gov.co, @consejodeestado.gov.co, @cortesuprema.gov.co, @corteconstitucional.gov.co, @ramajudicial.gov.co, @fiscalia.gov.co, @procuraduria.gov.co

Tambien keywords: juzgado, tribunal, corte, judicial, magistrad
