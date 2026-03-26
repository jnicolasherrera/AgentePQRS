# Aprendizaje Continuo IA -- FlexPQR

## Sistema de Clasificacion Hibrida

FlexPQR usa un sistema de clasificacion de dos capas que mejora con el tiempo:

### Capa 1: Scoring Engine (Keywords)
- **Archivo:** `backend/app/services/scoring_engine.py`
- Reglas ponderadas (`ScoringRule`) con pattern, weight, category y zone
- Zonas: `subject` (peso x1.5 si match), `body`, `any`
- Senales contextuales: dominios judiciales (+4.0 TUTELA), "48 horas" (+2.0 TUTELA), "habeas data" (+2.0 PETICION)
- Confianza: calculada por margen entre top-1 y top-2 scores (0.40 a 0.97)

### Capa 2: Claude Haiku (LLM)
- **Archivo:** `backend/app/services/ai_engine.py`
- Solo se invoca si confianza de Capa 1 < 0.70
- Usa tool_use con schema estructurado (`clasificar_pqr`)
- System prompt especializado en derecho colombiano
- Recibe los scores de keywords como contexto adicional

### Merge de Confianza
- Si ambas capas coinciden: boost +0.08
- Si Claude tiene >= 0.70: prevalece Claude
- Si Claude < 0.70: max(claude_conf, 0.50)

## Feedback Loop

### Clasificacion Feedback
- **Tabla:** `clasificacion_feedback` -- registra divergencias entre keywords y Claude
- Campos: email_hash, keyword_tipo, keyword_confianza, claude_tipo, claude_confianza, claude_razonamiento
- Se alimenta automaticamente cuando Claude corrige la clasificacion de keywords

### PQRS Clasificacion Feedback (Manual)
- **Tabla:** `pqrs_clasificacion_feedback` -- feedback humano via admin
- Endpoint: `POST /api/v2/admin/casos/{caso_id}/feedback`
- El admin puede marcar si un caso es_pqrs y la clasificacion_correcta
- Contador de correcciones por tenant para ajustar boost en futuro

### Borrador Feedback
- **Tabla:** `borrador_feedback` -- mide cuanto edita el abogado el borrador de IA
- Cuando un usuario edita el borrador, se calcula `similarity_score` (SequenceMatcher)
- Se guarda original_ai vs editado_usuario (truncado a 2000 chars)

## Deteccion de Problematicas

El sistema detecta problematicas especificas para personalizar borradores:
- SUPLANTACION_RAPICREDIT
- PAZ_Y_SALVO_RAPICREDIT
- SUPLANTACION_GENERAL
- PAZ_Y_SALVO_FINDORSE
- DEBITOS_AUTOMATICOS
- ELIMINACION_CENTRALES_PAZ_SALVO
- ELIMINACION_CENTRALES_PROPIA
- SIN_IDENTIFICACION

Cada problematica se mapea a una plantilla en `plantillas_respuesta` por tenant.

## Filtrado de Spam
- Dominios bloqueados: litigando.com, hablame.co, noreply@, etc.
- Asuntos bloqueados: "generacion de demanda", "marketing", "newsletter", etc.
- Funcion `parece_pqrs()` combina anti-spam + scores para determinar si el email es una PQR real


## Referencias

- [[service_ai_classifier]]
- [[service_clasificador]]
- [[service_scoring_engine]]
- [[worker_kafka_consumer]]
