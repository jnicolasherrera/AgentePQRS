# Service: AI Classifier

## Archivo
`backend/app/services/ai_classifier.py`

## Descripcion
Orquesta la clasificacion de eventos de email provenientes de Kafka. Usa la clasificacion hibrida (keywords + Claude) con retry exponencial ante rate limits y Claim Check inverso para adjuntos.

## Clase Principal: ClassificationResult

```python
@dataclass
class ClassificationResult:
    tipo_caso: str          # "TUTELA" | "PETICION" | "QUEJA" | etc.
    prioridad: str          # "CRITICA" | "ALTA" | "MEDIA" | "BAJA"
    plazo_dias: int         # Dias habiles segun normativa
    cedula: str | None
    nombre_cliente: str | None
    es_juzgado: bool
    confianza: float
    borrador: str | None
```

## Funcion Principal: classify_email_event(event)

### Flujo
1. Extrae asunto, cuerpo, remitente del evento (claves en espanol o ingles)
2. **Claim Check inverso:** Si hay `adjunto_s3_uri`, descarga de MinIO (max 3000 bytes) y agrega al cuerpo
3. Llama `clasificar_hibrido(asunto, cuerpo, remitente)` con retry
4. Convierte ResultadoClasificacion a ClassificationResult

### Retry Exponencial
- Max 5 intentos
- Base: 2 segundos (2s, 4s, 8s, 16s, 32s)
- Solo ante `anthropic.RateLimitError`
- Si se agotan intentos: lanza `PoisonPillError`

## PoisonPillError
Excepcion que indica que el mensaje debe ir a la Dead Letter Queue. El consumer la captura y envia el mensaje a `pqrs.events.dead_letter`.

## Claim Check Inverso
Los adjuntos grandes viajan en MinIO, no en Kafka. El classifier los descarga para enriquecer el texto de clasificacion:
- Limite de bytes enviados al clasificador: 3000
- Descarga en thread pool (`run_in_executor`) para no bloquear el event loop
- Si la descarga falla, continua sin adjunto (graceful degradation)

## Dependencias
- `app.services.ai_engine.clasificar_hibrido` -- Motor hibrido de clasificacion
- `app.services.storage_engine.download_file` -- Descarga desde MinIO
- `app.core.config.PLAZOS_DIAS_HABILES, PRIORIDADES` -- Business rules
